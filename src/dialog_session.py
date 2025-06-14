import asyncio
import queue
import signal
import threading
import time
import uuid
from typing import Dict, Any

from src import config
from src.audio_converter import OggToPcmConverter, detect_audio_format, debug_audio_data
from src.audio_manager import AudioDeviceManager, AudioConfig, save_pcm_to_wav
from src.socket_manager import SocketAudioManager, SocketConfig
from src.webrtc_manager import WebRTCManager
from src.logger import logger, set_debug_mode
from src.protocol import ServerEvent
from src.dialog_client import RealtimeDialogClient


class DialogSession:
    """对话会话管理类"""

    def __init__(self, ws_config: Dict[str, Any], debug_mode: bool = False, socket_mode: bool = False, webrtc_mode: bool = False):
        # 设置调试模式
        set_debug_mode(debug_mode)

        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

        self.client = RealtimeDialogClient(config=ws_config, session_id=self.session_id)
        self.socket_mode = socket_mode
        self.webrtc_mode = webrtc_mode

        output_audio_config = config.ogg_output_audio_config

        # override output config using tts_audio_config
        tts_config = config.start_session_req.get("tts")
        if tts_config:
            tts_audio_config = tts_config.get("audio_config")
            if tts_audio_config:
                output_audio_config = tts_audio_config  # output_audio_config['channels'] = tts_audio_config.pop("channel")  # output_audio_config['chunk'] = 3200

        if self.webrtc_mode:
            # WebRTC模式
            self.webrtc_manager = WebRTCManager(
                signaling_host=config.webrtc_config['signaling_host'],
                signaling_port=config.webrtc_config['signaling_port']
            )
            self.webrtc_manager.set_audio_input_callback(self._handle_webrtc_audio_input)
            self.audio_device = None
            self.socket_manager = None
        elif self.socket_mode:
            # Socket模式
            self.socket_manager = SocketAudioManager(SocketConfig(**config.socket_config))
            self.socket_manager.set_audio_input_callback(self._handle_socket_audio_input)
            self.audio_device = None
            self.webrtc_manager = None
        else:
            # 传统音频设备模式
            self.audio_device = AudioDeviceManager(AudioConfig(**config.input_audio_config),
                AudioConfig(**output_audio_config))
            self.socket_manager = None
            self.webrtc_manager = None
            
        self.output_config = AudioConfig(**config.ogg_output_audio_config)

        self.is_running = True
        self.is_session_finished = False

        signal.signal(signal.SIGINT, self._keyboard_signal)
        # 初始化音频队列和输出流 - 限制队列大小防止延迟累积
        self.audio_queue = queue.Queue(maxsize=50)
        
        if not self.socket_mode and not self.webrtc_mode:
            self.output_stream = self.audio_device.open_output_stream()
            # 启动播放线程
            self.is_recording = True
            self.is_playing = True
            self.player_thread = threading.Thread(target=self._audio_player_thread)
            self.player_thread.daemon = True
            self.player_thread.start()
        else:
            self.output_stream = None
            self.is_recording = True
            self.is_playing = False
            self.player_thread = None

        # 音频转换器
        self.ogg_converter = OggToPcmConverter(sample_rate=self.output_config.sample_rate,
            channels=self.output_config.channels)

        # 统计信息
        self.stats = {'audio_queue_overflows': 0
        }

        # 实时字幕显示
        self.current_user_text = ""  # 当前用户说话内容
        self.current_ai_text = ""  # 当前AI回复内容
        self.conversation_history = []  # 对话历史
        self.subtitle_lock = threading.Lock()  # 字幕显示线程锁
        self.console_lines = []  # 控制台显示缓存
        self.is_user_speaking = False  # 用户正在说话状态
        self.is_ai_responding = False  # AI正在回复状态
        self.last_displayed_ai_text = ""  # 上次显示的AI文本，避免重复显示
        self.stats_logged = False  # 统计信息是否已输出，避免重复

    def _audio_player_thread(self):
        """音频播放线程 - 改进的错误处理"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.is_playing:
            try:
                # 从队列获取音频数据
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is not None and len(audio_data) > 0:
                    self.output_stream.write(audio_data)
                    consecutive_errors = 0  # 重置错误计数

            except queue.Empty:
                # 队列为空时等待一小段时间
                time.sleep(0.1)
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.debug(f"音频播放错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("连续播放错误过多，尝试重新初始化音频流")
                    try:
                        # 重新初始化输出流
                        if self.output_stream:
                            self.output_stream.stop_stream()
                            self.output_stream.close()
                        self.output_stream = self.audio_device.open_output_stream()
                        consecutive_errors = 0
                        logger.info("音频流重新初始化成功")
                    except Exception as reinit_error:
                        logger.error(f"音频流重新初始化失败: {reinit_error}")
                        time.sleep(1.0)
                else:
                    time.sleep(0.2)

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        """处理服务器响应"""
        if response == {}:
            return

        if response['message_type'] == 'SERVER_ACK':
            # 检查事件类型，特别处理TTSResponse事件(352)的二进制音频数据
            event = response.get('event', 0)

            # 检查是否包含音频数据
            if isinstance(response.get('payload_msg'), bytes):
                audio_data = response['payload_msg']

                if len(audio_data) == 0:
                    return

                # 特殊处理TTSResponse事件的音频数据
                if event == ServerEvent.TTS_RESPONSE:
                    logger.debug(f"🎵 收到TTSResponse音频数据: {len(audio_data)}字节")

                # 调试：分析音频数据
                debug_audio_data(audio_data)

                # 检测音频格式
                audio_format = detect_audio_format(audio_data)

                # logger.info(f"format: {audio_format}")
                # 如果是 OGG 格式，处理流式数据
                if audio_format == "ogg":
                    audio_data = self.ogg_converter.convert(audio_data)

                if self.webrtc_mode:
                    # WebRTC模式：暂时禁用音频输出，避免爆音问题
                    # TODO: 修复音频格式兼容性后重新启用
                    # if self.webrtc_manager:
                    #     self.webrtc_manager.send_audio_to_all_clients(audio_data)
                    logger.debug(f"🔇 跳过音频输出 (WebRTC模式): {len(audio_data)}字节")
                elif self.socket_mode:
                    # Socket模式：直接发送给客户端
                    format_type = "ogg" if audio_format == "ogg" else "pcm"
                    if self.socket_manager:
                        self.socket_manager.send_audio_output(audio_data, format_type)
                else:
                    # 传统模式：加入播放队列
                    try:
                        self.audio_queue.put(audio_data, timeout=0.1)
                    except queue.Full:
                        self.stats['audio_queue_overflows'] += 1
                        if self.stats['audio_queue_overflows'] % 10 == 1:  # 每10次溢出才输出一次警告
                            logger.debug(f"⚠️ 音频队列溢出 (第{self.stats['audio_queue_overflows']}次)")

            # 检查是否包含AI文本回复 (这应该通过ChatResponse事件550处理)
            elif isinstance(response.get('payload_msg'), dict):
                ai_content = response.get('payload_msg', {}).get('content', '')
                if ai_content:
                    # AI实时文本回复 - 这里主要是兼容性处理
                    logger.debug(f"🤖 AI文本回复(SERVER_ACK): '{ai_content}'")
                    self.current_ai_text += ai_content
                    self._display_subtitle(ai_text=self.current_ai_text, is_final=False)
        elif response['message_type'] == 'SERVER_FULL_RESPONSE':
            event = response.get('event', 'unknown')
            # 只在调试模式下记录详细日志
            if logger.level <= 10:  # DEBUG level
                logger.debug(f'Event: {event}, Response: {response}\n')
            payload_msg = response.get('payload_msg', {})

            # 记录重要服务器事件，过滤调试噪音
            connection_events = [ServerEvent.CONNECTION_STARTED, ServerEvent.CONNECTION_FAILED,
                                 ServerEvent.CONNECTION_FINISHED, ServerEvent.SESSION_STARTED,
                                 ServerEvent.SESSION_FINISHED, ServerEvent.SESSION_FAILED]

            if event in connection_events:
                logger.info(f"📡 {ServerEvent(event).name}")
            else:
                # 其他事件只在调试模式下显示
                event_name = ServerEvent(event).name if event in ServerEvent._value2member_map_ else f'Unknown({event})'
                logger.debug(f"📡 {event_name}")

            # 处理服务器事件
            if event == ServerEvent.CONNECTION_STARTED:
                logger.info("🔗 连接已建立")
            elif event == ServerEvent.CONNECTION_FAILED:
                error = payload_msg.get('error', 'Unknown error')
                logger.error(f"❌ 连接失败: {error}")
            elif event == ServerEvent.CONNECTION_FINISHED:
                logger.info("🔗 连接已结束")
            elif event == ServerEvent.SESSION_STARTED:
                dialog_id = payload_msg.get('dialog_id', '')
                logger.info(f"🚀 会话已启动 (Dialog ID: {dialog_id[:8]}...)")
                # 会话启动成功后发送SayHello
                asyncio.create_task(self.client.say_hello("你好，我是你的语音助手，有什么可以帮助你的吗？"))
            elif event == ServerEvent.SESSION_FINISHED:
                logger.info("✅ 会话已结束")
            elif event == ServerEvent.SESSION_FAILED:
                error = payload_msg.get('error', 'Unknown error')
                logger.error(f"❌ 会话失败: {error}")
            elif event == ServerEvent.TTS_SENTENCE_START:
                tts_type = payload_msg.get('tts_type', 'default')
                text = payload_msg.get('text', '')
                logger.debug(f"🎵 TTS开始: {tts_type} - '{text[:30]}...'")  # TTS开始时不清空AI文本，因为CHAT_RESPONSE可能还在继续
            elif event == ServerEvent.TTS_SENTENCE_END:
                logger.debug("🎵 TTS句子结束")
            elif event == ServerEvent.TTS_RESPONSE:
                # 这个事件的音频数据已经在 SERVER_ACK 中处理了
                logger.debug("🎵 收到TTS音频数据")
            elif event == ServerEvent.TTS_ENDED:
                logger.debug("🎵 TTS音频合成结束")
                # TTS完成，结束这轮对话
                self._finalize_conversation_turn()
            elif event == ServerEvent.ASR_INFO:
                # 清空音频队列，停止当前播放
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break
                # 重置OGG转换器
                self.ogg_converter.reset()
                logger.debug("已清空音频缓冲区 (用户打断)")
                # 开始用户说话状态
                self.is_user_speaking = True
                self.is_ai_responding = False
                self.current_user_text = ""
                self._update_console_display()
            elif event == ServerEvent.ASR_RESPONSE:
                results = payload_msg.get('results', [])
                if results and len(results) > 0:
                    text = results[0].get('text', '')
                    is_interim = results[0].get('is_interim', False)
                    if text and text.strip():
                        self.current_user_text = text
                        self._update_console_display()
                        logger.debug(f"👤 用户语音识别: '{text}' (临时: {is_interim})")
            elif event == ServerEvent.ASR_ENDED:
                self.is_user_speaking = False
                if self.current_user_text and self.current_user_text.strip():
                    self._update_console_display(final_user=True)
                logger.debug("语音识别结束")
            elif event == ServerEvent.CHAT_RESPONSE:
                content = payload_msg.get('content', '')
                if content and content.strip():
                    # AI实时文本回复 - 累积显示
                    if not self.is_ai_responding:
                        self.is_ai_responding = True
                        self.current_ai_text = ""  # 只在第一次CHAT_RESPONSE时清空
                        self.last_displayed_ai_text = ""  # 重置显示记录
                    self.current_ai_text += content
                    # 限制更新频率，避免过度刷新
                    if len(self.current_ai_text) - len(self.last_displayed_ai_text) >= 5 or content.endswith(('。', '！',
                                                                                                              '？', '，',
                                                                                                              '、')):
                        self._update_console_display()
                    logger.debug(f"🤖 AI文本回复: '{content}' → 总计: '{self.current_ai_text[:50]}...'")
            elif event == ServerEvent.CHAT_ENDED:
                logger.debug("🤖 AI文本回复结束")
                # 不在这里显示最终AI文本，等待TTS_ENDED时统一处理
                self.is_ai_responding = False
            else:
                # 其他未知事件
                logger.debug(f"📡 未知事件: {event}")
        elif response['message_type'] == 'SERVER_ERROR':
            logger.error(f"服务器错误: {response['payload_msg']}")
            raise Exception("服务器错误")

    def _display_welcome_screen(self):
        """显示欢迎界面"""
        # 清屏
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🎙️ 🤖  实时语音对话系统  🤖 🎙️")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🎤 直接说话，系统会实时识别您的语音")
        print("   • 🤖 AI助手会语音回复，同时显示文字")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print("🚀 系统已就绪，请开始说话...")
        print("=" * 80 + "\n")
        
    def _display_welcome_screen_socket(self):
        """显示Socket模式欢迎界面"""
        # 清屏
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🔌 🤖  实时语音对话系统 (Socket模式)  🤖 🔌")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🔌 通过Socket接收客户端音频输入")
        print("   • 🤖 AI助手会通过Socket返回音频回复")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print(f"🚀 Socket服务器已启动: {config.socket_config['host']}:{config.socket_config['port']}")
        print("等待客户端连接...")
        print("=" * 80 + "\n")
        
    def _display_welcome_screen_webrtc(self):
        """显示WebRTC模式欢迎界面"""
        # 清屏
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🌐 🤖  实时语音对话系统 (WebRTC模式)  🤖 🌐")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🌐 通过WebRTC接收浏览器音频输入")
        print("   • 🤖 AI助手会通过WebRTC返回音频回复")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print(f"🚀 WebRTC信令服务器已启动: {config.webrtc_config['signaling_host']}:{config.webrtc_config['signaling_port']}")
        print("请在浏览器中打开测试页面进行连接...")
        print("=" * 80 + "\n")

    def _clear_current_line(self):
        """清除当前行"""
        print("\r\033[K", end="", flush=True)

    def _update_console_display(self, final_user: bool = False, final_ai: bool = False):
        """更新控制台显示"""
        with self.subtitle_lock:
            if final_user and self.current_user_text:
                # 用户说话完成，显示最终结果
                self._clear_current_line()
                print(f"👤 用户: {self.current_user_text}")
                return
            elif final_ai and self.current_ai_text:
                # AI回复完成，显示最终结果
                self._clear_current_line()
                print(f"🤖 AI: {self.current_ai_text}")
                self.last_displayed_ai_text = self.current_ai_text  # 记录已显示的文本
                return

            # 实时更新逻辑
            if self.is_user_speaking and self.current_user_text:
                # 用户正在说话，实时更新
                self._clear_current_line()
                display_text = self.current_user_text[
                               :150] + "..." if len(self.current_user_text) > 150 else self.current_user_text
                print(f"👤 用户: {display_text}", end="", flush=True)
            elif self.is_ai_responding and self.current_ai_text:
                # AI正在回复，实时更新 - 只有当文本真正改变时才更新
                if self.current_ai_text != self.last_displayed_ai_text:
                    self._clear_current_line()
                    display_text = self.current_ai_text[
                                   :150] + "..." if len(self.current_ai_text) > 150 else self.current_ai_text
                    print(f"🤖 AI: {display_text}", end="", flush=True)
                    self.last_displayed_ai_text = self.current_ai_text
            elif not self.is_user_speaking and not self.is_ai_responding:
                # 等待状态
                self._clear_current_line()
                print("🎙️ 请说话...", end="", flush=True)

    def _finalize_conversation_turn(self):
        """完成一轮对话"""
        with self.subtitle_lock:
            if self.current_user_text or self.current_ai_text:
                # 确保最终AI文本被显示
                if self.current_ai_text and self.current_ai_text != self.last_displayed_ai_text:
                    self._clear_current_line()
                    print(f"🤖 AI: {self.current_ai_text}")

                # 保存到对话历史
                self.conversation_history.append({
                    'user': self.current_user_text,
                    'ai': self.current_ai_text,
                    'timestamp': time.time()
                })

                # 清空当前内容
                self.current_user_text = ""
                self.current_ai_text = ""
                self.last_displayed_ai_text = ""
                self.is_user_speaking = False
                self.is_ai_responding = False

                # 显示简洁的分隔线
                print(f"\n{'─' * 50}")
                print(f"📊 第{len(self.conversation_history)}轮对话 | ⏰ {time.strftime('%H:%M:%S')}")
                print(f"{'─' * 50}\n")

                # 显示等待状态
                print("🎙️ 请说话...", end="", flush=True)

    def log_stats(self):
        """输出统计信息"""
        if self.stats_logged:
            return  # 避免重复输出

        self.stats_logged = True
        logger.info("=== 音频处理统计 ===")

        # 获取OGG转换器统计信息
        converter_stats = self.ogg_converter.get_stats()
        logger.info(f"接收OGG页面数: {converter_stats['ogg_pages_received']}")
        logger.info(f"解码PCM字节数: {converter_stats['pcm_bytes_decoded']}")
        logger.info(f"解码错误次数: {converter_stats['decoding_errors']}")

        logger.info(f"队列溢出次数: {self.stats['audio_queue_overflows']}")
        logger.info(f"对话轮次: {len(self.conversation_history)}")
        logger.info("==================")

    def _keyboard_signal(self, sig, frame):
        logger.info("👋 收到退出信号，正在关闭...")
        self.log_stats()
        self.is_recording = False
        self.is_playing = False
        self.is_running = False
        
        # 强制退出WebRTC相关资源
        if self.webrtc_mode and self.webrtc_manager:
            try:
                # 在后台异步停止WebRTC管理器
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.webrtc_manager.stop())
                else:
                    loop.run_until_complete(self.webrtc_manager.stop())
            except Exception as e:
                logger.error(f"停止WebRTC管理器错误: {e}")
        
        # 强制退出
        import os
        os._exit(0)

    async def receive_loop(self):
        try:
            while True:
                response = await self.client.receive_server_response()
                self.handle_server_response(response)
                if 'event' in response and (response['event'] == ServerEvent.SESSION_FINISHED or response[
                    'event'] == ServerEvent.SESSION_FAILED):
                    logger.info(f"接收到会话结束事件: {ServerEvent(response['event']).name}({response['event']})")
                    self.is_session_finished = True
                    break
        except asyncio.CancelledError:
            logger.info("接收任务已取消")
        except Exception as e:
            logger.error(f"接收消息错误: {e}")

    def _handle_socket_audio_input(self, audio_data: bytes) -> None:
        """处理Socket音频输入"""
        try:
            # 创建异步任务发送音频数据
            asyncio.create_task(self.client.task_request(audio_data))
        except Exception as e:
            logger.error(f"处理Socket音频输入错误: {e}")
    
    def _handle_webrtc_audio_input(self, audio_data: bytes) -> None:
        """处理WebRTC音频输入"""
        try:
            # 检查是否仍在运行
            if not self.is_running or not self.is_recording:
                return
                
            # 检查WebSocket连接状态
            if not self.client.ws or hasattr(self.client.ws, 'closed') and self.client.ws.closed:
                logger.warning("WebSocket连接已关闭，停止音频处理")
                self.is_running = False
                self.is_recording = False
                return
                
            # 创建异步任务发送音频数据
            asyncio.create_task(self.client.task_request(audio_data))
        except Exception as e:
            logger.error(f"处理WebRTC音频输入错误: {e}")
            # 如果发送失败，停止处理
            self.is_running = False
            self.is_recording = False
    
    async def process_microphone_input(self) -> None:
        """处理麦克风输入"""
        stream = self.audio_device.open_input_stream()
        logger.info("🎙️ 麦克风已就绪，开始监听...")

        # 显示欢迎界面
        self._display_welcome_screen()

        while self.is_recording:
            try:
                # 添加exception_on_overflow=False参数来忽略溢出错误
                audio_data = stream.read(config.input_audio_config["chunk"], exception_on_overflow=False)
                save_pcm_to_wav(audio_data, "../output.wav")
                await self.client.task_request(audio_data)
                await asyncio.sleep(0.01)  # 避免CPU过度使用
            except Exception as e:
                logger.error(f"读取麦克风数据出错: {e}")
                await asyncio.sleep(0.1)  # 给系统一些恢复时间
    
    async def process_socket_input(self) -> None:
        """处理Socket输入模式"""
        if not self.socket_manager:
            logger.error("Socket管理器未初始化")
            return
            
        logger.info("🔌 启动Socket服务器...")
        await self.socket_manager.start_server()
        
        # 显示欢迎界面
        self._display_welcome_screen_socket()
        
        # 等待连接和处理
        while self.is_recording:
            if not self.socket_manager.is_connected:
                await asyncio.sleep(0.1)  # 等待客户端连接
            else:
                await asyncio.sleep(0.01)  # 保持活跃
    
    async def process_webrtc_input(self) -> None:
        """处理WebRTC输入模式"""
        if not self.webrtc_manager:
            logger.error("WebRTC管理器未初始化")
            return
            
        logger.info("🌐 启动WebRTC服务器...")
        await self.webrtc_manager.start()
        
        # 显示欢迎界面
        self._display_welcome_screen_webrtc()
        
        # 等待连接和处理
        while self.is_recording:
            await asyncio.sleep(0.1)  # 保持活跃

    async def start(self) -> None:
        """启动对话会话"""
        try:
            # 建立WebSocket连接
            await self.client.connect()

            # 启动接收循环
            receive_task = asyncio.create_task(self.receive_loop())

            # 发送连接和会话初始化请求
            await self.client.start_connection()
            await self.client.start_session()

            # 等待一下确保连接事件被处理
            await asyncio.sleep(0.1)

            # 启动音频输入处理
            if self.webrtc_mode:
                asyncio.create_task(self.process_webrtc_input())
            elif self.socket_mode:
                asyncio.create_task(self.process_socket_input())
            else:
                asyncio.create_task(self.process_microphone_input())

            # 保持主循环运行，监控连接状态
            while self.is_running:
                # 检查WebSocket连接状态
                if not self.client.ws or (hasattr(self.client.ws, 'closed') and self.client.ws.closed):
                    logger.error("🔴 WebSocket连接断开，程序即将退出...")
                    self.is_running = False
                    break
                
                await asyncio.sleep(0.5)  # 每500ms检查一次

            await self.client.finish_session()
            while not self.is_session_finished:
                await asyncio.sleep(0.1)
            await self.client.finish_connection()
            await asyncio.sleep(0.1)
            await self.client.close()
            logger.info(f"对话请求日志ID: {self.client.logid}")
            self.log_stats()
        except Exception as e:
            logger.error(f"会话错误: {e}")
        finally:
            if self.webrtc_mode and self.webrtc_manager:
                await self.webrtc_manager.stop()
            elif self.socket_mode and self.socket_manager:
                self.socket_manager.cleanup()
            elif self.audio_device:
                self.audio_device.cleanup()

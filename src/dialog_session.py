import asyncio
import io
import queue
import signal
import threading
import time
import uuid
from enum import IntEnum
from typing import Dict, Any

import numpy as np
from pydub import AudioSegment


class ServerEvent(IntEnum):
    """服务端事件类型枚举"""
    # Connect类事件
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52
    
    # Session类事件
    SESSION_STARTED = 150
    SESSION_FINISHED = 152
    SESSION_FAILED = 153
    
    # TTS类事件
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352
    TTS_ENDED = 359
    
    # ASR类事件
    ASR_INFO = 450
    ASR_RESPONSE = 451
    ASR_ENDED = 459
    
    # Chat类事件
    CHAT_RESPONSE = 550
    CHAT_ENDED = 559

from src import config
from src.audio_manager import set_debug_mode, logger, AudioDeviceManager, AudioConfig, save_pcm_to_wav
from src.realtime_dialog_client import RealtimeDialogClient


class DialogSession:
    """对话会话管理类"""

    def __init__(self, ws_config: Dict[str, Any], debug_mode: bool = False):
        # 设置调试模式
        set_debug_mode(debug_mode)

        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

        self.client = RealtimeDialogClient(config=ws_config, session_id=self.session_id)
        self.audio_device = AudioDeviceManager(
            AudioConfig(**config.input_audio_config),
            AudioConfig(**config.output_audio_config)
        )
        self.output_config = AudioConfig(**config.output_audio_config)

        self.is_running = True
        self.is_session_finished = False

        signal.signal(signal.SIGINT, self._keyboard_signal)
        # 初始化音频队列和输出流 - 限制队列大小防止延迟累积
        self.audio_queue = queue.Queue(maxsize=50)
        self.output_stream = self.audio_device.open_output_stream()
        # 启动播放线程
        self.is_recording = True
        self.is_playing = True
        self.player_thread = threading.Thread(target=self._audio_player_thread)
        self.player_thread.daemon = True
        self.player_thread.start()

        # OGG 流缓存 - 改进的缓冲管理
        self.ogg_buffer = bytearray()
        self.last_pcm_size = 0  # 记录上次解码的PCM数据大小

        # 统计信息
        self.stats = {
            'ogg_pages_received': 0,
            'pcm_bytes_decoded': 0,
            'audio_queue_overflows': 0,
            'decoding_errors': 0
        }

        # 实时字幕显示
        self.current_user_text = ""  # 当前用户说话内容
        self.current_ai_text = ""    # 当前AI回复内容
        self.conversation_history = []  # 对话历史
        self.subtitle_lock = threading.Lock()  # 字幕显示线程锁

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
                logger.warning(f"音频播放错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")

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

    def _detect_audio_format(self, audio_data: bytes) -> str:
        """检测音频格式"""
        if len(audio_data) < 4:
            return "pcm"

        # 检查 OGG 文件头 (4F 67 67 53)
        if audio_data[:4] == b'OggS':
            return "ogg"

        # 检查 WebM 文件头 (1A 45 DF A3)
        if audio_data[:4] == b'\x1A\x45\xDF\xA3':
            return "ogg"  # WebM 也用 OGG 解码器处理

        # 检查 Opus 在 OGG 中的特征
        if b'OpusHead' in audio_data[:64]:
            return "ogg"

        # 根据配置判断：如果没有配置 TTS，很可能是压缩格式
        if not hasattr(config, 'start_session_req') or 'tts' not in config.start_session_req:
            # 没有 TTS 配置时，尝试作为压缩音频处理
            return "ogg"

        # 默认为 PCM
        return "pcm"

    def _process_ogg_stream(self, ogg_page: bytes) -> bytes:
        """处理 OGG 流式数据 - 改进的增量解码版本"""
        # 将新的 OGG 页面添加到缓冲区
        self.ogg_buffer.extend(ogg_page)
        self.stats['ogg_pages_received'] += 1
        if len(self.ogg_buffer) % 5000 < len(ogg_page):  # 每5KB输出一次日志
            logger.debug(f"🔊 接收音频流: {len(self.ogg_buffer)}字节")

        # 尝试解码当前缓冲区的音频流
        try:
            audio = AudioSegment.from_file(io.BytesIO(bytes(self.ogg_buffer)), format="ogg")

            # 转换为目标格式
            audio = audio.set_frame_rate(self.output_config.sample_rate)
            audio = audio.set_channels(self.output_config.channels)
            audio = audio.set_sample_width(2)  # int16 = 2 bytes

            full_pcm_data = audio.raw_data

            if len(full_pcm_data) > 0:
                # 计算新增的PCM数据 - 使用更精确的方法
                if hasattr(self, 'last_pcm_size') and self.last_pcm_size > 0:
                    # 直接从上次的PCM数据长度开始截取
                    if len(full_pcm_data) > self.last_pcm_size:
                        new_pcm_data = full_pcm_data[self.last_pcm_size:]
                        # 更新已解码的PCM数据长度
                        self.last_pcm_size = len(full_pcm_data)

                        if len(new_pcm_data) > 0:
                            # 验证音频数据质量
                            validated_data = self._validate_pcm_data(new_pcm_data)
                            if len(validated_data) > 0:
                                self.stats['pcm_bytes_decoded'] += len(validated_data)
                                logger.debug(f"🎵 解码音频: {len(validated_data)}字节")
                                return validated_data
                    else:
                        # 没有新数据
                        return b''
                else:
                    # 第一次解码
                    self.last_pcm_size = len(full_pcm_data)
                    # 验证音频数据质量
                    validated_data = self._validate_pcm_data(full_pcm_data)
                    if len(validated_data) > 0:
                        self.stats['pcm_bytes_decoded'] += len(validated_data)
                        logger.debug(f"🎵 首次解码: {len(validated_data)}字节")
                        return validated_data

        except Exception as e:
            # 解码失败，记录统计
            self.stats['decoding_errors'] += 1
            # 检查是否是因为缓冲区数据不完整导致的失败
            if len(self.ogg_buffer) < 1000:  # 如果缓冲区很小，可能需要更多数据
                logger.debug("等待更多OGG数据进行解码")
            else:
                # 缓冲区较大但解码失败，可能是数据损坏
                logger.debug(f"OGG解码失败，缓冲区大小: {len(self.ogg_buffer)}")

        # 缓冲区管理：如果过大则保留最近的有效OGG数据
        max_buffer_size = 200000  # 200KB
        if len(self.ogg_buffer) > max_buffer_size:
            # 寻找最后一个完整的OGG页面边界
            last_ogg_start = self.ogg_buffer.rfind(b'OggS')
            if last_ogg_start > 0:
                # 从最后一个OGG页面开始保留
                self.ogg_buffer = self.ogg_buffer[last_ogg_start:]
                # 重置PCM计数，因为缓冲区被截断了
                self.last_pcm_size = 0
                logger.warning(f"OGG缓冲区过大，从最后页面保留 {len(self.ogg_buffer)} 字节")
            else:
                # 清空缓冲区重新开始
                self.ogg_buffer.clear()
                self.last_pcm_size = 0
                logger.warning("OGG缓冲区过大且无有效页面，重置缓冲区")

        # 返回空数据，等待更多OGG页面
        return b''

    def _validate_pcm_data(self, pcm_data: bytes) -> bytes:
        """验证和过滤PCM数据，防止爆炸嗞音"""
        if len(pcm_data) == 0:
            return b''

        # 检查数据长度是否为样本大小的倍数
        sample_size = 2  # int16 = 2 bytes
        if len(pcm_data) % sample_size != 0:
            # 截断到最近的样本边界
            pcm_data = pcm_data[:len(pcm_data) - (len(pcm_data) % sample_size)]

        if len(pcm_data) < sample_size:
            return b''

        # 转换为numpy数组进行分析
        try:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)

            # 检查是否有异常大的音量峰值（可能的爆炸音）
            max_amplitude = np.max(np.abs(audio_array))
            if max_amplitude > 25000:  # 接近int16最大值32767的阈值
                logger.warning(f"检测到异常音量峰值: {max_amplitude}，进行音量限制")
                # 进行音量限制
                audio_array = np.clip(audio_array, -25000, 25000)

            # 检查是否有大量的零值（可能的静音段）
            zero_ratio = np.count_nonzero(audio_array == 0) / len(audio_array)
            if zero_ratio > 0.95:  # 95%以上都是零值
                logger.debug("检测到大量静音数据，跳过播放")
                return b''

            # 返回处理后的数据
            return audio_array.tobytes()

        except Exception as e:
            logger.error(f"PCM数据验证失败: {e}")
            return pcm_data  # 验证失败时返回原始数据

    def _convert_ogg_to_pcm(self, ogg_data: bytes) -> bytes:
        """将 OGG/Opus 音频转换为 PCM"""
        return self._process_ogg_stream(ogg_data)

    def _debug_audio_data(self, audio_data: bytes) -> None:
        """调试音频数据格式"""
        # 简化调试输出，避免过多信息
        if len(audio_data) >= 4 and audio_data[:4] == b'OggS':
            logger.debug(f"检测到OGG页面: {len(audio_data)}字节")

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        if response == {}:
            return
        """处理服务器响应"""
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
                self._debug_audio_data(audio_data)

                # 检测音频格式
                audio_format = self._detect_audio_format(audio_data)

                # 如果是 OGG 格式，处理流式数据
                if audio_format == "ogg":
                    processed_audio = self._convert_ogg_to_pcm(audio_data)
                    if len(processed_audio) > 0:
                        # 将处理后的PCM数据加入播放队列
                        try:
                            self.audio_queue.put(processed_audio, timeout=0.1)
                        except queue.Full:
                            self.stats['audio_queue_overflows'] += 1
                            if self.stats['audio_queue_overflows'] % 10 == 1:  # 每10次溢出才输出一次警告
                                logger.warning(f"⚠️ 音频队列溢出 (第{self.stats['audio_queue_overflows']}次)")
                else:
                    # PCM格式直接播放
                    try:
                        self.audio_queue.put(audio_data, timeout=0.1)
                    except queue.Full:
                        self.stats['audio_queue_overflows'] += 1
                        if self.stats['audio_queue_overflows'] % 10 == 1:  # 每10次溢出才输出一次警告
                            logger.warning(f"⚠️ 音频队列溢出 (第{self.stats['audio_queue_overflows']}次)")

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
            logger.info(f'Event: {event}, Response: {response}\n')
            payload_msg = response.get('payload_msg', {})

            # 记录重要服务器事件，过滤调试噪音
            connection_events = [ServerEvent.CONNECTION_STARTED, ServerEvent.CONNECTION_FAILED, 
                               ServerEvent.CONNECTION_FINISHED, ServerEvent.SESSION_STARTED, 
                               ServerEvent.SESSION_FINISHED, ServerEvent.SESSION_FAILED]
            tts_asr_chat_events = [ServerEvent.TTS_SENTENCE_START, ServerEvent.TTS_SENTENCE_END, 
                                 ServerEvent.TTS_ENDED, ServerEvent.ASR_INFO, ServerEvent.ASR_RESPONSE, 
                                 ServerEvent.ASR_ENDED, ServerEvent.CHAT_RESPONSE, ServerEvent.CHAT_ENDED]
            
            if event in connection_events:
                logger.info(f"📡 服务器事件: {ServerEvent(event).name}({event})")
            elif event in tts_asr_chat_events:
                logger.debug(f"📡 服务器事件: {ServerEvent(event).name}({event})")
            else:
                logger.debug(f"📡 未知事件: {event}")

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
            elif event == ServerEvent.SESSION_FINISHED:
                logger.info("✅ 会话已结束")
            elif event == ServerEvent.SESSION_FAILED:
                error = payload_msg.get('error', 'Unknown error')
                logger.error(f"❌ 会话失败: {error}")
            elif event == ServerEvent.TTS_SENTENCE_START:
                tts_type = payload_msg.get('tts_type', 'default')
                text = payload_msg.get('text', '')
                logger.debug(f"🎵 TTS开始: {tts_type} - '{text[:30]}...'")
                # 清空上一轮的AI文本
                self.current_ai_text = ""
            elif event == ServerEvent.TTS_SENTENCE_END:
                logger.debug("🎵 TTS句子结束")
            elif event == ServerEvent.TTS_RESPONSE:
                # 这个事件的音频数据已经在 SERVER_ACK 中处理了
                logger.debug("🎵 收到TTS音频数据")
            elif event == ServerEvent.TTS_ENDED:
                logger.debug("🎵 TTS音频合成结束")
                # TTS完成，结束这轮对话
                # if self.current_ai_text: self._display_subtitle(ai_text=self.current_ai_text, is_final=True)
                self._finalize_conversation_turn()
            elif event == ServerEvent.ASR_INFO:
                # 清空音频队列，停止当前播放
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break
                # 清空OGG缓冲区
                self.ogg_buffer.clear()
                self.last_pcm_size = 0
                logger.debug("已清空音频缓冲区 (用户打断)")
                # print("\n🎤 正在识别...", end="", flush=True)  # 显示识别状态
                # 清空上一轮的用户文本
                self.current_user_text = ""
            elif event == ServerEvent.ASR_RESPONSE:
                results = payload_msg.get('results', [])
                if results and len(results) > 0:
                    text = results[0].get('text', '')
                    is_interim = results[0].get('is_interim', False)
                    if text and text.strip():
                        self.current_user_text = text
                        # self._display_subtitle(user_text=self.current_user_text, is_final=not is_interim)
                        logger.debug(f"👤 用户语音识别: '{text}' (临时: {is_interim})")
            elif event == ServerEvent.ASR_ENDED:
                pass
                # 确认用户文本最终结果
                # if self.current_user_text and self.current_user_text.strip():
                #     self._display_subtitle(user_text=self.current_user_text, is_final=True)
                # else:
                #     logger.debug("语音识别结束但内容为空")
            elif event == ServerEvent.CHAT_RESPONSE:
                content = payload_msg.get('content', '')
                if content and content.strip():
                    # AI实时文本回复 - 累积显示
                    self.current_ai_text += content
                    logger.debug(f"🤖 AI文本回复: '{content}' → 总计: '{self.current_ai_text[:50]}...'")
                    # self._display_subtitle(ai_text=self.current_ai_text, is_final=False)
            elif event == ServerEvent.CHAT_ENDED:
                logger.debug("🤖 AI文本回复结束")
                # 确认AI文本最终结果
                # if self.current_ai_text and self.current_ai_text.strip():
                #     self._display_subtitle(ai_text=self.current_ai_text, is_final=True)
            else:
                # 其他未知事件
                logger.debug(f"📡 未知事件: {event}")
        elif response['message_type'] == 'SERVER_ERROR':
            logger.error(f"服务器错误: {response['payload_msg']}")
            raise Exception("服务器错误")

    def _display_welcome_screen(self):
        """显示欢迎界面"""
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

    def _clear_line(self):
        """清除当前行"""
        print("\r" + " " * 120 + "\r", end="", flush=True)

    def _display_subtitle(self, user_text: str = None, ai_text: str = None, is_final: bool = False):
        """显示实时字幕"""
        with self.subtitle_lock:
            if user_text is not None:
                self.current_user_text = user_text
            if ai_text is not None:
                self.current_ai_text = ai_text

            # 清除当前行
            self._clear_line()

            # 显示字幕
            if self.current_user_text:
                if is_final:
                    print(f"💬 【用户】{self.current_user_text}")
                else:
                    # 限制显示长度，避免换行
                    display_text = self.current_user_text[:80] + "..." if len(self.current_user_text) > 80 else self.current_user_text
                    print(f"🎤 【用户】{display_text}", end="", flush=True)
            elif self.current_ai_text:
                if is_final:
                    print(f"🤖 【AI助手】{self.current_ai_text}")
                else:
                    # 限制显示长度，避免换行
                    display_text = self.current_ai_text[:80] + "..." if len(self.current_ai_text) > 80 else self.current_ai_text
                    print(f"🤖 【AI助手】{display_text}", end="", flush=True)

    def _finalize_conversation_turn(self):
        """完成一轮对话"""
        with self.subtitle_lock:
            if self.current_user_text or self.current_ai_text:
                # 保存到对话历史
                self.conversation_history.append({
                    'user': self.current_user_text,
                    'ai': self.current_ai_text,
                    'timestamp': time.time()
                })

                # 清空当前内容
                self.current_user_text = ""
                self.current_ai_text = ""

                # 显示简洁的分隔线
                print(f"\n{'─' * 50}")
                print(f"📊 第{len(self.conversation_history)}轮对话 | ⏰ {time.strftime('%H:%M:%S')}")
                print(f"{'─' * 50}")

    def log_stats(self):
        """输出统计信息"""
        logger.info("=== 音频处理统计 ===")
        logger.info(f"接收OGG页面数: {self.stats['ogg_pages_received']}")
        logger.info(f"解码PCM字节数: {self.stats['pcm_bytes_decoded']}")
        logger.info(f"队列溢出次数: {self.stats['audio_queue_overflows']}")
        logger.info(f"解码错误次数: {self.stats['decoding_errors']}")
        logger.info(f"对话轮次: {len(self.conversation_history)}")
        logger.info("==================")

    def _keyboard_signal(self, sig, frame):
        logger.info("👋 收到退出信号，正在关闭...")
        self.log_stats()
        self.is_recording = False
        self.is_playing = False
        self.is_running = False

    async def receive_loop(self):
        try:
            while True:
                response = await self.client.receive_server_response()
                self.handle_server_response(response)
                if 'event' in response and (response['event'] == ServerEvent.SESSION_FINISHED or response['event'] == ServerEvent.SESSION_FAILED):
                    logger.info(f"接收到会话结束事件: {ServerEvent(response['event']).name}({response['event']})")
                    self.is_session_finished = True
                    break
        except asyncio.CancelledError:
            logger.info("接收任务已取消")
        except Exception as e:
            logger.error(f"接收消息错误: {e}")

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

    async def start(self) -> None:
        """启动对话会话"""
        try:
            await self.client.connect()
            asyncio.create_task(self.process_microphone_input())
            asyncio.create_task(self.receive_loop())

            while self.is_running:
                await asyncio.sleep(0.1)

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
            self.audio_device.cleanup()

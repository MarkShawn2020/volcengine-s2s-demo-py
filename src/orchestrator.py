import asyncio
import signal
import threading
import time
import uuid
from typing import Dict, Any

import src.io.webrtc.config
import src.io.websocket.config
import src.volcengine.config
from src import config
from src.client import RealtimeDialogClient
from src.io.io_base import IOBase
from src.utils.audio.audio_converter import OggToPcmConverter
from src.utils.audio.detect_audio_format import detect_audio_format
from src.utils.logger import logger
from src.volcengine.protocol import ServerEvent


class Orchestrator:
    """对话会话管理类 - 重构版本"""

    def __init__(self, ws_config: Dict[str, Any], io_mode: str = None):
        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

        # WebSocket客户端
        self.client = RealtimeDialogClient(config=ws_config, session_id=self.session_id)

        # 确定IO模式
        if io_mode is None:
            io_mode = config.IO_MODE
        self.io_mode = io_mode

        # 初始化音频IO
        self.audio_io = self._create_audio_io(io_mode)
        self.audio_io.set_audio_input_callback(self._handle_audio_input)

        # 会话控制
        self.is_running = True
        self.is_session_finished = False

        # 信号处理
        signal.signal(signal.SIGINT, self._keyboard_signal)

        # 音频转换器
        output_config = src.volcengine.config.ogg_output_audio_config
        tts_config = src.volcengine.config.start_session_req.get("tts")
        if tts_config:
            tts_audio_config = tts_config.get("audio_config")
            if tts_audio_config:
                output_config = tts_audio_config

        self.ogg_converter = OggToPcmConverter(sample_rate=output_config['sample_rate'],
                                               channels=output_config['channels'])

        # 实时字幕显示
        self.current_user_text = ""
        self.current_ai_text = ""
        self.conversation_history = []
        self.subtitle_lock = threading.Lock()
        self.is_user_speaking = False
        self.is_ai_responding = False
        self.last_displayed_ai_text = ""

        # 重连控制
        self._reconnecting = False
        self._reconnect_lock = None

    def _create_audio_io(self, io_mode: str) -> IOBase:
        """创建音频IO实例"""
        if io_mode == "webrtc":
            from src.io.webrtc.webrtc_io import WebRTCIO
            return WebRTCIO(src.io.webrtc.config.webrtc_config)
        elif io_mode == "websocket":
            from src.io.websocket.websocket_io import WebsocketIO
            return WebsocketIO(src.io.websocket.config.socket_config)
        else:  # system
            from src.io.system.system_io import SystemIO
            return SystemIO({})

    def _handle_audio_input(self, audio_data: bytes) -> None:
        """处理音频输入数据"""
        if not self.is_running:
            return

        # 创建异步任务发送音频数据
        asyncio.create_task(self.client.task_request(audio_data))

    def _is_websocket_connected(self) -> bool:
        """检查WebSocket连接状态"""
        if not self.client or not self.client.ws:
            return False

        try:
            import websockets
            if hasattr(self.client.ws, 'state'):
                return self.client.ws.state == websockets.protocol.State.OPEN
            elif hasattr(self.client.ws, 'closed'):
                return not self.client.ws.closed
            else:
                return True
        except Exception as e:
            logger.debug(f"检查WebSocket状态时出错: {e}")
            return False

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        """处理服务器响应"""
        if response == {}:
            return

        if response['message_type'] == 'SERVER_ACK':
            event = response.get('event', 0)

            if isinstance(response.get('payload_msg'), bytes):
                audio_data = response['payload_msg']

                if len(audio_data) == 0:
                    return

                if event == ServerEvent.TTS_RESPONSE:
                    logger.debug(f"🎵 收到TTSResponse音频数据: {len(audio_data)}字节")

                audio_format = detect_audio_format(audio_data)

                if audio_format == "ogg":
                    audio_data = self.ogg_converter.convert(audio_data)

                # 通过音频IO发送输出
                format_type = "ogg" if audio_format == "ogg" else "pcm"
                asyncio.create_task(self.audio_io.send_audio_output(audio_data, format_type))

            elif isinstance(response.get('payload_msg'), dict):
                ai_content = response.get('payload_msg', {}).get('content', '')
                if ai_content:
                    logger.debug(f"🤖 AI文本回复(SERVER_ACK): '{ai_content}'")
                    self.current_ai_text += ai_content
                    self._display_subtitle(ai_text=self.current_ai_text, is_final=False)

        elif response['message_type'] == 'SERVER_FULL_RESPONSE':
            event = response.get('event', 'unknown')
            if logger.level <= 10:
                logger.debug(f'Event: {event}, Response: {response}\n')
            payload_msg = response.get('payload_msg', {})

            connection_events = [ServerEvent.CONNECTION_STARTED, ServerEvent.CONNECTION_FAILED,
                                 ServerEvent.CONNECTION_FINISHED, ServerEvent.SESSION_STARTED,
                                 ServerEvent.SESSION_FINISHED, ServerEvent.SESSION_FAILED]

            if event in connection_events:
                logger.info(f"📡 {ServerEvent(event).name}")
            else:
                event_name = ServerEvent(event).name if event in ServerEvent._value2member_map_ else f'Unknown({event})'
                logger.debug(f"📡 {event_name}")

            # 处理各种服务器事件
            if event == ServerEvent.CONNECTION_STARTED:
                logger.info("🔗 连接已建立")
            elif event == ServerEvent.SESSION_STARTED:
                dialog_id = payload_msg.get('dialog_id', '')
                logger.info(f"🚀 会话已启动 (Dialog ID: {dialog_id[:8]}...)")
                asyncio.create_task(self.client.say_hello("你好，我是你的语音助手，有什么可以帮助你的吗？"))
            elif event == ServerEvent.SESSION_FINISHED:
                logger.info("✅ 会话已结束")
            elif event == ServerEvent.TTS_ENDED:
                logger.debug("🎵 TTS音频合成结束")
                self._finalize_conversation_turn()
            elif event == ServerEvent.ASR_INFO:
                self.ogg_converter.reset()
                logger.debug("已清空音频缓冲区 (用户打断)")
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
                    if not self.is_ai_responding:
                        self.is_ai_responding = True
                        self.current_ai_text = ""
                        self.last_displayed_ai_text = ""
                    self.current_ai_text += content
                    if len(self.current_ai_text) - len(self.last_displayed_ai_text) >= 5 or content.endswith(('。', '！',
                                                                                                              '？', '，',
                                                                                                              '、')):
                        self._update_console_display()
                    logger.debug(f"🤖 AI文本回复: '{content}' → 总计: '{self.current_ai_text[:50]}...'")
            elif event == ServerEvent.CHAT_ENDED:
                logger.debug("🤖 AI文本回复结束")
                self.is_ai_responding = False

        elif response['message_type'] == 'SERVER_ERROR':
            logger.error(f"服务器错误: {response['payload_msg']}")
            raise Exception("服务器错误")

    def _display_subtitle(self, ai_text: str = "", is_final: bool = False):
        """显示字幕"""
        pass  # 简化实现

    def _clear_current_line(self):
        """清除当前行"""
        print("\r\033[K", end="", flush=True)

    def _update_console_display(self, final_user: bool = False, final_ai: bool = False):
        """更新控制台显示"""
        with self.subtitle_lock:
            if final_user and self.current_user_text:
                self._clear_current_line()
                print(f"👤 用户: {self.current_user_text}")
                return
            elif final_ai and self.current_ai_text:
                self._clear_current_line()
                print(f"🤖 AI: {self.current_ai_text}")
                self.last_displayed_ai_text = self.current_ai_text
                return

            if self.is_user_speaking and self.current_user_text:
                self._clear_current_line()
                display_text = self.current_user_text[
                               :150] + "..." if len(self.current_user_text) > 150 else self.current_user_text
                print(f"👤 用户: {display_text}", end="", flush=True)
            elif self.is_ai_responding and self.current_ai_text:
                if self.current_ai_text != self.last_displayed_ai_text:
                    self._clear_current_line()
                    display_text = self.current_ai_text[
                                   :150] + "..." if len(self.current_ai_text) > 150 else self.current_ai_text
                    print(f"🤖 AI: {display_text}", end="", flush=True)
                    self.last_displayed_ai_text = self.current_ai_text
            elif not self.is_user_speaking and not self.is_ai_responding:
                self._clear_current_line()
                print("🎙️ 请说话...", end="", flush=True)

    def _finalize_conversation_turn(self):
        """完成一轮对话"""
        with self.subtitle_lock:
            if self.current_user_text or self.current_ai_text:
                if self.current_ai_text and self.current_ai_text != self.last_displayed_ai_text:
                    self._clear_current_line()
                    print(f"🤖 AI: {self.current_ai_text}")

                self.conversation_history.append({
                    'user': self.current_user_text,
                    'ai': self.current_ai_text,
                    'timestamp': time.time()
                })

                self.current_user_text = ""
                self.current_ai_text = ""
                self.last_displayed_ai_text = ""
                self.is_user_speaking = False
                self.is_ai_responding = False

                print(f"\n{'─' * 50}")
                print(f"📊 第{len(self.conversation_history)}轮对话 | ⏰ {time.strftime('%H:%M:%S')}")
                print(f"{'─' * 50}\n")
                print("🎙️ 请说话...", end="", flush=True)

    def _keyboard_signal(self, sig, frame):
        logger.info("👋 收到退出信号，正在优雅关闭...")
        self.is_running = False

        # 立即停止音频IO，避免继续产生错误
        if self.audio_io and hasattr(self.audio_io, 'is_running'):
            self.audio_io.is_running = False
            
        # 如果是WebRTC模式，立即停止WebRTC管理器
        if self.io_mode == "webrtc" and self.audio_io and hasattr(self.audio_io, 'webrtc_manager'):
            if self.audio_io.webrtc_manager:
                self.audio_io.webrtc_manager.is_running = False

        # 创建一个新的事件循环来处理清理操作
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                asyncio.create_task(self._graceful_shutdown())
            else:
                # 如果事件循环未运行，直接运行
                loop.run_until_complete(self._graceful_shutdown())
        except Exception as e:
            logger.error(f"优雅关闭过程中出现错误: {e}")
            import os
            os._exit(1)

    async def _graceful_shutdown(self):
        """优雅关闭所有资源"""
        try:
            logger.info("开始优雅关闭...")
            
            # 停止音频IO
            if self.audio_io:
                try:
                    await self.audio_io.stop()
                    self.audio_io.cleanup()
                except Exception as e:
                    logger.warning(f"停止音频IO错误: {e}")

            # 优雅关闭WebSocket连接
            if self.client:
                try:
                    await self.client.graceful_shutdown()
                except Exception as e:
                    logger.warning(f"优雅关闭WebSocket错误: {e}")

            logger.info("✅ 优雅关闭完成")
        except Exception as e:
            logger.error(f"优雅关闭过程中出现错误: {e}")
        finally:
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

    async def start(self) -> None:
        """启动对话会话"""
        try:
            # 初始化重连锁
            self._reconnect_lock = asyncio.Lock()

            # 建立WebSocket连接
            await self.client.connect()

            # 启动接收循环
            receive_task = asyncio.create_task(self.receive_loop())

            # 发送连接和会话初始化请求
            await self.client.start_connection()
            await self.client.start_session()

            await asyncio.sleep(0.1)

            # 启动音频IO
            asyncio.create_task(self.audio_io.start())

            # 保持主循环运行，监控连接状态
            while self.is_running:
                await asyncio.sleep(0.5)

            # 正常结束时也使用优雅关闭
            await self.client.graceful_shutdown()
            logger.info(f"对话请求日志ID: {self.client.logid}")
        except Exception as e:
            logger.error(f"会话错误: {e}")
        finally:
            # 确保资源被清理
            if self.audio_io:
                try:
                    await self.audio_io.stop()
                    self.audio_io.cleanup()
                except Exception as e:
                    logger.warning(f"清理音频IO资源错误: {e}")
            
            if self.client:
                try:
                    await self.client.close()
                except Exception as e:
                    logger.warning(f"最终关闭WebSocket错误: {e}")

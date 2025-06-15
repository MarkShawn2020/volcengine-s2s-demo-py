import asyncio
import json
import logging
import signal
import threading
import time
import uuid
from typing import Dict, Any

from src.config import (
    webrtc_config, websocket_config, ADAPTER_MODE, VOLCENGINE_AUDIO_TYPE, VOLCENGINE_WELCOME,
    )
from src.io_adapters.base import AdapterBase
from src.io_adapters.type import AdapterMode
from src.volcengine.client import VoicengineClient
from src.volcengine.config import ws_connect_config
from src.volcengine.protocol import ServerEvent

logger = logging.getLogger(__name__)


class Orchestrator:
    """对话会话管理类 - 重构版本"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

        # WebSocket --> voicengine 客户端
        self.client = VoicengineClient(config=ws_connect_config, session_id=self.session_id)

        # 初始化音频IO
        self.audio_adapter = self._create_audio_adapter(ADAPTER_MODE)
        self.audio_adapter.set_audio_input_callback(self._handle_audio_input)
        self.audio_adapter.set_prepared_callback(self._on_audio_io_prepared)

        # 会话控制
        self.is_running = True
        self.is_session_finished = False

        # 信号处理
        signal.signal(signal.SIGINT, self._keyboard_signal)

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

    def _create_audio_adapter(self, adapter_mode: AdapterMode) -> AdapterBase:
        """创建音频IO实例"""
        if adapter_mode == AdapterMode.webrtc:
            from src.io_adapters.webrtc.adapter import WebRTCAdapter
            return WebRTCAdapter(webrtc_config)
        elif adapter_mode == AdapterMode.websocket:
            from src.io_adapters.websocket.adapter import WebsocketAdapter
            return WebsocketAdapter(websocket_config)
        elif adapter_mode == AdapterMode.system:
            from src.io_adapters.system.adapter import SystemAdapter
            return SystemAdapter()
        else:
            raise Exception(f"invalid adapter mode: {adapter_mode}")

    def _handle_audio_input(self, audio_data: bytes) -> None:
        """处理音频输入数据"""
        if not self.is_running:
            return

        # 检查WebSocket连接状态
        if not self._is_websocket_connected():
            logger.debug("WebSocket连接不可用，跳过音频发送")
            return

        # logger.info(f"🎤 Orchestrator接收到音频数据: {len(audio_data)} bytes")

        # 创建异步任务发送音频数据
        task = asyncio.create_task(self.client.task_request(audio_data))
        task.add_done_callback(self._handle_task_request_exception)

    def _on_audio_io_prepared(self) -> None:
        """音频IO准备就绪回调"""
        logger.info("🎯 音频IO已准备就绪，发送SayHello")
        task = asyncio.create_task(self.client.say_hello(VOLCENGINE_WELCOME))
        task.add_done_callback(self._handle_general_task_exception)

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

    def _handle_task_request_exception(self, task) -> None:
        """处理task_request异步任务的异常"""
        try:
            task.result()
        except Exception as e:
            logger.warning(f"音频发送任务失败: {e}")
            # WebSocket连接已关闭，停止运行
            if "received 1000" in str(e) or "ConnectionClosed" in str(e):
                logger.info("检测到WebSocket连接已关闭，停止音频处理")
                self.is_running = False

    def _handle_general_task_exception(self, task) -> None:
        """处理一般异步任务的异常"""
        try:
            task.result()
        except Exception as e:
            logger.warning(f"异步任务失败: {e}")

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        """处理服务器响应"""
        if response == {}:
            return

        event = response.get('event', 'unknown')
        payload_msg = response.get('payload_msg')
        logger.debug(
            f"🏠 <-- 📡 [{ServerEvent(event).name}] Payload(type={type(payload_msg)}, size="
            f"{len(payload_msg)})"
            )
        if isinstance(payload_msg, dict):
            logger.debug(json.dumps(payload_msg, indent=2, ensure_ascii=False))

        if response['message_type'] == 'SERVER_ACK':

            if isinstance(payload_msg, bytes):
                if len(payload_msg) == 0: return

                # 通过音频IO发送输出
                task = asyncio.create_task(self.audio_adapter.send_audio_output(payload_msg, VOLCENGINE_AUDIO_TYPE))
                task.add_done_callback(self._handle_general_task_exception)

            elif isinstance(payload_msg, dict):
                ai_content = payload_msg.get('content', '')
                if ai_content:
                    logger.debug(f"🤖 AI文本回复(SERVER_ACK): '{ai_content}'")
                    self.current_ai_text += ai_content
                    self._display_subtitle(ai_text=self.current_ai_text, is_final=False)

        elif response['message_type'] == 'SERVER_FULL_RESPONSE':

            # 处理各种服务器事件
            if event == ServerEvent.CONNECTION_STARTED:
                logger.info("🔗 连接已建立")
            elif event == ServerEvent.SESSION_STARTED:
                dialog_id = payload_msg.get('dialog_id', '')
                logger.info(f"🚀 会话已启动 (Dialog ID: {dialog_id[:8]}...)")  # SayHello将在音频IO准备就绪时发送
            elif event == ServerEvent.SESSION_FINISHED:
                logger.info("✅ 会话已结束")
            elif event == ServerEvent.TTS_ENDED:
                logger.debug("🎵 TTS音频合成结束")
                self._finalize_conversation_turn()
            elif event == ServerEvent.ASR_INFO:
                logger.info("🎤 ASR_INFO: 已清空音频缓冲区 (用户打断)")
                self.is_user_speaking = True
                self.is_ai_responding = False
                self.current_user_text = ""
                self._update_console_display()
            elif event == ServerEvent.ASR_RESPONSE:
                logger.info(f"🎤 ASR_RESPONSE: 收到语音识别响应")
                results = payload_msg.get('results', [])
                if results and len(results) > 0:
                    text = results[0].get('text', '')
                    is_interim = results[0].get('is_interim', False)
                    logger.info(f"👤 用户语音识别: '{text}' (临时: {is_interim})")
                    if text and text.strip():
                        self.current_user_text = text
                        self._update_console_display()
                else:
                    logger.warning("⚠️ ASR_RESPONSE中无results或results为空")
            elif event == ServerEvent.ASR_ENDED:
                logger.info("🎤 ASR_ENDED: 语音识别结束")
                self.is_user_speaking = False
                if self.current_user_text and self.current_user_text.strip():
                    self._update_console_display(final_user=True)
            elif event == ServerEvent.CHAT_RESPONSE:
                content = payload_msg.get('content', '')
                if content and content.strip():
                    if not self.is_ai_responding:
                        self.is_ai_responding = True
                        self.current_ai_text = ""
                        self.last_displayed_ai_text = ""
                    self.current_ai_text += content
                    if len(self.current_ai_text) - len(self.last_displayed_ai_text) >= 5 or content.endswith(
                            ('。', '！', '？', '，', '、')
                            ):
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
                display_text = self.current_user_text[:150] + "..." if len(
                    self.current_user_text
                    ) > 150 else self.current_user_text
                print(f"👤 用户: {display_text}", end="", flush=True)
            elif self.is_ai_responding and self.current_ai_text:
                if self.current_ai_text != self.last_displayed_ai_text:
                    self._clear_current_line()
                    display_text = self.current_ai_text[:150] + "..." if len(
                        self.current_ai_text
                        ) > 150 else self.current_ai_text
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

                self.conversation_history.append(
                    {
                        'user': self.current_user_text,
                        'ai': self.current_ai_text,
                        'timestamp': time.time()
                        }
                    )

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
        if self.audio_adapter and hasattr(self.audio_adapter, 'is_running'):
            self.audio_adapter.is_running = False

        # 如果是WebRTC模式，立即停止WebRTC管理器
        if ADAPTER_MODE == AdapterMode.webrtc and self.audio_adapter and hasattr(self.audio_adapter, 'webrtc_manager'):
            if self.audio_adapter.webrtc_manager:
                self.audio_adapter.webrtc_manager.is_running = False

    async def _graceful_shutdown(self):
        """优雅关闭所有资源"""
        # 防止重复执行
        if hasattr(self, '_shutdown_started') and self._shutdown_started:
            return
        self._shutdown_started = True
        
        try:
            logger.info("开始优雅关闭...")

            # 停止音频IO
            if self.audio_adapter:
                try:
                    await self.audio_adapter.stop()
                    self.audio_adapter.cleanup()
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
                # 检查连接状态
                if not self._is_websocket_connected():
                    logger.info("WebSocket连接已关闭，退出接收循环")
                    self.is_running = False
                    break

                response = await self.client.receive_server_response()
                # logger.debug(f"📡 接收到原始响应，开始处理...")
                self.handle_server_response(response)
                if 'event' in response and (response['event'] == ServerEvent.SESSION_FINISHED or response[
                    'event'] == ServerEvent.SESSION_FAILED):
                    logger.info(f"接收到会话结束事件: {ServerEvent(response['event']).name}({response['event']})")
                    self.is_session_finished = True
                    break
        except asyncio.CancelledError:
            logger.info("接收任务已取消")
        except Exception as e:
            logger.warning(f"接收消息主循环异常： {e}")
            # 检查是否为WebSocket正常关闭
            if "received 1000" in str(e) or "ConnectionClosed" in str(e) or "connection is closed" in str(e).lower():
                logger.warning("WebSocket连接已正常关闭，退出接收循环")
                self.is_running = False
            else:
                logger.error(f"接收消息错误: {e}")
                self.is_running = False

    async def start(self) -> None:
        """启动对话会话"""
        try:
            # 初始化重连锁
            self._reconnect_lock = asyncio.Lock()

            # 建立WebSocket连接
            await self.client.connect()

            # 启动接收循环
            asyncio.create_task(self.receive_loop())

            # 发送连接和会话初始化请求
            await self.client.start_connection()
            await self.client.start_session()

            await asyncio.sleep(0.1)

            # 启动音频IO
            asyncio.create_task(self.audio_adapter.start())

            # 保持主循环运行，监控连接状态
            while self.is_running:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"会话错误: {e}")
        finally:
            # 正常结束时也使用优雅关闭
            await self._graceful_shutdown()
            if self.client:
                logger.info(f"对话请求日志ID: {self.client.logid}")

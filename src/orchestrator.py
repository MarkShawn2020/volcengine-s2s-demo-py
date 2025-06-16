import asyncio
import json
import logging
import signal
import threading
import time

from src.config import (ADAPTER_MODE, VOLCENGINE_WELCOME, )
from src.io_adapters.base import AdapterBase
from src.io_adapters.type import AdapterMode
from src.volcengine.client import VoicengineClient
from src.volcengine.config import ws_connect_config
from src.volcengine.protocol import ServerEvent

logger = logging.getLogger(__name__)


class Orchestrator:

    def __init__(self):
        # WebSocket --> voicengine 客户端
        self.volcengine_client = VoicengineClient(config=ws_connect_config)

        # 初始化音频IO
        self.audio_adapter = self._create_audio_adapter(ADAPTER_MODE)
        self.audio_adapter.set_on_prepared(self._request_say_hello)

        # 会话控制
        self.is_running = False
        self.is_session_finished = False
        self.is_stopping = False
        self._should_send_hello = False

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

    async def start(self) -> None:
        """启动对话会话"""
        if self.is_running: return
        self.is_running = True
        logger.info("starting")
        try:

            logger.info("starting volcengine client")
            await self.volcengine_client.start()
            await self.volcengine_client.request_start_connection()
            await self.volcengine_client.request_start_session()
            logger.info("started volcengine client")

            await self.audio_adapter.start()

            async with asyncio.TaskGroup() as tg:
                logger.info("starting tasks")
                # 根据官方代码经验
                # receiver 里不要加任何的await，因为recv本来就在等
                # sender里要加一点await，否则cpu会过高
                tg.create_task(self.thread_server2client())
                tg.create_task(self.thread_client2server())
                logger.info("started tasks")
        except Exception as e:
            logger.error(f"failed to start, reason: {e}")
        finally:
            await self.stop()

    async def stop(self):
        if self.is_stopping: return
        self.is_stopping = True

        try:
            logger.info("stopping")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.volcengine_client.stop())
                tg.create_task(self.audio_adapter.stop())
            logger.info("stopped")
        except Exception as e:
            logger.error(f"failed to stop, reason: {e}")

    async def thread_server2client(self):
        seq = 0
        try:
            while self.is_running and self.volcengine_client.is_active:
                seq += 1
                logger.debug(f"pulling ({seq})")
                response = await self.volcengine_client.on_response()
                if response is None:
                    # 超时或连接问题，继续循环检查is_running状态
                    continue
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
                        # 【重要】当中控收到了AI音频，交给代理器处理
                        await self.audio_adapter.on_get_next_server_chunk(payload_msg)

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
                        logger.info(f"🚀 会话已启动 (Dialog ID: {dialog_id[:8]}...)")

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

        except Exception as e:
            logger.warning(f"failed to pull, reason: {e}")

    async def thread_client2server(self):
        seq = 0
        try:
            while self.is_running and self.audio_adapter.is_running:
                seq += 1
                logger.debug(f"pushing ({seq})")
                chunk = await self.audio_adapter.get_next_client_chunk()
                if chunk:
                    await self.volcengine_client.push_audio(chunk)
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.warning(f"failed to push, reason: {e}")

    async def _request_say_hello(self):
        await self.volcengine_client.request_say_hello(VOLCENGINE_WELCOME)

    def _create_audio_adapter(self, adapter_mode: AdapterMode) -> AdapterBase:
        """创建音频IO实例"""

        def handle_audio_input(audio_data: bytes) -> None:
            """处理音频输入数据"""
            if not self.is_running or not self.volcengine_client.is_active:
                return
            asyncio.create_task(self.volcengine_client.push_audio(audio_data))

        def on_adapter_prepared() -> None:
            """音频IO准备就绪回调"""
            logger.info("🎯 WebRTC连接已建立，发送SayHello")
            # 设置标志，在主事件循环中发送say-hello
            self._should_send_hello = True

        if adapter_mode == AdapterMode.system:
            from src.io_adapters.system.adapter import SystemAdapter
            return SystemAdapter()

        if adapter_mode == AdapterMode.webrtc:
            from src.io_adapters.webrtc.adapter import WebRTCAdapter
            from src.config import webrtc_config
            adapter = WebRTCAdapter(webrtc_config)
            # 设置WebRTC准备就绪回调
            adapter._on_prepared = on_adapter_prepared
            return adapter

        raise Exception(f"invalid adapter mode: {adapter_mode}")

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
        # 确保音频适配器也停止
        if hasattr(self, 'audio_adapter') and self.audio_adapter:
            self.audio_adapter.is_running = False
            # 如果是 WebRTC 适配器，需要停止 WebRTC 管理器
            if hasattr(self.audio_adapter, '_webrtc_manager') and self.audio_adapter._webrtc_manager:
                self.audio_adapter._webrtc_manager.is_running = False
                logger.info("已设置WebRTC停止标志")

        logger.info("信号处理完成")

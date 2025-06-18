import asyncio
import json
import logging
import queue
import threading
from typing import AsyncGenerator, Optional

import websockets

from src.adapters.base import AudioAdapter, BrowserConnectionConfig
from src.adapters.proxy_server import ProxyServer
from src.adapters.type import AdapterType

logger = logging.getLogger(__name__)


class BrowserAudioAdapter(AudioAdapter):
    """浏览器音频适配器 - 内嵌代理服务器"""

    def __init__(self, config: BrowserConnectionConfig):
        super().__init__(config.params)
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self._receiver_task = None
        self.proxy_server = None
        self.server_task = None
        self._send_queue = None
        self._play_queue = None

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.BROWSER

    async def connect(self) -> bool:
        """启动内嵌代理服务器"""
        try:
            proxy_url = self.config.get("proxy_url")

            # 启动内嵌代理服务器
            self.proxy_server = ProxyServer(proxy_url)
            self.server_task = asyncio.create_task(self.proxy_server.start())

            # 等待服务器启动
            await asyncio.sleep(0.5)

            # 连接到代理服务器
            self.ws = await websockets.connect(proxy_url)
            return True

        except Exception as e:
            logger.error(f"浏览器适配器连接失败: {e}")
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()
            self.ws = None

        if self.proxy_server:
            await self.proxy_server.stop()

        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass

        self.is_connected = False
        logger.info("浏览器适配器已断开连接")

    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据"""
        if not self.is_connected or not self.ws:
            return False

        try:
            message = {
                "type": "audio",
                "data": audio_data.hex()  # 转换为十六进制字符串
                }
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
            return False

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收音频数据流"""
        while self.is_connected:
            try:
                audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if not self.is_connected or not self.ws:
            return False

        try:
            message = {
                "type": "text",
                "content": text
                }
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def _receive_messages(self):
        """接收消息的后台任务"""
        while self.is_connected and self.ws:
            try:
                message = await self.ws.recv()

                # 检查消息类型：二进制数据（音频）或文本数据（JSON）
                if isinstance(message, bytes):
                    # 二进制音频数据，直接放入队列
                    await self.audio_queue.put(message)
                    logger.debug(f"收到二进制音频数据: {len(message)}字节")
                else:
                    # 文本消息，解析为JSON
                    try:
                        data = json.loads(message)
                        if data.get("type") == "audio":
                            # 将十六进制字符串转换回字节
                            audio_data = bytes.fromhex(data.get("data", ""))
                            await self.audio_queue.put(audio_data)
                        elif data.get("type") == "event":
                            logger.info(f"收到事件: {data}")
                    except json.JSONDecodeError:
                        logger.warning(f"收到无效JSON消息: {message}")

            except Exception as e:
                logger.error(f"接收消息失败: {e}")
                break

    async def setup_audio_devices(self, p, stop_event: threading.Event) -> tuple[
        Optional[threading.Thread], Optional[threading.Thread]]:
        """Browser模式：音频通过WebSocket传输，跳过系统音频设备选择"""
        logger.info("Browser模式：音频通过WebSocket传输，跳过系统音频设备选择")
        return None, None

    async def run_sender_task(self, send_queue: queue.Queue, stop_event: threading.Event) -> None:
        """Browser发送任务 - 等待浏览器音频数据"""
        logger.info("Browser发送任务启动，等待浏览器音频数据")

        # Browser模式下，适配器内部会处理音频转发
        # 这里主要是保持任务运行，让控制消息和状态监控正常工作
        try:
            while not stop_event.is_set() and self.is_connected:
                await asyncio.sleep(1)  # 可以在这里添加状态检查和日志

        except Exception as e:
            logger.error(f"Browser发送任务异常: {e}")

        logger.info("Browser发送任务结束")

    async def run_receiver_task(self, play_queue: queue.Queue, stop_event: threading.Event) -> None:
        """Browser接收任务"""
        logger.info("Browser接收任务启动")
        received_count = 0

        try:
            async for audio_data in self.receive_audio():
                logger.debug(f"收到音频数据: {len(audio_data)} bytes")
                if stop_event.is_set():
                    break

                received_count += 1
                logger.debug(f"收到音频数据 #{received_count}，大小: {len(audio_data)} bytes")

                # Browser模式下，音频数据通过WebSocket直接转发给浏览器
                # 不需要放入播放队列，因为没有本地播放设备
                if play_queue is not None:
                    try:
                        play_queue.put_nowait(
                            {
                                "payload_msg": audio_data
                                }
                            )
                    except queue.Full:
                        # 播放队列满时，移除最老的数据再放入新数据
                        try:
                            play_queue.get_nowait()
                            play_queue.put_nowait(
                                {
                                    "payload_msg": audio_data
                                    }
                                )
                        except queue.Empty:
                            pass

        except Exception as e:
            logger.error(f"Browser接收任务异常: {e}")

        if received_count > 0:
            logger.info(f"Browser总共接收 {received_count} 个音频数据")

import asyncio
import json
import logging
from typing import AsyncGenerator

import websockets

from src.adapters.base import AudioAdapter, AdapterType, BrowserConnectionConfig
from src.adapters.proxy_server import ProxyServer

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

            # 发送认证信息
            auth_message = {
                "type": "auth",
                "app_id": self.config.get("app_id"),
                "access_token": self.config.get("access_token")
                }
            await self.ws.send(json.dumps(auth_message))

            # 等待认证响应
            response = await self.ws.recv()
            auth_response = json.loads(response)

            if auth_response.get("type") == "auth_success":
                self.is_connected = True
                self.session_id = auth_response.get("session_id")
                # 启动接收任务
                self._receiver_task = asyncio.create_task(self._receive_messages())
                logger.info(f"浏览器适配器连接成功，会话ID: {self.session_id[:8]}...")
                logger.info(f"代理服务器运行在 {proxy_url}")
                return True
            else:
                logger.error(f"认证失败: {auth_response}")
                return False

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

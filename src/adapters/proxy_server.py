import asyncio
import logging
import uuid
from typing import Dict
from urllib.parse import urlparse

import websockets

from src.adapters.proxy_client import ProxyClient

logger = logging.getLogger(__name__)


class ProxyServer:
    """代理服务器 - 解决浏览器WebSocket自定义header限制"""

    def __init__(self, websocket_uri: str = "ws://localhost:8765"):
        parsed_url = urlparse(websocket_uri)
        self.host = parsed_url.hostname or "localhost"
        self.port = parsed_url.port or (443 if parsed_url.scheme == "wss" else 8765)
        self.clients: Dict[str, 'ProxyClient'] = {}
        self.server = None

    async def start(self):
        """启动代理服务器"""
        logger.info(f"启动代理服务器 ws://{self.host}:{self.port}")

        # 兼容新版本websockets库的处理方法
        async def handler(websocket):
            return await self.handle_client(websocket)

        self.server = await websockets.serve(handler, self.host, self.port)
        try:
            await self.server.wait_closed()
        except asyncio.CancelledError:
            logger.info("代理服务器已被取消")
            await self.stop()

    async def stop(self):
        """停止代理服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("代理服务器已停止")

    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = str(uuid.uuid4())
        logger.info(f"新客户端连接: {client_id}")

        proxy_client = ProxyClient(client_id, websocket)
        await proxy_client._send_welcome_to_volcengine()
        # 传递配置给ProxyClient
        if hasattr(self, 'config'):
            proxy_client.config = self.config
        self.clients[client_id] = proxy_client

        try:
            await proxy_client.handle()
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {client_id} 正常断开连接")
        except Exception as e:
            logger.error(f"客户端 {client_id} 处理异常: {e}")
        finally:
            # 清理资源
            await proxy_client.cleanup()
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"客户端 {client_id} 连接关闭")

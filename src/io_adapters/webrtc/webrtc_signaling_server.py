import json
from typing import Dict, Optional, Callable, Any

import websockets
from websockets.legacy.server import WebSocketServerProtocol

from src.utils.logger import logger


class WebRTCSignalingServer:
    """WebRTC信令服务器"""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.server = None

        # 回调函数
        self.on_offer_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_answer_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_ice_candidate_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_client_connected_callback: Optional[Callable[[str], None]] = None
        self.on_client_disconnected_callback: Optional[Callable[[str], None]] = None

    async def start(self):
        """启动信令服务器"""
        logger.info(f"🚀 启动WebRTC信令服务器: {self.host}:{self.port}")
        self.server = await websockets.serve(
            self.handle_client, self.host, self.port
            )
        logger.info("✅ WebRTC信令服务器启动成功")

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔗 客户端已连接: {client_id}")

        self.clients[client_id] = websocket

        # 通知有新客户端连接
        if self.on_client_connected_callback:
            self.on_client_connected_callback(client_id)

        try:
            async for message in websocket:
                await self.handle_message(client_id, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 客户端正常断开连接: {client_id}")
        except websockets.exceptions.ConnectionClosedError:
            logger.info(f"🔌 客户端异常断开连接: {client_id}")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"🔌 客户端优雅断开连接: {client_id}")
        except Exception as e:
            logger.warning(f"⚠️ 处理客户端连接异常: {client_id} - {type(e).__name__}: {e}")
        finally:
            # 清理客户端
            if client_id in self.clients:
                del self.clients[client_id]
                logger.debug(f"🧹 清理客户端WebSocket连接: {client_id}")

            # 通知客户端断开连接
            if self.on_client_disconnected_callback:
                self.on_client_disconnected_callback(client_id)

    async def handle_message(self, client_id: str, message: str):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            logger.debug(f"📨 收到信令消息: {client_id} -> {message_type}")

            if message_type == "offer":
                # 处理WebRTC Offer
                if self.on_offer_callback:
                    await self.on_offer_callback(client_id, data)

            elif message_type == "answer":
                # 处理WebRTC Answer
                if self.on_answer_callback:
                    await self.on_answer_callback(client_id, data)

            elif message_type == "ice-candidate":
                # 处理ICE候选
                if self.on_ice_candidate_callback:
                    await self.on_ice_candidate_callback(client_id, data)

            elif message_type == "ping":
                # 心跳包
                await self.send_to_client(
                    client_id,
                    {
                        "type": "pong"
                        }
                    )

            else:
                logger.warning(f"⚠️ 未知消息类型: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"❌ 无效的JSON消息: {message}")
        except Exception as e:
            logger.error(f"❌ 处理消息错误: {e}")

    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """发送消息给指定客户端"""
        if client_id not in self.clients:
            logger.warning(f"⚠️ 客户端不存在: {client_id}")
            return

        try:
            websocket = self.clients[client_id]
            await websocket.send(json.dumps(message))
            logger.debug(f"📤 发送信令消息: {client_id} <- {message.get('type')}")
        except Exception as e:
            logger.error(f"❌ 发送消息失败: {e}")

    async def broadcast(self, message: Dict[str, Any], exclude_client: Optional[str] = None):
        """广播消息给所有客户端"""
        for client_id in self.clients:
            if exclude_client and client_id == exclude_client:
                continue
            await self.send_to_client(client_id, message)

    async def send_offer(self, client_id: str, offer: Dict[str, Any]):
        """发送WebRTC Offer给客户端"""
        message = {
            "type": "offer",
            "sdp": offer
            }
        await self.send_to_client(client_id, message)

    async def send_answer(self, client_id: str, answer: Dict[str, Any]):
        """发送WebRTC Answer给客户端"""
        message = {
            "type": "answer",
            "sdp": answer
            }
        await self.send_to_client(client_id, message)

    async def send_ice_candidate(self, client_id: str, candidate: Dict[str, Any]):
        """发送ICE候选给客户端"""
        message = {
            "type": "ice-candidate",
            "candidate": candidate
            }
        await self.send_to_client(client_id, message)

    def set_callbacks(
        self,
        on_offer: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_answer: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_ice_candidate: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_client_connected: Optional[Callable[[str], None]] = None,
        on_client_disconnected: Optional[Callable[[str], None]] = None, ):
        """设置回调函数"""
        if on_offer:
            self.on_offer_callback = on_offer
        if on_answer:
            self.on_answer_callback = on_answer
        if on_ice_candidate:
            self.on_ice_candidate_callback = on_ice_candidate
        if on_client_connected:
            self.on_client_connected_callback = on_client_connected
        if on_client_disconnected:
            self.on_client_disconnected_callback = on_client_disconnected

    async def stop(self):
        """停止信令服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("🛑 WebRTC信令服务器已停止")

    def get_client_count(self) -> int:
        """获取当前连接的客户端数量"""
        return len(self.clients)

import asyncio
import gzip
import json
import logging
import uuid
from typing import Dict, Any

import websockets
from websockets import ClientConnection, State

from src.volcengine import protocol
from src.volcengine.config import start_session_req

logger = logging.getLogger(__name__)


class VoicengineClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

        self.ws: ClientConnection | None = None
        self.logid = ""

        self.is_connected = False  # connection

        self.is_alive = False  # session
        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

    async def _deinit(self):
        self.is_alive = False
        self.is_connected = False
        if self.ws:
            await self.ws.close()
        self.ws = None

    @property
    def is_active(self) -> bool:
        return (self.ws is not None and self.ws.state == State.OPEN and self.is_alive)

    async def connect_websocket_server(self) -> None:
        """建立WebSocket连接"""
        try:
            logger.info(f"url: {self.config['base_url']}, headers: {self.config['headers']}")
            self.ws = await websockets.connect(
                self.config['base_url'], additional_headers=self.config['headers'], ping_interval=5
                )
            self.logid = self.ws.response_headers.get("X-Tt-Logid") if hasattr(self.ws, 'response_headers') else None
            logger.info(f"dialog server response logid: {self.logid}")
        except Exception as e:
            logger.warning(f"failed to connect, reason: {e}")

    async def start_connection(self) -> None:
        """
        区别于 @connect_websocket_server，这个是用于主动向火山发起一次连接请求，即：
        1. connect to server
        2. build a connection
        3. build a session
        """
        try:
            start_connection_request = bytearray(protocol.generate_header())
            start_connection_request.extend(int(1).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            start_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            start_connection_request.extend(payload_bytes)
            await self.ws.send(start_connection_request)
            logger.info("StartConnection request sent")
            self.is_connected = True
        except Exception as e:
            logger.warning(f"failed to start connection, reason: {e}")

    async def start_session(self) -> None:
        """发送StartSession请求"""
        try:
            request_params = start_session_req
            payload_bytes = str.encode(json.dumps(request_params))
            payload_bytes = gzip.compress(payload_bytes)
            start_session_request = bytearray(protocol.generate_header())
            start_session_request.extend(int(100).to_bytes(4, 'big'))
            start_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            start_session_request.extend(str.encode(self.session_id))
            start_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            start_session_request.extend(payload_bytes)
            await self.ws.send(start_session_request)
            logger.info("StartSession request sent")
            self.is_alive = True
        except Exception as e:
            logger.warning(f"failed to start session, reason: {e}")

    async def say_hello(self, content: str = "你好") -> None:
        """发送SayHello事件"""
        say_hello_request = bytearray(protocol.generate_header())
        say_hello_request.extend(int(300).to_bytes(4, 'big'))  # SayHello事件ID: 300
        say_hello_request.extend((len(self.session_id)).to_bytes(4, 'big'))
        say_hello_request.extend(str.encode(self.session_id))

        payload_data = {
            "content": content
            }
        payload_bytes = str.encode(json.dumps(payload_data, ensure_ascii=False))
        payload_bytes = gzip.compress(payload_bytes)
        say_hello_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        say_hello_request.extend(payload_bytes)
        await self.ws.send(say_hello_request)
        logger.info(f"SayHello sent: {content}")

    async def upload_audio(self, audio: bytes) -> None:
        if not self.is_active: return

        try:
            task_request = bytearray(
                protocol.generate_header(
                    message_type=protocol.CLIENT_AUDIO_ONLY_REQUEST, serial_method=protocol.NO_SERIALIZATION
                    )
                )
            task_request.extend(int(200).to_bytes(4, 'big'))
            task_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            task_request.extend(str.encode(self.session_id))
            payload_bytes = gzip.compress(audio)
            task_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
            task_request.extend(payload_bytes)
            await self.ws.send(task_request)
            logger.debug(f"🏠 --> 📡 {len(payload_bytes)} bytes")
        except Exception as e:
            logger.warning(f"failed to upload audio, reason: {e}")

    async def receive_server_response(self) -> Dict[str, Any] | None:
        if not self.is_active: return None

        try:
            response = await self.ws.recv()
            data = protocol.parse_response(response)
            return data
        except Exception as e:
            logger.warning(f"failed to receive server response, reason: {e}")

    async def finish_session(self):
        """发送结束会话请求"""
        if not self.is_active: return

        self.is_alive = False
        try:
            finish_session_request = bytearray(protocol.generate_header())
            finish_session_request.extend(int(102).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            finish_session_request.extend(str.encode(self.session_id))
            finish_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_session_request.extend(payload_bytes)
            await self.ws.send(finish_session_request)
            logger.info("FinishSession request sent")
        except Exception as e:
            logger.warning(f"failed to finish session, reason: {e}")

    async def finish_connection(self):
        """发送结束连接请求"""
        if not self.is_active: return

        self.is_connected = False
        try:
            finish_connection_request = bytearray(protocol.generate_header())
            finish_connection_request.extend(int(2).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_connection_request.extend(payload_bytes)
            await self.ws.send(finish_connection_request)
            logger.info("FinishConnection request sent")

            # 尝试接收响应，但设置超时
            try:
                response = await asyncio.wait_for(self.ws.recv(), timeout=3.0)
                logger.info(f"FinishConnection response: {protocol.parse_response(response)}")
            except asyncio.TimeoutError:
                logger.warning("等待FinishConnection响应超时")
            except Exception as e:
                logger.warning(f"接收FinishConnection响应失败: {e}")

        except Exception as e:
            logger.warning(f"failed to finish connection: {e}")

    async def graceful_shutdown(self) -> None:
        """优雅关闭WebSocket连接，包括发送结束请求"""
        if not self.ws: return

        try:
            logger.info("开始优雅关闭WebSocket连接...")

            # 尝试发送结束会话请求
            await self.finish_session()

            # 短暂等待，让服务器处理请求
            await asyncio.sleep(0.1)

            # 尝试发送结束连接请求
            await self.finish_connection()

            # 短暂等待，让服务器处理请求
            await asyncio.sleep(0.1)

            await self._deinit()

        except Exception as e:
            logger.warning(f"优雅关闭过程中出现错误: {e}")

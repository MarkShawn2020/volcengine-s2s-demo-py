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

        self.is_running = False
        self.is_connected = False  # connection
        self.is_alive = False  # session
        self.session_id = str(uuid.uuid4())
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

    @property
    def is_active(self) -> bool:
        return (self.ws is not None and self.ws.state == State.OPEN and self.is_alive)

    async def start(self) -> None:
        """建立WebSocket连接"""
        try:
            self.is_running = True
            logger.info(f"url: {self.config['base_url']}, headers: {self.config['headers']}")
            self.ws = await websockets.connect(
                self.config['base_url'], additional_headers=self.config['headers'], ping_interval=5
                )
            self.logid = self.ws.response_headers.get("X-Tt-Logid") if hasattr(self.ws, 'response_headers') else None
            logger.info(f"dialog server response logid: {self.logid}")

            await self.request_start_connection()

            await self.request_start_session()

        except Exception as e:
            logger.warning(f"failed to connect, reason: {e}")

    async def request_start_connection(self) -> None:
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
            logger.info("requesting start-connection")
            await self.ws.send(start_connection_request)
            logger.info("requested start-connection")
            self.is_connected = True
        except Exception as e:
            logger.warning(f"failed to request start-connection, reason: {e}")

    async def request_stop_connection(self):
        """发送结束连接请求"""
        if not self.is_connected: return

        self.is_connected = False
        try:
            finish_connection_request = bytearray(protocol.generate_header())
            finish_connection_request.extend(int(2).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_connection_request.extend(payload_bytes)
            logger.info("requesting stop-connection")
            await self.ws.send(finish_connection_request)
            logger.info("requested stop-connection")

        except Exception as e:
            logger.warning(f"failed to finish connection: {e}")

    async def request_start_session(self) -> None:
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
            logger.info("requesting start-session")
            await self.ws.send(start_session_request)
            logger.info("requested start-session")
            self.is_alive = True
        except Exception as e:
            logger.warning(f"failed to request start-session, reason: {e}")

    async def request_stop_session(self):
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
            logger.info("requesting stop-session")
            await self.ws.send(finish_session_request)
            logger.info("requested stop-session")
        except Exception as e:
            logger.warning(f"failed to stop session, reason: {e}")

    async def request_say_hello(self, content: str = "你好") -> None:
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
        logger.info(f"requesting say-hello, content: {content}")
        await self.ws.send(say_hello_request)
        logger.info(f"requested say-hello")

    async def push_audio(self, audio: bytes) -> None:
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
            push_result = await self.ws.send(task_request)
            logger.debug(f"🏠 --> 📡 {len(payload_bytes)} bytes, result: {push_result}")
        except Exception as e:
            logger.warning(f"failed to upload audio, reason: {e}")

    async def on_response(self) -> Dict[str, Any] | None:
        if not self.is_active: return None

        try:
            # logger.debug("waiting for response")
            # 设置超时，让程序能够定期检查is_running状态
            response = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
            data = protocol.parse_response(response)
            # logger.debug(f"on parsed-response")
            return data
        except asyncio.TimeoutError:
            # 超时时返回None，让调用方重新检查is_running状态
            return None
        except Exception as e:
            logger.warning(f"failed to receive server response, reason: {e}")

    async def stop(self) -> None:
        """优雅关闭WebSocket连接，包括发送结束请求"""
        if not self.is_running: return

        logger.info("stopping")
        self.is_running = False

        try:
            # 尝试发送结束会话请求
            await self.request_stop_session()

            # 尝试发送结束连接请求
            await self.request_stop_connection()

            if self.ws:
                await self.ws.close()
                self.ws = None
            logger.info("stopped")
        except Exception as e:
            logger.warning(f"failed to stop, reason: {e}")

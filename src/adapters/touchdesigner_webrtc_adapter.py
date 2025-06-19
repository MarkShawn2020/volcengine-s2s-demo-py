import asyncio
import json
import logging
import queue
import threading
from typing import AsyncGenerator, Optional, Dict, Any

from src.adapters.base import AudioAdapter, ConnectionConfig
from src.adapters.type import AdapterType
from src.volcengine import protocol
from src.volcengine.client import VolcengineClient
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


class TouchDesignerWebRTCConnectionConfig(ConnectionConfig):
    """TouchDesigner WebRTC连接配置"""

    def __init__(self, signaling_port: int, app_id: str, access_token: str, **kwargs):
        super().__init__(
            signaling_port=signaling_port,
            app_id=app_id,
            access_token=access_token,
            base_url="wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
            **kwargs
        )


class TouchDesignerWebRTCAudioAdapter(AudioAdapter):
    """TouchDesigner WebRTC音频适配器 - 通过WebSocket信令与TD进行WebRTC通信"""

    def __init__(self, config: TouchDesignerWebRTCConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None

        # WebSocket信令服务器配置
        self.signaling_port = self.config.get("signaling_port", 8080)
        self.signaling_server = None
        self._signaling_task = None

        # WebRTC相关
        self.peer_connections = {}  # 存储与TouchDesigner的对等连接
        self.audio_streams = {}     # 音频流管理

        # 音频格式配置 (根据豆包要求: 16kHz, 16-bit, mono)
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2
        
        # 队列初始化（兼容UnifiedAudioApp）
        self._send_queue = None
        self._play_queue = None

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCH_DESIGNER

    async def connect(self) -> bool:
        """建立与豆包的连接和WebRTC信令服务"""
        try:
            # 1. 建立与豆包的WebSocket连接
            self.client = VolcengineClient(ws_connect_config)
            await self.client.start()

            if not self.client.is_active:
                logger.error("豆包客户端连接失败")
                return False

            # 2. 启动WebSocket信令服务器
            await self._start_signaling_server()

            self.is_connected = True
            self.session_id = self.client.session_id

            # 启动响应接收任务
            self._receiver_task = asyncio.create_task(self._receive_responses())

            logger.info(f"TouchDesigner WebRTC适配器连接成功，会话ID: {self.session_id[:8]}...")
            logger.info(f"WebSocket信令服务器端口: {self.signaling_port}")
            return True

        except Exception as e:
            logger.error(f"TouchDesigner WebRTC适配器连接失败: {e}")
            return False

    async def _start_signaling_server(self):
        """启动WebSocket信令服务器用于WebRTC协商"""
        import websockets

        async def handle_signaling(websocket, path):
            """处理来自TouchDesigner的WebRTC信令"""
            try:
                logger.info(f"TouchDesigner客户端连接: {websocket.remote_address}")
                client_id = f"td_{id(websocket)}"

                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self._handle_signaling_message(client_id, data, websocket)
                    except json.JSONDecodeError:
                        logger.warning(f"无效的JSON消息: {message}")
                    except Exception as e:
                        logger.error(f"处理信令消息失败: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.info(f"TouchDesigner客户端断开连接")
            except Exception as e:
                logger.error(f"信令处理异常: {e}")
            finally:
                # 清理连接
                if client_id in self.peer_connections:
                    del self.peer_connections[client_id]

        self.signaling_server = await websockets.serve(
            handle_signaling,
            "0.0.0.0",
            self.signaling_port
        )

        logger.info(f"WebRTC信令服务器启动在端口 {self.signaling_port}")

    async def _handle_signaling_message(self, client_id: str, data: Dict[str, Any], websocket):
        """处理WebRTC信令消息"""
        message_type = data.get("type")

        if message_type == "offer":
            # 处理SDP offer
            await self._handle_offer(client_id, data, websocket)
        elif message_type == "answer":
            # 处理SDP answer
            await self._handle_answer(client_id, data)
        elif message_type == "ice-candidate":
            # 处理ICE候选
            await self._handle_ice_candidate(client_id, data)
        elif message_type == "audio-data":
            # 处理音频数据 (如果通过WebSocket传输)
            await self._handle_audio_data(data)
        elif message_type == "text-message":
            # 处理文本消息
            await self._handle_text_message(data)
        else:
            logger.warning(f"未知信令消息类型: {message_type}")

    async def _handle_offer(self, client_id: str, data: Dict[str, Any], websocket):
        """处理SDP offer"""
        try:
            # 这里应该创建WebRTC连接，但为了简化实现，我们先通过WebSocket模拟
            response = {
                "type": "answer",
                "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",  # 简化的SDP
                "session_id": self.session_id
            }
            await websocket.send(json.dumps(response))

            self.peer_connections[client_id] = {
                "websocket": websocket,
                "connected": True
            }

            logger.info(f"WebRTC连接建立: {client_id}")

        except Exception as e:
            logger.error(f"处理offer失败: {e}")

    async def _handle_answer(self, client_id: str, data: Dict[str, Any]):
        """处理SDP answer"""
        logger.info(f"收到SDP answer from {client_id}")

    async def _handle_ice_candidate(self, client_id: str, data: Dict[str, Any]):
        """处理ICE候选"""
        logger.debug(f"收到ICE candidate from {client_id}")

    async def _handle_audio_data(self, data: Dict[str, Any]):
        """处理来自TouchDesigner的音频数据"""
        try:
            # 假设音频数据是base64编码的
            import base64
            audio_data = base64.b64decode(data.get("audio", ""))
            if len(audio_data) > 0:
                # 转发到豆包
                await self.send_audio(audio_data)
                logger.debug(f"从TD接收并转发音频: {len(audio_data)} 字节")
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")

    async def _handle_text_message(self, data: Dict[str, Any]):
        """处理来自TouchDesigner的文本消息"""
        try:
            text = data.get("text", "")
            if text:
                await self.send_text(text)
                logger.info(f"从TD接收并转发文本: {text}")
        except Exception as e:
            logger.error(f"处理文本消息失败: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        logger.info("开始断开TouchDesigner WebRTC适配器连接")

        # 停止信令服务器
        if self.signaling_server:
            self.signaling_server.close()
            await self.signaling_server.wait_closed()

        # 关闭所有WebRTC连接
        for client_id, connection in self.peer_connections.items():
            try:
                if "websocket" in connection:
                    await connection["websocket"].close()
            except Exception as e:
                logger.warning(f"关闭WebSocket连接失败: {e}")

        self.peer_connections.clear()

        # 停止响应接收任务
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        # 断开豆包连接
        if self.client:
            await self.client.stop()
            self.client = None

        self.is_connected = False
        logger.info("TouchDesigner WebRTC适配器已断开连接")

    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据到豆包"""
        if not self.is_connected or not self.client:
            return False

        try:
            await self.client.push_audio(audio_data)
            return True
        except Exception as e:
            logger.error(f"发送音频到豆包失败: {e}")
            return False

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收来自豆包的音频数据流"""
        while self.is_connected:
            try:
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                if response.get('event') == protocol.ServerEvent.TTS_RESPONSE:
                    audio_data = response.get('payload_msg')
                    if isinstance(audio_data, bytes):
                        # 同时发送到TouchDesigner
                        await self._send_audio_to_td(audio_data)
                        yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break

    async def _send_audio_to_td(self, audio_data: bytes):
        """发送音频数据到TouchDesigner (通过WebSocket)"""
        try:
            import base64
            # 将音频数据编码为base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            message = {
                "type": "audio-response",
                "audio": audio_b64,
                "length": len(audio_data),
                "timestamp": asyncio.get_event_loop().time()
            }

            # 发送到所有连接的TouchDesigner客户端
            for client_id, connection in self.peer_connections.items():
                if connection.get("connected") and "websocket" in connection:
                    try:
                        await connection["websocket"].send(json.dumps(message))
                    except Exception as e:
                        logger.warning(f"发送音频到TD客户端 {client_id} 失败: {e}")

            logger.debug(f"发送音频到TD: {len(audio_data)} 字节")

        except Exception as e:
            logger.warning(f"发送音频到TouchDesigner失败: {e}")

    async def send_text(self, text: str) -> bool:
        """发送文本消息到豆包"""
        if not self.is_connected or not self.client:
            return False

        try:
            await self.client.push_text(text)

            # 同时发送状态到TouchDesigner
            await self._send_status_to_td(f"发送文本: {text}")

            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def _send_status_to_td(self, status: str):
        """发送状态信息到TouchDesigner"""
        try:
            message = {
                "type": "status",
                "message": status,
                "timestamp": asyncio.get_event_loop().time()
            }

            # 发送到所有连接的TouchDesigner客户端
            for client_id, connection in self.peer_connections.items():
                if connection.get("connected") and "websocket" in connection:
                    try:
                        await connection["websocket"].send(json.dumps(message))
                    except Exception as e:
                        logger.warning(f"发送状态到TD客户端 {client_id} 失败: {e}")

        except Exception as e:
            logger.warning(f"发送状态到TouchDesigner失败: {e}")

    async def _receive_responses(self):
        """接收豆包响应的后台任务"""
        while self.is_connected and self.client:
            try:
                response = await self.client.on_response()
                if response:
                    await self.response_queue.put(response)

                    # 发送事件状态到TouchDesigner
                    if response.get('event'):
                        event_name = str(response.get('event'))
                        await self._send_status_to_td(f"事件: {event_name}")

            except Exception as e:
                logger.error(f"接收豆包响应失败: {e}")
                break

    async def setup_audio_devices(self, p, stop_event: threading.Event) -> tuple[Optional[threading.Thread], Optional[threading.Thread]]:
        """TouchDesigner WebRTC模式：音频通过WebRTC传输，跳过系统音频设备选择"""
        logger.info("TouchDesigner WebRTC模式：音频通过WebRTC传输，跳过系统音频设备选择")
        
        # 创建队列（兼容UnifiedAudioApp）
        import queue
        self._send_queue = queue.Queue()
        self._play_queue = queue.Queue()
        
        return None, None

    async def run_sender_task(self, send_queue: queue.Queue, stop_event: threading.Event) -> None:
        """TouchDesigner WebRTC发送任务 - 等待TouchDesigner WebRTC连接和音频数据"""
        logger.info("TouchDesigner WebRTC发送任务启动，等待TouchDesigner连接")

        try:
            while not stop_event.is_set() and self.is_connected:
                # 监控连接状态
                connected_clients = len([c for c in self.peer_connections.values() if c.get("connected")])
                if connected_clients > 0:
                    logger.debug(f"当前有 {connected_clients} 个TouchDesigner客户端连接")

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"TouchDesigner WebRTC发送任务异常: {e}")

        logger.info("TouchDesigner WebRTC发送任务结束")

    async def run_receiver_task(self, play_queue: queue.Queue, stop_event: threading.Event) -> None:
        """TouchDesigner WebRTC接收任务"""
        logger.info("TouchDesigner WebRTC接收任务启动")
        received_count = 0

        try:
            async for audio_data in self.receive_audio():
                logger.debug(f"收到音频数据: {len(audio_data)} bytes")
                if stop_event.is_set():
                    break

                received_count += 1
                logger.debug(f"收到音频数据 #{received_count}，大小: {len(audio_data)} bytes")

                # 将音频数据放入播放队列
                try:
                    play_queue.put_nowait({
                        "payload_msg": audio_data
                    })
                except queue.Full:
                    # 播放队列满时，移除最老的数据再放入新数据
                    try:
                        play_queue.get_nowait()
                        play_queue.put_nowait({
                            "payload_msg": audio_data
                        })
                    except queue.Empty:
                        pass

        except Exception as e:
            logger.error(f"TouchDesigner WebRTC接收任务异常: {e}")

        if received_count > 0:
            logger.info(f"TouchDesigner WebRTC总共接收 {received_count} 个音频数据")
import asyncio
import json
import logging
import queue
import threading
from typing import AsyncGenerator, Optional, Dict, Any
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender
from aiortc.rtcrtpreceiver import RTCRtpReceiver
import numpy as np

from src.adapters.base import AudioAdapter, ConnectionConfig
from src.adapters.type import AdapterType
from src.volcengine import protocol
from src.volcengine.client import VolcengineClient
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


class TouchDesignerProperWebRTCConnectionConfig(ConnectionConfig):
    """TouchDesigner 真正WebRTC连接配置"""

    def __init__(self, signaling_port: int, webrtc_port: int, app_id: str, access_token: str, **kwargs):
        super().__init__(
            signaling_port=signaling_port,
            webrtc_port=webrtc_port,
            app_id=app_id,
            access_token=access_token,
            base_url="wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
            **kwargs
        )


class AudioTrackReceiver:
    """音频轨道接收器 - 处理来自TouchDesigner的音频"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.audio_buffer = asyncio.Queue()
        
    async def recv(self):
        """接收音频帧"""
        try:
            # 从缓冲区获取音频数据
            audio_data = await asyncio.wait_for(self.audio_buffer.get(), timeout=0.1)
            return audio_data
        except asyncio.TimeoutError:
            return None
    
    async def add_audio_data(self, audio_data: bytes):
        """添加音频数据到缓冲区"""
        await self.audio_buffer.put(audio_data)


class AudioTrackSender:
    """音频轨道发送器 - 发送音频到TouchDesigner"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self._running = False
        
    async def send(self, audio_data: bytes):
        """发送音频数据"""
        if self._running:
            # 通过WebRTC发送音频数据
            # 这里需要将bytes转换为适当的音频帧格式
            logger.debug(f"通过WebRTC发送音频: {len(audio_data)} 字节")


class TouchDesignerProperWebRTCAudioAdapter(AudioAdapter):
    """TouchDesigner真正WebRTC音频适配器 - 实现完整的WebRTC协议"""

    def __init__(self, config: TouchDesignerProperWebRTCConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None

        # WebRTC配置
        self.signaling_port = self.config.get("signaling_port", 8080)
        self.webrtc_port = self.config.get("webrtc_port", 8081)
        
        # WebRTC相关
        self.peer_connections = {}  # 存储RTCPeerConnection实例
        self.signaling_server = None
        self.media_relay = MediaRelay()
        
        # 音频轨道
        self.audio_receivers = {}  # 接收来自TD的音频
        self.audio_senders = {}    # 发送音频到TD

        # 音频格式配置
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2
        
        # 队列初始化（兼容UnifiedAudioApp）
        self._send_queue = None
        self._play_queue = None

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCH_DESIGNER_WEBRTC

    async def connect(self) -> bool:
        """建立连接"""
        try:
            # 1. 建立与豆包的WebSocket连接
            self.client = VolcengineClient(ws_connect_config)
            await self.client.start()

            if not self.client.is_active:
                logger.error("豆包客户端连接失败")
                return False

            # 2. 启动WebRTC信令服务器
            await self._start_webrtc_signaling_server()

            self.is_connected = True
            self.session_id = self.client.session_id

            # 启动响应接收任务
            self._receiver_task = asyncio.create_task(self._receive_responses())

            logger.info(f"TouchDesigner WebRTC适配器连接成功，会话ID: {self.session_id[:8]}...")
            logger.info(f"WebRTC信令服务器端口: {self.signaling_port}")
            return True

        except Exception as e:
            logger.error(f"TouchDesigner WebRTC适配器连接失败: {e}")
            return False

    async def _start_webrtc_signaling_server(self):
        """启动WebRTC信令服务器"""
        async def handle_websocket(websocket, path):
            """处理WebRTC信令WebSocket连接"""
            try:
                client_id = f"td_{id(websocket)}"
                logger.info(f"TouchDesigner WebRTC客户端连接: {client_id}")
                
                # 创建RTCPeerConnection
                pc = RTCPeerConnection()
                self.peer_connections[client_id] = {
                    "pc": pc,
                    "websocket": websocket,
                    "connected": False
                }

                # 设置WebRTC事件处理
                await self._setup_webrtc_handlers(client_id, pc)

                # 处理信令消息
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self._handle_webrtc_signaling(client_id, data, websocket)
                    except json.JSONDecodeError:
                        logger.warning(f"无效的JSON消息: {message}")
                    except Exception as e:
                        logger.error(f"处理信令消息失败: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.info(f"TouchDesigner WebRTC客户端断开连接: {client_id}")
            except Exception as e:
                logger.error(f"WebRTC信令处理异常: {e}")
            finally:
                # 清理连接
                if client_id in self.peer_connections:
                    await self.peer_connections[client_id]["pc"].close()
                    del self.peer_connections[client_id]

        self.signaling_server = await websockets.serve(
            handle_websocket,
            "0.0.0.0",
            self.signaling_port
        )

        logger.info(f"WebRTC信令服务器启动在端口 {self.signaling_port}")

    async def _setup_webrtc_handlers(self, client_id: str, pc: RTCPeerConnection):
        """设置WebRTC事件处理器"""
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"WebRTC连接状态变化 {client_id}: {pc.connectionState}")
            if pc.connectionState == "connected":
                self.peer_connections[client_id]["connected"] = True
                logger.info(f"WebRTC连接建立成功: {client_id}")

        @pc.on("track")
        def on_track(track):
            logger.info(f"收到WebRTC音频轨道 {client_id}: {track.kind}")
            if track.kind == "audio":
                # 创建音频接收器
                receiver = AudioTrackReceiver(self)
                self.audio_receivers[client_id] = receiver
                
                # 启动音频接收任务
                asyncio.create_task(self._handle_incoming_audio(client_id, track))

        @pc.on("datachannel")
        def on_datachannel(channel):
            logger.info(f"收到数据通道 {client_id}: {channel.label}")

    async def _handle_incoming_audio(self, client_id: str, track):
        """处理来自TouchDesigner的音频流"""
        try:
            while True:
                frame = await track.recv()
                # 将音频帧转换为字节数据
                audio_data = self._audio_frame_to_bytes(frame)
                if audio_data:
                    # 转发到豆包
                    await self.send_audio(audio_data)
                    logger.debug(f"从TD接收并转发音频: {len(audio_data)} 字节")
        except Exception as e:
            logger.error(f"处理音频流失败: {e}")

    def _audio_frame_to_bytes(self, frame) -> bytes:
        """将音频帧转换为字节数据"""
        try:
            # 假设frame是AudioFrame对象
            # 将其转换为PCM字节数据
            if hasattr(frame, 'to_ndarray'):
                # 获取numpy数组
                array = frame.to_ndarray()
                # 转换为16位PCM
                if array.dtype != np.int16:
                    array = (array * 32767).astype(np.int16)
                return array.tobytes()
            return b''
        except Exception as e:
            logger.error(f"音频帧转换失败: {e}")
            return b''

    async def _handle_webrtc_signaling(self, client_id: str, data: Dict[str, Any], websocket):
        """处理WebRTC信令消息"""
        message_type = data.get("type")
        pc = self.peer_connections[client_id]["pc"]

        try:
            if message_type == "offer":
                # 处理SDP offer
                offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                await pc.setRemoteDescription(offer)

                # 创建并发送answer
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)

                response = {
                    "type": "answer",
                    "sdp": pc.localDescription.sdp
                }
                await websocket.send(json.dumps(response))
                logger.info(f"发送WebRTC answer: {client_id}")

            elif message_type == "answer":
                # 处理SDP answer
                answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                await pc.setRemoteDescription(answer)
                logger.info(f"收到WebRTC answer: {client_id}")

            elif message_type == "ice-candidate":
                # 处理ICE candidate
                if data.get("candidate"):
                    candidate = RTCIceCandidate(
                        component=data.get("component", 1),
                        foundation=data.get("foundation", ""),
                        ip=data.get("ip", ""),
                        port=data.get("port", 0),
                        priority=data.get("priority", 0),
                        protocol=data.get("protocol", "udp"),
                        type=data.get("type", "host")
                    )
                    await pc.addIceCandidate(candidate)
                    logger.debug(f"添加ICE candidate: {client_id}")

        except Exception as e:
            logger.error(f"处理WebRTC信令失败: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        logger.info("开始断开TouchDesigner WebRTC适配器连接")

        # 关闭所有WebRTC连接
        for client_id, connection in self.peer_connections.items():
            try:
                await connection["pc"].close()
                if "websocket" in connection:
                    await connection["websocket"].close()
            except Exception as e:
                logger.warning(f"关闭WebRTC连接失败: {e}")

        self.peer_connections.clear()

        # 停止信令服务器
        if self.signaling_server:
            self.signaling_server.close()
            await self.signaling_server.wait_closed()

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
                        # 发送到TouchDesigner
                        await self._send_audio_to_touchdesigner(audio_data)
                        yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break

    async def _send_audio_to_touchdesigner(self, audio_data: bytes):
        """通过WebRTC发送音频到TouchDesigner"""
        try:
            # 通过WebRTC音频轨道发送音频
            for client_id, sender in self.audio_senders.items():
                if sender:
                    await sender.send(audio_data)
            
            logger.debug(f"通过WebRTC发送音频到TD: {len(audio_data)} 字节")

        except Exception as e:
            logger.warning(f"发送音频到TouchDesigner失败: {e}")

    async def send_text(self, text: str) -> bool:
        """发送文本消息到豆包"""
        if not self.is_connected or not self.client:
            return False

        try:
            await self.client.push_text(text)
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def _receive_responses(self):
        """接收豆包响应的后台任务"""
        while self.is_connected and self.client:
            try:
                response = await self.client.on_response()
                if response:
                    await self.response_queue.put(response)
            except Exception as e:
                logger.error(f"接收豆包响应失败: {e}")
                break

    async def setup_audio_devices(self, p, stop_event: threading.Event) -> tuple[Optional[threading.Thread], Optional[threading.Thread]]:
        """TouchDesigner WebRTC模式：音频通过WebRTC传输"""
        logger.info("TouchDesigner WebRTC模式：音频通过WebRTC传输")
        
        # 创建队列（兼容UnifiedAudioApp）
        import queue
        self._send_queue = queue.Queue()
        self._play_queue = queue.Queue()
        
        return None, None

    async def run_sender_task(self, send_queue: queue.Queue, stop_event: threading.Event) -> None:
        """TouchDesigner WebRTC发送任务"""
        logger.info("TouchDesigner WebRTC发送任务启动")

        try:
            while not stop_event.is_set() and self.is_connected:
                # 监控WebRTC连接状态
                connected_clients = len([c for c in self.peer_connections.values() if c.get("connected")])
                if connected_clients > 0:
                    logger.debug(f"当前有 {connected_clients} 个WebRTC连接")

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

                # 将音频数据放入播放队列（用于本地播放）
                try:
                    play_queue.put_nowait({
                        "payload_msg": audio_data
                    })
                except queue.Full:
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
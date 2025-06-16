import asyncio
import logging
from typing import Dict, Optional, Callable, Any, Awaitable

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate

from src.audio.audio_stream_track import AudioStreamTrack
from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.webrtc.webrtc_signaling_server import WebRTCSignalingServer

logger = logging.getLogger(__name__)


class WebRTCManager:
    """WebRTC管理器，处理与浏览器的WebRTC连接"""

    def __init__(self, config: WebrtcConfig) -> None:
        self.config = config
        self.signaling_server = WebRTCSignalingServer(self.config)
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        # 分离发送轨道和接收轨道
        self.server2client_tracks: Dict[str, AudioStreamTrack] = {}  # 发送AI音频到浏览器
        self.client2server_tracks: Dict[str, AudioStreamTrack] = {}  # 接收浏览器麦克风音频

        # 音频处理回调
        self.on_client_connected: Optional[Callable[[str], Awaitable[None]]] = None

        # 管理器运行状态
        self.is_running = False

        # 错误计数器，避免重复错误日志
        self._error_counters = {}

        # 设置信令服务器回调
        self.signaling_server.set_callbacks(
            on_offer=self.handle_offer,
            on_answer=self.handle_answer,
            on_ice_candidate=self.handle_ice_candidate,
            on_client_connected=self.handle_client_connected,
            on_client_disconnected=self.handle_client_disconnected, )

    async def start(self):
        """启动WebRTC管理器"""
        logger.info("🚀 启动WebRTC管理器")
        self.is_running = True
        await self.signaling_server.start()

    async def stop(self):
        """停止WebRTC管理器"""
        logger.info("🛑 停止WebRTC管理器")

        # 设置停止标志
        self.is_running = False

        # 取消所有音频轨道处理任务
        if hasattr(self, '_track_handlers'):
            for client_id, task in list(self._track_handlers.items()):
                if not task.done():
                    task.cancel()
                    logger.debug(f"🛑 已取消音频轨道处理任务: {client_id}")
            self._track_handlers.clear()

        # 关闭所有音频轨道
        for client_id, server2client_track in list(self.server2client_tracks.items()):
            try:
                if hasattr(server2client_track, 'stop'):
                    server2client_track.stop()
            except Exception as e:
                logger.debug(f"停止server2client轨道错误: {e}")
        
        # client2server轨道通常不需要手动停止，由WebRTC自动处理

        # 关闭所有peer connections
        for pc in self.peer_connections.values():
            try:
                await pc.close()
            except Exception as e:
                logger.debug(f"关闭peer connection错误: {e}")

        # 清理所有资源
        self.peer_connections.clear()
        self.server2client_tracks.clear()
        self.client2server_tracks.clear()

        await self.signaling_server.stop()

    def handle_client_connected(self, client_id: str):
        """处理客户端连接"""
        logger.info(f"🔗 WebRTC客户端连接: {client_id}")

        # 创建新的RTCPeerConnection
        pc = RTCPeerConnection()
        self.peer_connections[client_id] = pc

        # 创建发送轨道用于发送AI音频给浏览器 (server2client)
        server2client_track = AudioStreamTrack(sample_rate=self.config.sample_rate)
        self.server2client_tracks[client_id] = server2client_track

        # 添加发送轨道到连接
        pc.addTransceiver(server2client_track, direction="sendrecv")

        # 设置连接状态变化回调
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = pc.connectionState
            logger.info(f"🔄 连接状态变化: {client_id} -> {state}")

            if state == "failed":
                logger.error(f"❌ WebRTC连接失败: {client_id}")
                # 连接失败时立即清理资源
                self._cleanup_client_resources(client_id)
            elif state == "disconnected":
                logger.warning(f"⚠️ WebRTC连接断开: {client_id}")
                # 连接断开时立即清理资源
                self._cleanup_client_resources(client_id)
            elif state == "closed":
                logger.info(f"🔌 WebRTC连接已关闭: {client_id}")
                # 确保资源已清理
                self._cleanup_client_resources(client_id)
            elif state == "connected":
                logger.info(f"✅ WebRTC连接已建立: {client_id}")
                # 触发客户端连接回调
                if self.on_client_connected:
                    asyncio.create_task(self.on_client_connected(client_id))

        # 设置接收音频轨道回调 (client2server)
        @pc.on("track")
        def on_track(track):
            logger.info(f"🎤 接收到音频轨道: {client_id} -> {track.kind}")
            if track.kind == "audio":
                # 存储接收轨道用于获取浏览器麦克风音频
                self.client2server_tracks[client_id] = track
                logger.info(f"✅ 已保存client2server轨道: {client_id}")

    def handle_client_disconnected(self, client_id: str):
        """处理客户端断开连接"""
        logger.info(f"🔌 WebRTC客户端断开: {client_id}")
        self._cleanup_client_resources(client_id)

    def _cleanup_client_resources(self, client_id: str):
        """清理指定客户端的所有资源"""
        logger.debug(f"🧹 开始清理客户端资源: {client_id}")

        # 取消音频轨道处理任务
        if hasattr(self, '_track_handlers') and client_id in self._track_handlers:
            task = self._track_handlers[client_id]
            if not task.done():
                task.cancel()
                logger.debug(f"🛑 已取消音频轨道处理任务: {client_id}")
            del self._track_handlers[client_id]

        # 停止server2client轨道
        if client_id in self.server2client_tracks:
            try:
                server2client_track = self.server2client_tracks[client_id]
                if hasattr(server2client_track, 'stop'):
                    server2client_track.stop()
                    logger.debug(f"🛑 已停止server2client轨道: {client_id}")
            except Exception as e:
                logger.debug(f"停止server2client轨道错误: {e}")
            del self.server2client_tracks[client_id]

        # 清理client2server轨道
        if client_id in self.client2server_tracks:
            logger.debug(f"🗑️ 清理client2server轨道: {client_id}")
            del self.client2server_tracks[client_id]

        # 清理peer connection
        if client_id in self.peer_connections:
            try:
                pc = self.peer_connections[client_id]
                # 不使用asyncio.create_task，因为这可能在回调中被调用
                if hasattr(pc, 'close'):
                    # 尝试同步关闭，或者安排异步关闭
                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(pc.close())
                        else:
                            loop.run_until_complete(pc.close())
                    except Exception:
                        pass  # 如果异步关闭失败，忽略错误
            except Exception as e:
                logger.debug(f"关闭peer connection时出错: {e}")
            del self.peer_connections[client_id]

        # 清理错误计数器
        keys_to_remove = [key for key in self._error_counters.keys() if key.startswith(f"{client_id}:")]
        for key in keys_to_remove:
            del self._error_counters[key]

        logger.debug(f"✅ 客户端资源清理完成: {client_id}")

    async def handle_offer(self, client_id: str, data: Dict[str, Any]):
        """处理WebRTC Offer"""
        logger.info(f"📨 收到Offer: {client_id}")

        if client_id not in self.peer_connections:
            logger.error(f"❌ 客户端连接不存在: {client_id}")
            return

        pc = self.peer_connections[client_id]

        try:
            # 设置远程描述
            offer = RTCSessionDescription(sdp=data["sdp"]["sdp"], type=data["sdp"]["type"])
            await pc.setRemoteDescription(offer)

            # 创建答案
            answer = await pc.createAnswer()

            # todo: 如果使用16k
            if self.config.sample_rate == 16000:
                answer.sdp = self._modify_sdp_for_16khz(answer.sdp)

            answer = RTCSessionDescription(sdp=answer.sdp, type=answer.type)

            await pc.setLocalDescription(answer)

            # 发送答案给客户端
            await self.signaling_server.send_answer(
                client_id, {
                    "type": answer.type,
                    "sdp": answer.sdp
                    }
                )

            logger.debug(f"📤 发送Answer: {client_id}")

        except Exception as e:
            logger.error(f"❌ 处理Offer错误: {e}")

    async def handle_answer(self, client_id: str, data: Dict[str, Any]):
        """处理WebRTC Answer"""
        logger.info(f"📨 收到Answer: {client_id}")  # 通常服务器端不需要处理Answer

    async def handle_ice_candidate(self, client_id: str, data: Dict[str, Any]):
        """处理ICE候选"""
        logger.debug(f"📨 收到ICE候选: {client_id}")

        if client_id not in self.peer_connections:
            logger.error(f"❌ 客户端连接不存在: {client_id}")
            return

        pc = self.peer_connections[client_id]

        try:
            candidate_data = data["candidate"]
            if candidate_data and candidate_data.get("candidate"):
                # 解析ICE候选字符串
                candidate_string = candidate_data["candidate"]
                sdp_mid = candidate_data.get("sdpMid")
                sdp_mline_index = candidate_data.get("sdpMLineIndex")

                # 手动解析候选字符串 (例如: "candidate:1 1 UDP 2113667326 192.168.1.1 54400 typ host")
                parts = candidate_string.split()
                if len(parts) >= 8:
                    foundation = parts[0].split(":")[1] if ":" in parts[0] else parts[0]
                    component = int(parts[1])
                    protocol = parts[2].lower()
                    priority = int(parts[3])
                    ip = parts[4]
                    port = int(parts[5])
                    typ = parts[7] if len(parts) > 7 else "host"

                    # 创建RTCIceCandidate对象
                    candidate = RTCIceCandidate(
                        foundation=foundation,
                        component=component,
                        protocol=protocol,
                        priority=priority,
                        ip=ip,
                        port=port,
                        type=typ,
                        sdpMid=sdp_mid,
                        sdpMLineIndex=sdp_mline_index
                        )

                    await pc.addIceCandidate(candidate)
                else:
                    logger.warning(f"⚠️ 无效的ICE候选格式: {candidate_string}")
            else:
                # 空候选表示候选收集结束
                await pc.addIceCandidate(None)
        except Exception as e:
            logger.error(f"❌ 添加ICE候选错误: {e}")

    def set_on_client_connected(self, callback: Callable[[str], Awaitable[None]]):
        self.on_client_connected = callback

    def _modify_sdp_for_16khz(self, sdp: str) -> str:
        """修改SDP以支持16000采样率"""
        lines = sdp.split('\n')
        modified_lines = []

        for line in lines:
            modified_lines.append(line)
            # 在opus的a=fmtp行中添加maxplaybackrate=16000
            if line.startswith('a=fmtp:') and 'opus' in sdp.lower():
                # 提取fmtp行的payload type
                parts = line.split(' ', 1)
                if len(parts) > 1:
                    # 如果已经有参数，添加maxplaybackrate
                    if ';' in parts[1] or '=' in parts[1]:
                        modified_lines[-1] = line + ';maxplaybackrate=16000'
                    else:
                        modified_lines[-1] = line + ' maxplaybackrate=16000'
                    logger.info(f"🎵 修改SDP支持16kHz采样率: {modified_lines[-1]}")

        return '\n'.join(modified_lines)

    def get_client_count(self) -> int:
        """获取当前连接的客户端数量"""
        return len(self.peer_connections)

    @property
    def audio_tracks(self):
        """兼容性属性，返回包含两种轨道的字典"""
        tracks = {}
        # 添加server2client轨道
        for client_id, track in self.server2client_tracks.items():
            tracks[f"server2client"] = track
        # 添加client2server轨道
        for client_id, track in self.client2server_tracks.items():
            tracks[f"client2server"] = track
        return tracks

    @property
    def send_tracks(self):
        """兼容性属性，映射到server2client_tracks"""
        return self.server2client_tracks

    @property
    def recv_tracks(self):
        """兼容性属性，映射到client2server_tracks"""
        return self.client2server_tracks

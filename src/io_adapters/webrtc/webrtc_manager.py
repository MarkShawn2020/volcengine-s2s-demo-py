import asyncio
from typing import Dict, Optional, Callable, Any

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate

from src.audio.audio_stream_track import AudioStreamTrack
from src.audio.input_processor import AudioFrameProcessor
from src.audio.type import AudioType
from src.io_adapters.webrtc.webrtc_signaling_server import WebRTCSignalingServer
from src.utils.logger import logger


class WebRTCManager:
    """WebRTC管理器，处理与浏览器的WebRTC连接"""

    def __init__(self, host: str = "localhost", port: int = 8765):

        self.signaling_server = WebRTCSignalingServer(host, port)
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.audio_tracks: Dict[str, AudioStreamTrack] = {}

        self.frame_processor = AudioFrameProcessor()  # 创建处理器实例

        # 音频处理回调
        self.audio_input_callback: Optional[Callable[[bytes], None]] = None
        self.client_connected_callback: Optional[Callable[[str], None]] = None

        # 管理器运行状态
        self.is_running = True

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
        for client_id, audio_track in list(self.audio_tracks.items()):
            try:
                if hasattr(audio_track, 'stop'):
                    audio_track.stop()
            except Exception as e:
                logger.debug(f"停止音频轨道错误: {e}")

        # 关闭所有peer connections
        for pc in self.peer_connections.values():
            try:
                await pc.close()
            except Exception as e:
                logger.debug(f"关闭peer connection错误: {e}")

        # 清理所有资源
        self.peer_connections.clear()
        self.audio_tracks.clear()

        await self.signaling_server.stop()

    def handle_client_connected(self, client_id: str):
        """处理客户端连接"""
        logger.info(f"🔗 WebRTC客户端连接: {client_id}")

        # 创建新的RTCPeerConnection
        pc = RTCPeerConnection()
        self.peer_connections[client_id] = pc

        # 创建音频轨道用于发送音频给浏览器
        audio_track = AudioStreamTrack()
        self.audio_tracks[client_id] = audio_track

        # 明确指定音频轨道参数，确保与OPUS编码器兼容
        transceiver = pc.addTransceiver(audio_track, direction="sendrecv")

        # 设置OPUS编码器参数 - 通过SDP协商来配置
        try:
            # aiortc会自动选择OPUS编码器，我们只需要确保音频格式正确
            logger.info(f"🎵 WebRTC轨道已添加，将使用OPUS编码")
        except Exception as e:
            logger.warning(f"⚠️ OPUS编码器配置失败: {e}")

        # 日志记录WebRTC配置
        logger.info(f"🎵 创建音频轨道: 48kHz, mono, s16 -> OPUS编码")

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
                if self.client_connected_callback:
                    self.client_connected_callback(client_id)

        # 设置接收音频轨道回调
        @pc.on("track")
        def on_track(track):
            logger.info(f"🎤 接收到音频轨道: {client_id} -> {track.kind}")
            if track.kind == "audio":
                # 记录音频轨道，用于重连时的清理
                self._track_handlers = getattr(self, '_track_handlers', {})
                task = asyncio.create_task(self.process_audio_track(client_id, track))
                self._track_handlers[client_id] = task

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

        # 停止音频轨道
        if client_id in self.audio_tracks:
            try:
                audio_track = self.audio_tracks[client_id]
                if hasattr(audio_track, 'stop'):
                    audio_track.stop()
                    logger.debug(f"🛑 已停止音频轨道: {client_id}")
            except Exception as e:
                logger.debug(f"停止音频轨道错误: {e}")
            del self.audio_tracks[client_id]

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
            await pc.setLocalDescription(answer)

            # 发送答案给客户端
            await self.signaling_server.send_answer(
                client_id, {
                    "type": answer.type,
                    "sdp": answer.sdp
                    }
                )

            logger.info(f"📤 发送Answer: {client_id}")

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

    async def process_audio_track(self, client_id: str, track):
        """
        从音频轨道接收帧，并委托给 AudioFrameProcessor 处理。
        (此版本更健壮、更简洁)
        """
        logger.info(f"🎵 开始处理音频轨道: {client_id}")
        pc = self.peer_connections.get(client_id)
        if not pc:
            logger.warning(f"处理音频轨道时，找不到 PeerConnection: {client_id}")
            return

        try:
            while self.is_running and pc.connectionState in ["new", "connecting", "connected"]:
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.debug(f"从客户端 {client_id} 接收音频超时，继续等待...")
                    if pc.connectionState not in ["new", "connecting", "connected"]:
                        logger.warning(f"客户端 {client_id} 连接状态恶化 ({pc.connectionState})，停止接收。")
                        break
                    continue
                except asyncio.CancelledError:
                    logger.info(f"音频轨道接收任务被取消: {client_id}")
                    break

                # --- 核心委托步骤 ---
                processed_data = self.frame_processor.process_frame(frame)

                if processed_data and self.audio_input_callback:
                    # 将处理好的、符合ASR要求的字节流传递给上层
                    self.audio_input_callback(processed_data)

        except Exception as e:
            logger.error(f"❌ 处理音频轨道时发生意外错误 ({client_id}): {e}", exc_info=True)
        finally:
            logger.info(f"🔚 音频轨道处理循环结束: {client_id}")

    # 这个方法现在是 async def
    async def send_audio_to_client(self, client_id: str, pcm_data: bytes):
        if client_id in self.audio_tracks:
            track = self.audio_tracks[client_id]
            await track.add_p_c_m_data(pcm_data)
        else:
            logger.warning(f"⚠️ 客户端音频轨道不存在: {client_id}")

    # 这个也变成 async def
    async def send_audio_to_all_clients(self, pcm_data: bytes, audio_type: AudioType):
        if not pcm_data or audio_type != AudioType.pcm:
            return

        # 使用 asyncio.gather 并行地向所有客户端发送
        tasks = [
            self.send_audio_to_client(client_id, pcm_data)
            for client_id in self.audio_tracks.keys()
            ]
        if tasks:
            await asyncio.gather(*tasks)

    def set_audio_input_callback(self, callback: Callable[[bytes], None]):
        """设置音频输入回调函数"""
        self.audio_input_callback = callback

    def set_client_connected_callback(self, callback: Callable[[str], None]):
        """设置客户端连接回调函数"""
        self.client_connected_callback = callback

    def get_client_count(self) -> int:
        """获取当前连接的客户端数量"""
        return len(self.peer_connections)

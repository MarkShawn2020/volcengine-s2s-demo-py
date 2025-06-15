import asyncio
from typing import Dict, Optional, Callable, Any

import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate

from src.audio.type import AudioType
from src.io_adapters.webrtc.audio_stream_track import AudioStreamTrack
from src.io_adapters.webrtc.webrtc_signaling_server import WebRTCSignalingServer
from src.utils.logger import logger


class WebRTCManager:
    """WebRTC管理器，处理与浏览器的WebRTC连接"""

    def __init__(self, host: str = "localhost", port: int = 8765):

        self.signaling_server = WebRTCSignalingServer(host, port)
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.audio_tracks: Dict[str, AudioStreamTrack] = {}

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
        """处理接收到的音频轨道"""
        logger.info(f"🎵 开始处理音频轨道: {client_id}")

        try:
            while self.is_running and client_id in self.peer_connections:
                # 检查客户端连接状态
                if client_id in self.peer_connections:
                    pc = self.peer_connections[client_id]
                    if pc.connectionState in ["failed", "disconnected", "closed"]:
                        logger.info(f"🔚 客户端连接已断开，停止音频轨道处理: {client_id} (状态: {pc.connectionState})")
                        break

                # 设置接收超时，避免无限等待
                frame = await asyncio.wait_for(track.recv(), timeout=3.0)

                if frame is None:
                    logger.debug(f"⚠️ 接收到空音频帧，跳过处理")
                    continue

                # logger.debug(f"🎤 收到音频帧: {frame.format}, 采样率: {frame.sample_rate}, 样本数: {frame.samples}")

                # 转换音频帧为numpy数组
                audio_array = frame.to_ndarray()

                if audio_array is None or audio_array.size == 0:
                    logger.debug(f"⚠️ 音频数组为空，跳过处理")
                    continue

                # logger.debug(f"🎤 音频数组形状: {audio_array.shape}, 数据类型: {audio_array.dtype}")

                # 如果是多维数组，展平为一维（通道在第一维）
                if len(audio_array.shape) > 1:
                    # 如果是多通道，取第一个通道或平均
                    if audio_array.shape[0] > 1:
                        audio_array = audio_array[0]  # 取第一个通道
                    else:
                        audio_array = audio_array.flatten()

                # logger.debug(f"🎤 展平后音频数组形状: {audio_array.shape}")

                # 转换为16位PCM格式（火山引擎需要的格式）
                if audio_array.dtype != 'int16':
                    # 如果是浮点格式，转换为int16
                    if audio_array.dtype.kind == 'f':
                        audio_array = (audio_array * 32767).astype('int16')
                    else:
                        audio_array = audio_array.astype('int16')

                # 重采样到16kHz（如果需要）
                if frame.sample_rate != 16000:
                    # 简单的重采样（生产环境建议使用更好的重采样算法）
                    target_length = int(len(audio_array) * 16000 / frame.sample_rate)
                    if target_length > 0:
                        indices = np.linspace(0, len(audio_array) - 1, target_length)
                        audio_array = np.interp(
                            indices, range(len(audio_array)), audio_array
                            ).astype(
                            'int16'
                            )  # logger.debug(f"🎤 重采样: {frame.sample_rate}Hz -> 16000Hz, 长度: {len(audio_array)}")
                    else:
                        # logger.debug(f"⚠️ 重采样长度为0: 原长度={len(audio_array)}, 目标长度={target_length}")
                        continue

                audio_data = audio_array.tobytes()
                # logger.debug(f"🎤 received audio data: {len(audio_data)} 字节")

                # 调用音频输入回调
                if self.audio_input_callback and len(audio_data) > 0:
                    self.audio_input_callback(audio_data)


        except Exception as e:
            logger.error(f"❌ 处理音频轨道错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            logger.info(f"🔚 音频轨道处理结束: {client_id}")

    def send_audio_to_client(self, client_id: str, audio_data: bytes, audio_type: AudioType):
        """发送音频数据给指定客户端"""
        if client_id in self.audio_tracks:
            try:
                # 检查客户端连接状态
                if client_id in self.peer_connections:
                    pc_state = self.peer_connections[
                        client_id].connectionState  # logger.debug(f"📡 向客户端 {client_id} 发送音频: {len(audio_data)}字节,
                    # 连接状态: {pc_state}")

                self.audio_tracks[client_id].add_audio_data(
                    audio_data, audio_type
                    )  # logger.debug(f"✅ 音频数据已发送给客户端: {client_id}")
            except Exception as e:
                logger.error(f"❌ 发送音频数据给客户端失败 {client_id}: {e}")
        else:
            logger.warning(f"⚠️ 客户端音频轨道不存在: {client_id}")

    def send_audio_to_all_clients(self, audio_data: bytes, audio_type: AudioType):
        """发送音频数据给所有客户端"""
        if not audio_data or len(audio_data) == 0:
            logger.debug("⚠️ 跳过空音频数据")
            return

        active_clients = list(self.audio_tracks.keys())
        if not active_clients:
            logger.debug("⚠️ 没有活跃的WebRTC客户端")
            return

        logger.debug(f"📡 向 {len(active_clients)} 个客户端发送音频数据: {len(audio_data)}字节")
        for client_id in active_clients:
            self.send_audio_to_client(client_id, audio_data, audio_type)

    def set_audio_input_callback(self, callback: Callable[[bytes], None]):
        """设置音频输入回调函数"""
        self.audio_input_callback = callback

    def set_client_connected_callback(self, callback: Callable[[str], None]):
        """设置客户端连接回调函数"""
        self.client_connected_callback = callback

    def get_client_count(self) -> int:
        """获取当前连接的客户端数量"""
        return len(self.peer_connections)

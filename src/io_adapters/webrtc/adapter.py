import asyncio
import logging
from asyncio import Queue

from av.audio import AudioFrame

from src.audio.processors import Ogg2PcmProcessor, PcmResamplerProcessor
from src.audio.processors.frame2pcm import Frame2PcmProcessor
from v2.audio.type import AudioType
from v2.config import VOLCENGINE_AUDIO_TYPE
from src.io_adapters.base import AdapterBase
from v2.adapters.io.webrtc.config import WebrtcConfig
from v2.constants import (
    VOLCENGINE_RECV_PCM_AUDIO_SAMPLE_RATE,
    VOLCENGINE_RECV_PCM_AUDIO_SOURCE_DTYPE,
    VOLCENGINE_SEND_AUDIO_SAMPLE_RATE,
    VOLCENGINE_SEND_AUDIO_SOURCE_DTYPE,
    )
from src.io_adapters.webrtc.webrtc_manager import WebRTCManager
from v2.volcengine import recv_pcm_audio_config

logger = logging.getLogger(__name__)


class WebRTCAdapter(AdapterBase):
    """WebRTC音频输入输出实现 - 声明式配置"""

    def __init__(self, config: WebrtcConfig):
        super().__init__()
        self.config = config
        self._webrtc_manager = None
        self._audio_input_queue = Queue()

        self.is_running = False

        # 初始化 WebRTC 管理器
        self._webrtc_manager = WebRTCManager(self.config)

        # 设置音频处理回调
        self._webrtc_manager.set_on_client_connected(self.on_client_connected)

        # 初始化音频处理器
        self.ogg2pcm = Ogg2PcmProcessor(recv_pcm_audio_config)
        self.pcm_resampler_server2client = PcmResamplerProcessor(
            VOLCENGINE_RECV_PCM_AUDIO_SAMPLE_RATE,
            VOLCENGINE_RECV_PCM_AUDIO_SOURCE_DTYPE,
            self.config.sample_rate,
            "int16"
            )

        self.frame2pcm = Frame2PcmProcessor(VOLCENGINE_SEND_AUDIO_SAMPLE_RATE, VOLCENGINE_SEND_AUDIO_SOURCE_DTYPE, 20)


    async def start(self) -> None:
        """在单独线程中启动 WebRTC 管理器"""
        if self.is_running: return
        self.is_running = True
        await self._webrtc_manager.start()

    async def on_get_next_server_chunk(self, chunk: bytes) -> None:
        """播放AI回复音频 (server2client)"""
        if not self.is_running or not chunk: return

        try:
            # processors
            if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
                chunk = self.ogg2pcm.process(chunk)
            chunk = self.pcm_resampler_server2client.process(chunk)

            # 发送到WebRTC客户端
            if self.first_server2client_track:
                await self.first_server2client_track.add_pcm_data(chunk)

        except Exception as e:
            logger.error(f"failed to get next server chunk, reason: {e}")

    async def get_next_client_chunk(self) -> bytes | None:
        """
        获取用户音频输入 (client2server)
        """
        try:
            if self.is_running and self.first_client2server_track:
                frame: AudioFrame = await asyncio.wait_for(self.first_client2server_track.recv(), timeout=1.0)
                chunk = self.frame2pcm.process(frame)
                return chunk
        except Exception as e:
            logger.debug(f"failed to get next client chunk, reason: {e}")

    async def on_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.debug(f"🔗 WebRTC客户端已连接: {client_id}")
        if self.on_prepared: await self.on_prepared()

    async def stop(self):
        """停止适配器"""
        logger.info("正在停止WebRTC适配器...")
        self.is_running = False
        if self._webrtc_manager:
            self._webrtc_manager.is_running = False

        # 等待WebRTC线程退出
        if hasattr(self, '_webrtc_thread') and self._webrtc_thread.is_alive():
            logger.info("等待WebRTC线程退出...")
            self._webrtc_thread.join(timeout=5.0)
            if self._webrtc_thread.is_alive():
                logger.warning("WebRTC线程未在超时时间内退出")

        logger.info("WebRTC适配器已停止")

    def display_welcome_screen(self) -> None:
        """显示WebRTC欢迎界面"""
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🌐 🤖  实时语音对话系统 (WebRTC模式)  🤖 🌐")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🌐 通过WebRTC接收浏览器音频输入")
        print("   • 🤖 AI助手会通过WebRTC返回音频回复")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print(
            f"🚀 WebRTC信令服务器已启动: {self.config['host']}:"
            f"{self.config['port']}"
            )
        print("请在浏览器中打开测试页面进行连接...")
        print("=" * 80 + "\n")
    @property
    def first_server2client_track(self):
        client_id = next(iter(self._webrtc_manager.server2client_tracks))
        server2client_track = self._webrtc_manager.server2client_tracks[client_id]
        return server2client_track

    @property
    def first_client2server_track(self):
        client_id = next(iter(self._webrtc_manager.client2server_tracks))
        client2server_track = self._webrtc_manager.client2server_tracks[client_id]
        return client2server_track

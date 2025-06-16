import asyncio
from asyncio import Queue

import numpy as np
from av.audio import AudioFrame

from src.audio.processors import Ogg2PcmProcessor, PcmResamplerProcessor
from src.audio.processors.frame2pcm import Frame2PcmProcessor
from src.audio.type import AudioType
from src.config import VOLCENGINE_AUDIO_TYPE
from src.io_adapters.base import AdapterBase
from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.webrtc.constants import VOLCENGINE_TTS_MODE_SAMPLE_RATE, VOLCENGINE_TTS_MODE_SOURCE_DTYPE
from src.io_adapters.webrtc.webrtc_manager import WebRTCManager
from src.utils.logger import logger
from src.volcengine.config import ogg_output_audio_config


class WebRTCAdapter(AdapterBase):
    """WebRTC音频输入输出实现 - 声明式配置"""

    def __init__(self, config: WebrtcConfig):
        super().__init__()
        self.config = config
        self._webrtc_manager = None
        self._prepared_triggered = False
        self._audio_input_queue = Queue()

        self.is_running = False
        # 初始化 WebRTC 管理器
        self._webrtc_manager = WebRTCManager(self.config)

        # 设置音频处理回调
        self._webrtc_manager.set_audio_input_callback(self._handle_webrtc_audio_input)
        self._webrtc_manager.set_client_connected_callback(self._handle_client_connected)

        # 初始化音频处理器
        self.ogg2pcm = Ogg2PcmProcessor(ogg_output_audio_config)
        self.pcm_resampler = PcmResamplerProcessor(
            VOLCENGINE_TTS_MODE_SAMPLE_RATE, VOLCENGINE_TTS_MODE_SOURCE_DTYPE, self.config.sample_rate, "int16"
            )
        self.frame2pcm = Frame2PcmProcessor(self.config.sample_rate, "int16", 20)

        # WebRTC 管理器将在外部异步启动  # 不在构造函数中同步启动，避免 asyncio.run() 冲突

    async def on_pull(self, chunk: bytes) -> None:
        """播放AI回复音频"""
        if not self.is_running or not chunk:
            return

        try:
            # 如果是 OGG 格式，转换为 PCM
            if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
                chunk = self.ogg2pcm.process(chunk)

            # 重采样：火山引擎TTS输出24kHz -> WebRTC需要16kHz
            chunk = self.pcm_resampler.process(chunk)

            # 发送到WebRTC客户端
            await self._webrtc_manager.handle_server2clients(chunk, VOLCENGINE_AUDIO_TYPE)
        except Exception as e:
            logger.error(f"处理音频输出失败: {e}")

    async def on_push(self) -> bytes | None:
        """获取用户音频输入"""
        if self.is_running:
            if not self._audio_input_queue.empty():
                frame: AudioFrame = await self._audio_input_queue.get()
                chunk = self.frame2pcm.process(frame)
                return chunk

    async def start(self) -> None:
        """在单独线程中启动 WebRTC 管理器"""
        if self.is_running: return
        self.is_running = True
        await self._webrtc_manager.start()

    async def _handle_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.debug(f"🔗 WebRTC客户端已连接: {client_id}")

        # 第一个客户端连接时触发prepared回调
        if not self._prepared_triggered:
            self._prepared_triggered = True
            logger.debug("🎯 WebRTC已准备就绪，触发prepared回调")
            if hasattr(self, '_on_prepared'):
                try:
                    if asyncio.iscoroutinefunction(self._on_prepared):
                        await self._on_prepared()
                    else:
                        self._on_prepared()
                except Exception as e:
                    logger.error(f"触发prepared回调失败: {e}")

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

    def _resample_audio(self, audio_data: bytes, source_rate: int, target_rate: int) -> bytes:
        """重采样音频数据"""
        if not audio_data or source_rate == target_rate:
            return audio_data

        try:
            # 将字节转换为numpy数组
            samples = np.frombuffer(audio_data, dtype=np.int16)

            # 计算重采样后的长度
            target_length = int(len(samples) * target_rate / source_rate)

            if target_length == 0:
                return b''

            # 使用线性插值重采样
            x_source = np.linspace(0, len(samples), len(samples))
            x_target = np.linspace(0, len(samples), target_length)
            resampled = np.interp(x_target, x_source, samples)

            # 转换回int16并返回字节
            return resampled.astype(np.int16).tobytes()
        except Exception as e:
            logger.warning(f"音频重采样失败: {e}")
            return audio_data

    async def _handle_webrtc_audio_input(self, audio_data: bytes) -> None:
        """
        处理WebRTC音频输入

        火山规定：客户端上传音频格式要求PCM（脉冲编码调制，未经压缩的的音频格式）、单声道、采样率16000、每个采样点用int16表示、字节序为小端序。
        浏览器已经配置为16kHz采样，无需重复采样
        """
        if not self.is_running or not audio_data:
            return

        try:
            await self._audio_input_queue.put(audio_data)
        except Exception as e:
            logger.debug(f"音频输入队列已满，丢弃数据: {e}")

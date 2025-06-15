import asyncio

import numpy as np
import pyaudio

from src.audio.processors import Ogg2PcmProcessor, PcmResamplerProcessor
from src.audio.processors.base import AudioProcessor
from src.audio.type import AudioType
from src.config import VOLCENGINE_AUDIO_TYPE
from src.io_adapters.base import AdapterBase
from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.webrtc.webrtc_manager import WebRTCManager
from src.utils.logger import logger


class WebRTCAdapter(AdapterBase):
    """WebRTC音频输入输出实现"""

    def __init__(self, config: WebrtcConfig):
        super().__init__(config)

        # 初始化WebRTC管理器
        self.webrtc_manager = WebRTCManager(**self.config)

        # 设置音频输入回调
        self.webrtc_manager.set_audio_input_callback(self._handle_webrtc_audio_input)

        # 设置客户端连接回调
        self.webrtc_manager.set_client_connected_callback(self._handle_client_connected)

        # 标记是否已经触发过prepared回调
        self._prepared_triggered = False

        # self.process

    def _build_audio_pipeline(self):
        """构建WebRTCAdapter的音频处理流水线"""

        class WebRTCSink(AudioProcessor):
            def __init__(self, adapter):
                self.adapter = adapter

            def process(self, audio_data: bytes) -> bytes:
                # 动态获取当前事件循环，而不是在初始化时获取
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        self.adapter.webrtc_manager.send_audio_to_all_clients(audio_data, AudioType.pcm), loop
                        )
                except RuntimeError:
                    # 如果没有运行中的事件循环，记录警告
                    logger.warning("没有运行中的事件循环，无法发送WebRTC音频数据")
                return b''

        pipeline = []

        # 步骤1: 如果输入是OGG，添加解码器
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            pipeline.append(Ogg2PcmProcessor(self.output_config))

        # 步骤2: 火山引擎TTS输出24kHz，WebRTC输出也用24kHz，无需重采样
        # 移除重采样步骤以减少延迟，AudioStreamTrack已调整为24kHz

        pipeline.append(WebRTCSink(self))
        self.audio_pipeline = pipeline

    async def start(self) -> None:
        logger.info("🌐 启动WebRTC音频输入输出...")
        self.is_running = True

        # 启动WebRTC管理器 (它内部不应该有阻塞循环)
        await self.webrtc_manager.start()

        # 显示欢迎界面
        self.display_welcome_screen()

        # 保持运行状态
        while self.is_running:
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        """停止WebRTC音频输入输出"""
        logger.info("🛑 停止WebRTC音频输入输出...")

        self.is_running = False

        # 清理音频处理流水线
        self._cleanup_pipeline()

        if self.webrtc_manager:
            # 确保WebRTC管理器也停止
            self.webrtc_manager.is_running = False
            await self.webrtc_manager.stop()

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

    def cleanup(self) -> None:
        """清理资源"""
        self._cleanup_pipeline()
        if self.webrtc_manager:
            try:
                asyncio.create_task(self.webrtc_manager.stop())
            except Exception as e:
                logger.error(f"清理WebRTC资源错误: {e}")

    def _handle_webrtc_audio_input(self, audio_data: bytes) -> None:
        """
        处理WebRTC音频输入

        火山规定：客户端上传音频格式要求PCM（脉冲编码调制，未经压缩的的音频格式）、单声道、采样率16000、每个采样点用int16表示、字节序为小端序。
        浏览器已经配置为16kHz采样，无需重复采样
        """
        if not self.is_running:
            return

        # 浏览器已配置为16kHz, int16, 单声道，直接使用
        # 移除重复的重采样步骤以减少延迟
        self._handle_audio_input(audio_data)

    def _handle_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.debug(f"🔗 WebRTC客户端已连接: {client_id}")

        # 第一个客户端连接时触发prepared回调
        if not self._prepared_triggered:
            self._prepared_triggered = True
            logger.debug("🎯 WebRTC已准备就绪，触发prepared回调")
            self._on_prepared()

import asyncio
import queue

from src.audio.processors import Ogg2PcmProcessor
from src.audio.processors.base import AudioProcessor
from src.audio.type import AudioType
from src.config import VOLCENGINE_AUDIO_TYPE
from src.io_adapters.base import AdapterBase
from src.io_adapters.system.system_audio_manager import SystemAudioManager, SystemAudioConfig
from src.utils.logger import logger
from src.volcengine.config import input_audio_config


class SystemAdapter(AdapterBase):
    """系统音频输入输出实现"""

    def __init__(self, config=None):
        super().__init__(config)

        # 初始化音频设备管理器
        config = SystemAudioConfig(input=self.input_audio_config, output=self.output_config)
        self.audio_device = SystemAudioManager(config)

        # 音频队列和播放流
        self.audio_queue = queue.Queue(maxsize=50)
        self.output_stream = None
        self.is_recording = False
        self.is_playing = False
        self.player_thread = None

        # 统计信息
        self.stats = {
            'audio_queue_overflows': 0
            }

    def _build_audio_pipeline(self):
        """构建SystemAdapter的音频处理流水线"""

        class SpeakerSink(AudioProcessor):
            def __init__(self, adapter):
                self.adapter = adapter

            def process(self, audio_data: bytes) -> bytes:
                if self.adapter.output_stream and not self.adapter.output_stream.is_stopped():
                    self.adapter.output_stream.write(audio_data)
                return b''  # 消费者不产生输出

        pipeline = []

        # 步骤1: 如果输入是OGG，添加解码器
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            pipeline.append(Ogg2PcmProcessor(self.output_config))

        # 步骤2: SystemAdapter 不需要额外的重采样，因为解码后的格式
        #         就已经是它需要的播放格式了。

        pipeline.append(SpeakerSink(self))
        self.audio_pipeline = pipeline

    async def start(self) -> None:
        logger.info("🎙️ 启动系统音频输入输出...")
        self.is_running = True
        self.is_recording = True

        # 1. 启动音频输出流
        self.output_stream = self.audio_device.open_output_stream()

        # 2. 显示欢迎界面和启动麦克风输入
        self.display_welcome_screen()
        self._on_prepared()
        await self._process_microphone_input()

    async def stop(self) -> None:
        """停止音频输入输出"""
        logger.info("🛑 停止系统音频输入输出...")

        self.is_running = False
        self.is_recording = False
        self.is_playing = False

        # 清理音频处理流水线
        self._cleanup_pipeline()

        # 可以向队列发送一个None来唤醒阻塞的get()
        self.audio_queue.put(None)

        # 等待播放线程结束
        if self.player_thread and self.player_thread.is_alive():
            self.player_thread.join(timeout=2.0)

    def display_welcome_screen(self) -> None:
        """显示欢迎界面"""
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🎙️ 🤖  实时语音对话系统  🤖 🎙️")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🎤 直接说话，系统会实时识别您的语音")
        print("   • 🤖 AI助手会语音回复，同时显示文字")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print("🚀 系统已就绪，请开始说话...")
        print("=" * 80 + "\n")

    def cleanup(self) -> None:
        """清理资源"""
        self._cleanup_pipeline()
        if self.audio_device:
            self.audio_device.cleanup()

    async def _process_microphone_input(self) -> None:
        """处理麦克风输入"""
        stream = self.audio_device.open_input_stream()
        logger.info("🎙️ 麦克风已就绪，开始监听...")

        while self.is_recording:
            try:
                audio_data = stream.read(input_audio_config["chunk"], exception_on_overflow=False)
                # save_pcm_to_wav(audio_data, "../../../output.wav")
                self._handle_audio_input(audio_data)
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"读取麦克风数据出错: {e}")
                await asyncio.sleep(0.1)

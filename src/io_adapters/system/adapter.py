import asyncio
import queue
import threading

from src.audio.opus_stream_decoder import OpusStreamDecoder
from src.audio.processor import OggDecodingStrategy, PcmPassThroughStrategy
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

    async def start(self) -> None:
        logger.info("🎙️ 启动系统音频输入输出...")
        self.is_running = True
        self.is_recording = True

        # 1. 启动音频输出流
        self.output_stream = self.audio_device.open_output_stream()

        # 2. 定义处理PCM数据的回调：写入系统扬声器
        def pcm_to_speaker(pcm_data: bytes):
            if self.output_stream and not self.output_stream.is_stopped():
                self.output_stream.write(pcm_data)

        # 3. 初始化并启动音频处理策略
        self._initialize_audio_processor(pcm_to_speaker)

        # ... (后续代码，如显示欢迎界面、启动麦克风输入) ...
        self.display_welcome_screen()
        self._on_prepared()
        await self._process_microphone_input()

    async def stop(self) -> None:
        """停止音频输入输出"""
        logger.info("🛑 停止系统音频输入输出...")

        self.is_running = False
        self.is_recording = False
        self.is_playing = False

        # 告诉策略停止
        if self.processing_strategy:
            self.processing_strategy.stop()

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

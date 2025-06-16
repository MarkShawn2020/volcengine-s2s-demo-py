from pyaudio import Stream

from src.audio.processors import Ogg2PcmProcessor
from src.audio.type import AudioType
from src.config import VOLCENGINE_AUDIO_TYPE
from src.io_adapters.base import AdapterBase
from src.io_adapters.system.system_audio_manager import SystemAudioManager
from src.volcengine.config import input_audio_config, ogg_output_audio_config


class SystemAdapter(AdapterBase):
    """系统音频输入输出实现 - 声明式配置"""

    def __init__(self, config=None):
        super().__init__(config)

        self._audio_device = SystemAudioManager()
        self._input_stream: Stream | None = None
        self._output_stream: Stream | None = None
        self.ogg2pcm = Ogg2PcmProcessor(ogg_output_audio_config)

        self.is_running = False

    async def start(self):
        self.is_running = True
        self._input_stream = self._audio_device.open_input_stream()
        self._output_stream = self._audio_device.open_output_stream()

    async def on_push(self) -> bytes | None:
        if self.is_running and self._input_stream.is_active():
            data = self._input_stream.read(input_audio_config.chunk, exception_on_overflow=False)
            return data

    async def on_pull(self, chunk: bytes) -> None:
        if self.is_running and self._output_stream.is_active():
            if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
                chunk = self.ogg2pcm.process(chunk)
            self._output_stream.write(chunk)

    async def stop(self):
        self.is_running = False
        if self._input_stream:
            self._input_stream.close()
        if self._output_stream:
            self._output_stream.close()

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

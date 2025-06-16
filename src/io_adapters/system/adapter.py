from pyaudio import Stream

from src.audio.processors import Ogg2PcmProcessor
from src.audio.processors.pcm_resampler import PcmResamplerProcessor
from src.audio.type import AudioType
from src.config import VOLCENGINE_AUDIO_TYPE, logger
from src.io_adapters.base import AdapterBase
from src.io_adapters.system.system_audio_manager import SystemAudioManager
from src.volcengine.config import send_audio_config, recv_pcm_audio_config


class SystemAdapter(AdapterBase):
    """系统音频输入输出实现 - 声明式配置"""

    def __init__(self, config=None):
        super().__init__(config)

        self._audio_device = SystemAudioManager()
        self._send_stream: Stream | None = None
        self._recv_stream: Stream | None = None
        self.is_running = False

        # 客户端音频处理管道：设备音频 -> 火山要求格式
        self.client2server_pipeline = []
        
        # 服务端音频处理管道：火山音频 -> 设备播放格式  
        self.server2client_pipeline = []


    async def start(self):
        self.is_running = True
        self._send_stream = self._audio_device.open_send_stream()
        self._recv_stream = self._audio_device.open_recv_stream()
        
        # 根据实际设备参数配置重采样器
        input_device = self._audio_device.pyaudio.get_default_input_device_info()
        input_sample_rate = int(input_device["defaultSampleRate"])
        logger.info(f"[send-sample-rate] input: {input_sample_rate}, sender: {send_audio_config.sample_rate}")

        # 如果设备采样率与火山要求不同，添加重采样器
        if input_sample_rate != send_audio_config.sample_rate:
            resampler = PcmResamplerProcessor(
                source_sr=input_sample_rate,
                source_dtype='int16',
                target_sr=send_audio_config.sample_rate,
                target_dtype='int16'
            )
            self.client2server_pipeline.append(resampler)

        # 配置服务端音频处理管道
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            self.server2client_pipeline.append(Ogg2PcmProcessor(recv_pcm_audio_config))

        # 为输出流添加重采样器：火山24kHz Float32 -> 设备采样率 Int16
        output_device = self._audio_device.pyaudio.get_default_output_device_info()
        output_sample_rate = int(output_device["defaultSampleRate"])
        logger.info(f"[recv-sample-rate] output: {output_sample_rate}, receive: {recv_pcm_audio_config.sample_rate}")

        if output_sample_rate != recv_pcm_audio_config.sample_rate:
            output_resampler = PcmResamplerProcessor(
                source_sr=recv_pcm_audio_config.sample_rate,  # 24kHz
                source_dtype='float32',
                target_sr=output_sample_rate,  # 设备采样率
                target_dtype='int16'
            )
            self.server2client_pipeline.append(output_resampler)
            
        if self.on_prepared: await self.on_prepared()

    async def get_next_client_chunk(self) -> bytes | None:
        if self.is_running and self._send_stream.is_active():
            chunk = self._send_stream.read(send_audio_config.chunk, exception_on_overflow=False)
            
            # 应用客户端音频处理管道
            for processor in self.client2server_pipeline:
                chunk = processor.process(chunk)
                
            return chunk

    async def on_get_next_server_chunk(self, chunk: bytes) -> None:
        if self.is_running and self._recv_stream.is_active():
            for processor in self.server2client_pipeline:
                chunk = processor.process(chunk)
            self._recv_stream.write(chunk)

    async def stop(self):
        self.is_running = False
        if self._send_stream:
            self._send_stream.close()
        if self._recv_stream:
            self._recv_stream.close()

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

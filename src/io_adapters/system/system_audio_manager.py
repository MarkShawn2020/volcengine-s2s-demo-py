from typing import Optional

import pyaudio

from src.types.audio import AudioConfig
from src.utils.logger import logger


class SystemAudioManager:
    """音频设备管理类，处理音频输入输出"""

    def __init__(self, input_config: AudioConfig, output_config: AudioConfig):
        self.input_config = input_config
        self.output_config = output_config
        self.pyaudio = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None

    def open_input_stream(self) -> pyaudio.Stream:
        """打开音频输入流"""
        # p = pyaudio.PyAudio()
        default_input_device = self.pyaudio.get_default_input_device_info()
        logger.info(f"🎤 输入设备: {default_input_device['name']}")
        self.input_stream = self.pyaudio.open(
            input_device_index=default_input_device['index'],
            channels=self.input_config.channels,
            rate=self.input_config.sample_rate,
            frames_per_buffer=self.input_config.chunk,
            format=self.input_config.bit_size,
            input=True,
            # Add low latency settings for AirPods compatibility
            input_host_api_specific_stream_info=None,
        )
        logger.debug(f"输入音频流已打开: {self.input_stream}")
        return self.input_stream

    def open_output_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        logger.info(f"🔊 输出设备: {default_output_device['name']}")
        self.output_stream = self.pyaudio.open(
            format=self.output_config.bit_size,
            channels=self.output_config.channels,
            rate=self.output_config.sample_rate,
            output=True,
            frames_per_buffer=self.output_config.chunk,
            output_device_index=default_output_device['index'],
        )
        return self.output_stream

    def cleanup(self) -> None:
        """清理音频设备资源"""
        for stream in [self.input_stream, self.output_stream]:
            if stream:
                stream.stop_stream()
                stream.close()
        self.pyaudio.terminate()

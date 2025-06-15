import json
import logging

import pyaudio
from typing_extensions import Optional, TypedDict

from src.audio.type import AudioConfig

logger = logging.getLogger(__name__)


class SystemAudioConfig(TypedDict):
    input: AudioConfig
    output: AudioConfig


class SystemAudioManager:
    """音频设备管理类，处理音频输入输出"""

    def __init__(self, config: SystemAudioConfig):
        logger.info("initializing")
        self.config = config
        self.pyaudio = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None
        logger.info("initialized")

    @property
    def input_config(self):
        return self.config['input']

    @property
    def output_config(self):
        return self.config['output']

    def open_input_stream(self) -> pyaudio.Stream:
        """打开音频输入流"""
        default_input_device = self.pyaudio.get_default_input_device_info()
        logger.info(f"opening input stream from device(name={default_input_device['name']})")
        params = {
            "input_device_index": default_input_device["index"],
            "channels": self.input_config.channels,
            "rate": self.input_config.sample_rate,
            "frames_per_buffer": self.input_config.chunk,
            "format": self.input_config.bit_size,
            "input": True,  # Add low latency settings for AirPods compatibility
            "input_host_api_specific_stream_info": None
            }
        logger.debug(f"输入参数：{json.dumps(params, indent=2)}")
        self.input_stream = self.pyaudio.open(**params)
        logger.info("opened input stream")
        return self.input_stream

    def open_output_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        logger.info(f"opening output stream from device(name={default_output_device['name']})")
        params = {
            "format": self.output_config.bit_size,
            "channels": self.output_config.channels,
            "rate": self.output_config.sample_rate,
            "output": True,
            "frames_per_buffer": self.output_config.chunk,
            "output_device_index": default_output_device["index"],
            }
        logger.debug(f"输出参数：{json.dumps(params, indent=2)}")
        self.output_stream = self.pyaudio.open(**params)
        logger.info("opened output stream")
        return self.output_stream

    def cleanup(self) -> None:
        """清理音频设备资源"""
        logger.info("cleaning")
        for (name, stream) in [("输入流", self.input_stream), ("输出流", self.output_stream)]:
            if stream:
                logger.info(f"closing {name}")
                stream.stop_stream()
                stream.close()
                logger.info(f"closed {name}")
            else:
                logger.info("skip closing %s", name)
        self.pyaudio.terminate()
        logger.info("cleaned up")

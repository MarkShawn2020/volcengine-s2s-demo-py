import json
import logging

import pyaudio
from typing_extensions import Optional

from src.volcengine.config import send_audio_config, recv_pcm_audio_config

logger = logging.getLogger(__name__)


class SystemAudioManager:
    """音频设备管理类，处理音频输入输出"""

    def __init__(self):
        logger.info("initializing")
        self.send_audio_config = send_audio_config
        self.recv_audio_config = recv_pcm_audio_config
        self.pyaudio = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None
        logger.info("initialized")

    def open_send_stream(self) -> pyaudio.Stream:
        """打开音频输入流"""
        default_input_device = self.pyaudio.get_default_input_device_info()
        logger.info(f"opening input stream from device(name={default_input_device['name']})")
        params = {
            "input_device_index": default_input_device["index"],
            "channels": self.send_audio_config.channels,
            "rate": self.send_audio_config.sample_rate,
            "frames_per_buffer": self.send_audio_config.chunk,
            "format": self.send_audio_config.bit_size,
            "input": True,  # Add low latency settings for AirPods compatibility
            "input_host_api_specific_stream_info": None
            }
        logger.debug(f"输入参数：{json.dumps(params, indent=2)}")
        self.input_stream = self.pyaudio.open(**params)
        logger.info("opened input stream")
        return self.input_stream

    def open_recv_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        logger.info(f"opening output stream from device(name={default_output_device['name']})")
        params = {
            "format": self.recv_audio_config.bit_size,
            "channels": self.recv_audio_config.channels,
            "rate": self.recv_audio_config.sample_rate,
            "output": True,
            "frames_per_buffer": self.recv_audio_config.chunk,
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

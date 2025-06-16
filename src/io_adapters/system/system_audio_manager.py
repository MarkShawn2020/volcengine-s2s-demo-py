import json
import logging

import pyaudio
from typing_extensions import Optional

from src.io_adapters.webrtc.constants import VOLCENGINE_SEND_AUDIO_SOURCE_DTYPE, VOLCENGINE_SEND_AUDIO_SAMPLE_RATE
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
        logger.info(f"opening input stream from default device: {default_input_device}")
        
        # 使用设备默认采样率和声道
        device_sample_rate = int(default_input_device["defaultSampleRate"])
        device_channels = min(default_input_device["maxInputChannels"], self.send_audio_config.channels)
        
        params = {
            "input_device_index": default_input_device["index"],
            "format": pyaudio.paInt16,
            # "format": self.send_audio_config.bit_size,
            "channels": 1,
            "rate": VOLCENGINE_SEND_AUDIO_SAMPLE_RATE,
            "frames_per_buffer": self.send_audio_config.chunk,
            "input": True,
            "input_host_api_specific_stream_info": None,

            }
        logger.debug(f"输入参数：{json.dumps(params, indent=2)}")
        self.input_stream = self.pyaudio.open(**params)
        logger.info("opened input stream")
        return self.input_stream

    def open_send_stream_with_callback(self, callback) -> pyaudio.Stream:
        """使用回调模式打开音频输入流"""
        default_input_device = self.pyaudio.get_default_input_device_info()
        logger.info(f"opening input stream with callback from default device: {default_input_device}")
        
        params = {
            "input_device_index": default_input_device["index"],
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": VOLCENGINE_SEND_AUDIO_SAMPLE_RATE,
            "frames_per_buffer": self.send_audio_config.chunk,
            "input": True,
            "stream_callback": callback,
            "start": True,  # 不自动启动，由外部控制
        }
        logger.debug(f"回调输入参数：{json.dumps({k: v for k, v in params.items() if k != 'stream_callback'}, indent=2)}")
        self.input_stream = self.pyaudio.open(**params)
        logger.info("opened input stream with callback")
        return self.input_stream

    def open_recv_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        logger.info(f"opening output stream from default device: {default_output_device}")
        
        # 使用设备默认采样率和声道
        device_sample_rate = int(default_output_device["defaultSampleRate"])
        device_channels = min(default_output_device["maxOutputChannels"], self.recv_audio_config.channels)
        
        params = {
            "format": pyaudio.paInt16,  # 确保使用Int16格式
            "channels": 1,  # 强制单声道，避免立体声问题
            "rate": device_sample_rate,
            "output": True,
            "frames_per_buffer": 1024,  # 添加合适的缓冲区大小
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

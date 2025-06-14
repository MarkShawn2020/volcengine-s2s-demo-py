import logging
from typing import Optional
import wave
import pyaudio
from dataclasses import dataclass

from . import config


# 配置日志
def setup_logging(level=logging.INFO):
    """配置日志系统"""
    # Python 3.7兼容性：移除已有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )

# 设置默认日志级别
setup_logging(logging.INFO)

# 创建音频管理器专用日志器
logger = logging.getLogger('AudioManager')

# 为不同模块设置不同的日志级别
def set_debug_mode(debug=False):
    """设置调试模式"""
    if debug:
        logger.setLevel(logging.DEBUG)
        setup_logging(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        setup_logging(logging.INFO)


@dataclass
class AudioConfig:
    """音频配置数据类"""
    format: str
    bit_size: int
    channels: int
    sample_rate: int
    chunk: int


class AudioDeviceManager:
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


def save_pcm_to_wav(pcm_data: bytes, filename: str) -> None:
    """保存PCM数据为WAV文件"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(config.input_audio_config["channels"])
        wf.setsampwidth(2)  # paInt16 = 2 bytes
        wf.setframerate(config.input_audio_config["sample_rate"])
        wf.writeframes(pcm_data)

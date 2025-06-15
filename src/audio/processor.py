# src/audio/processor.py (重构后)

import abc
import logging
import threading

import numpy as np
from scipy.signal import resample

from .opus_stream_decoder import OpusStreamDecoder

logger = logging.getLogger(__name__)


class AudioProcessor(abc.ABC):
    """音频处理模块的基类"""

    @abc.abstractmethod
    def process(self, audio_data: bytes) -> bytes:
        pass

    def flush(self) -> bytes | None:
        """处理内部可能剩余的缓冲数据"""
        return None

    def close(self):
        """清理资源"""
        pass


class AudioProcessingStrategy(abc.ABC):
    """音频处理策略的抽象基类 (接口)"""

    def __init__(self, output_config, pcm_output_callback):
        """
        :param output_config: 音频输出配置 (AudioConfig)
        :param pcm_output_callback: 一个函数，用于处理最终的PCM数据 (Callable[[bytes], None])
        """
        self.output_config = output_config
        self.pcm_output_callback = pcm_output_callback
        self.is_running = threading.Event()
        self.is_running.set()

    @abc.abstractmethod
    def process_input(self, audio_data: bytes):
        """处理输入的音频数据（可能是 OGG 或 PCM）"""
        pass

    @abc.abstractmethod
    def start(self):
        """启动策略可能需要的后台任务"""
        pass

    @abc.abstractmethod
    def stop(self):
        """停止策略并清理资源"""
        pass


# --- 策略一：OGG 解码 ---
class OggDecodingStrategy(AudioProcessingStrategy):
    def __init__(self, output_config, pcm_output_callback):
        super().__init__(output_config, pcm_output_callback)
        self.decoder = OpusStreamDecoder(
            output_sample_rate=self.output_config.sample_rate,
            output_channels=self.output_config.channels,
            pyaudio_format=self.output_config.bit_size
            )
        self.consumer_thread = None

    def start(self):
        # 启动一个消费者线程，从解码器获取PCM并调用回调
        self.consumer_thread = threading.Thread(target=self._consume_decoded_pcm)
        self.consumer_thread.daemon = True
        self.consumer_thread.start()

    def _consume_decoded_pcm(self):
        logger.info("PCM 消费者线程已启动。")
        while self.is_running.is_set():
            pcm_data = self.decoder.get_decoded_pcm(block=True, timeout=1.0)
            if pcm_data:
                self.pcm_output_callback(pcm_data)
            elif not self.decoder._is_running.is_set() and self.decoder.pcm_queue.empty():
                logger.info("解码器已停止，退出 PCM 消费循环。")
                break
        logger.info("PCM 消费者线程已结束。")

    def process_input(self, audio_data: bytes):
        """将OGG数据喂给解码器"""
        if self.decoder and self.decoder._is_running.is_set():
            self.decoder.feed_ogg_data(audio_data)

    def stop(self):
        logger.info("正在停止 OGG 解码策略...")
        self.is_running.clear()
        if self.decoder:
            self.decoder.close()
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=2)
        logger.info("OGG 解码策略已停止。")


# --- 策略二：PCM 直通 ---
class PcmPassThroughStrategy(AudioProcessingStrategy):
    def start(self):
        # PCM直通不需要后台线程
        logger.info("PCM 直通策略已启动。")
        pass

    def process_input(self, audio_data: bytes):
        """直接调用回调函数处理PCM数据"""
        self.pcm_output_callback(audio_data)

    def stop(self):
        logger.info("正在停止 PCM 直通策略...")
        self.is_running.clear()
        logger.info("PCM 直通策略已停止。")


class PcmResamplerProcessor(AudioProcessor):
    def __init__(self, source_sr, source_dtype, target_sr, target_dtype='int16'):
        self.source_sr = source_sr
        self.source_dtype = source_dtype
        self.target_sr = target_sr
        self.target_dtype = target_dtype
        # 维持一个小的缓冲区来处理跨块的音频，避免边界效应
        self._buffer = np.array([], dtype=np.float32)

    def process(self, audio_data: bytes) -> bytes:
        if not audio_data:
            return b''

        # 字节转 Numpy
        new_samples = np.frombuffer(audio_data, dtype=self.source_dtype)

        # 将新样本添加到缓冲区
        # 确保是 float32 以便处理
        self._buffer = np.concatenate([self._buffer, new_samples.astype(np.float32)])

        num_source_samples = len(self._buffer)

        # 计算可以输出多少目标样本
        # 注意：scipy.signal.resample 的第二个参数是输出样本数
        num_target_samples = int(num_source_samples * self.target_sr / self.source_sr)

        if num_target_samples == 0:
            return b''  # 缓冲区数据太少，还不够一个输出样本

        # 使用 scipy 进行高质量重采样
        resampled_samples = resample(self._buffer, num_target_samples)

        # 清空缓冲区，因为它已经被完全处理
        # 在流式应用中，更好的做法是保留一小部分重叠，但这里先简化
        self._buffer = np.array([], dtype=np.float32)

        # 转换到目标数据类型
        if self.target_dtype == 'int16':
            if resampled_samples.dtype.kind == 'f':
                resampled_samples = (np.clip(resampled_samples, -1.0, 1.0) * 32767).astype(np.int16)

        return resampled_samples.tobytes()

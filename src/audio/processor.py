# src/audio/processor.py (重构后)

import abc
import queue
import threading
import logging
from .opus_stream_decoder import OpusStreamDecoder

logger = logging.getLogger(__name__)

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
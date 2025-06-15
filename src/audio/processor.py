import abc
import queue
import threading
import logging

from src.audio.opus_stream_decoder import OpusStreamDecoder

logger = logging.getLogger(__name__)


class AudioProcessingStrategy(abc.ABC):
    """音频处理策略的抽象基类 (接口)"""

    def __init__(self, player_instance):
        self.player = player_instance
        self.is_running = threading.Event()
        self.is_running.set()

    @abc.abstractmethod
    def start(self):
        """启动策略所需的所有后台任务"""
        pass

    @abc.abstractmethod
    def stop(self):
        """停止策略并清理资源"""
        pass

# --- 策略一：PCM 直通 ---
class PcmPassThroughStrategy(AudioProcessingStrategy):
    def start(self):
        """直接从主队列获取PCM数据并播放"""
        logger.info("开始直接播放 PCM 数据...")
        while self.is_running.is_set():
            try:
                pcm_data = self.player.audio_queue.get(timeout=1.0)
                if pcm_data:
                    self.player.output_stream.write(pcm_data)
                else:  # 收到结束信号
                    logger.info("收到结束信号，退出 PCM 播放循环。")
                    break
            except queue.Empty:
                continue

    def stop(self):
        logger.info("正在停止 PCM 直通策略...")
        self.is_running.clear()
        logger.info("PCM 直通策略已停止。")

# --- 策略二：OGG 解码 ---
class OggDecodingStrategy(AudioProcessingStrategy):
    def __init__(self, player_instance):
        super().__init__(player_instance)
        self.decoder = OpusStreamDecoder(
            output_sample_rate=self.player.output_config['sample_rate'],
            output_channels=self.player.output_config['channels'],
            pyaudio_format=self.player.output_config['bit_size']
            )
        self.feeder_thread = None

    def _feed_decoder(self):
        """后台线程，从主队列获取OGG数据并喂给解码器"""
        logger.info("OGG 喂食线程已启动。")
        while self.is_running.is_set():
            try:
                ogg_data = self.player.audio_queue.get(timeout=1.0)
                if ogg_data:
                    self.decoder.feed_ogg_data(ogg_data)
                else:  # 收到结束信号
                    break
            except queue.Empty:
                continue
        logger.info("OGG 喂食线程已结束。")
        self.decoder.close()

    def start(self):
        """启动解码器和喂食线程，并开始播放循环"""
        self.feeder_thread = threading.Thread(target=self._feed_decoder)
        self.feeder_thread.daemon = True
        self.feeder_thread.start()

        logger.info("开始从解码器获取 PCM 数据并播放...")
        while self.is_running.is_set():
            # 这里的 is_running 由外部的 player 控制
            pcm_data = self.decoder.get_decoded_pcm(block=True, timeout=1.0)
            if pcm_data:
                self.player.output_stream.write(pcm_data)
            # 检查解码器是否已自行停止
            elif not self.decoder._is_running.is_set() and self.decoder.pcm_queue.empty():
                logger.info("解码器已停止，退出 OGG 播放循环。")
                break

    def stop(self):
        logger.info("正在停止 OGG 解码策略...")
        self.is_running.clear()
        if self.decoder:
            self.decoder.close()
        if self.feeder_thread and self.feeder_thread.is_alive():
            self.feeder_thread.join(timeout=2)
        logger.info("OGG 解码策略已停止。")

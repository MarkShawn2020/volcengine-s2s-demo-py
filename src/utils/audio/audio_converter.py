import io

import numpy as np
from pydub import AudioSegment

from src.utils.logger import logger


class OggToPcmConverter:
    """OGG转PCM流式转换器"""

    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        """
        初始化转换器

        Args:
            sample_rate: 目标采样率
            channels: 目标声道数
        """
        self.sample_rate = sample_rate
        self.channels = channels

        # OGG 流缓存
        self.ogg_buffer = bytearray()
        self.last_pcm_size = 0  # 记录上次解码的PCM数据大小

        # 统计信息
        self.stats = {
            'ogg_pages_received': 0,
            'pcm_bytes_decoded': 0,
            'decoding_errors': 0
        }

    def convert(self, ogg_page: bytes) -> bytes:
        """
        处理 OGG 流式数据 - 改进的增量解码版本

        Args:
            ogg_page: OGG音频页面数据

        Returns:
            转换后的PCM数据
        """
        # 将新的 OGG 页面添加到缓冲区
        self.ogg_buffer.extend(ogg_page)
        self.stats['ogg_pages_received'] += 1
        if len(self.ogg_buffer) % 5000 < len(ogg_page):  # 每5KB输出一次日志
            logger.debug(f"🔊 接收音频流: {len(self.ogg_buffer)}字节")

        # 尝试解码当前缓冲区的音频流
        try:
            audio = AudioSegment.from_file(io.BytesIO(bytes(self.ogg_buffer)), format="ogg")

            # 转换为目标格式
            audio = audio.set_frame_rate(self.sample_rate)
            audio = audio.set_channels(self.channels)
            audio = audio.set_sample_width(2)  # int16 = 2 bytes

            full_pcm_data = audio.raw_data

            if len(full_pcm_data) > 0:
                # 计算新增的PCM数据 - 使用更精确的方法
                if hasattr(self, 'last_pcm_size') and self.last_pcm_size > 0:
                    # 直接从上次的PCM数据长度开始截取
                    if len(full_pcm_data) > self.last_pcm_size:
                        new_pcm_data = full_pcm_data[self.last_pcm_size:]
                        # 更新已解码的PCM数据长度
                        self.last_pcm_size = len(full_pcm_data)

                        if len(new_pcm_data) > 0:
                            # 验证音频数据质量
                            validated_data = self._validate_pcm_data(new_pcm_data)
                            if len(validated_data) > 0:
                                self.stats['pcm_bytes_decoded'] += len(validated_data)
                                logger.debug(f"🎵 解码音频: {len(validated_data)}字节")
                                return validated_data
                    else:
                        # 没有新数据
                        return b''
                else:
                    # 第一次解码
                    self.last_pcm_size = len(full_pcm_data)
                    # 验证音频数据质量
                    validated_data = self._validate_pcm_data(full_pcm_data)
                    if len(validated_data) > 0:
                        self.stats['pcm_bytes_decoded'] += len(validated_data)
                        logger.debug(f"🎵 首次解码: {len(validated_data)}字节")
                        return validated_data

        except Exception as e:
            # 解码失败，记录统计
            self.stats['decoding_errors'] += 1
            # 检查是否是因为缓冲区数据不完整导致的失败
            if len(self.ogg_buffer) < 1000:  # 如果缓冲区很小，可能需要更多数据
                logger.debug("等待更多OGG数据进行解码")
            else:
                # 缓冲区较大但解码失败，可能是数据损坏
                logger.debug(f"OGG解码失败，缓冲区大小: {len(self.ogg_buffer)}")

        # 缓冲区管理：如果过大则保留最近的有效OGG数据
        self._manage_buffer()

        # 返回空数据，等待更多OGG页面
        return b''

    def _validate_pcm_data(self, pcm_data: bytes) -> bytes:
        """验证和过滤PCM数据，防止爆炸嗞音"""
        if len(pcm_data) == 0:
            return b''

        # 检查数据长度是否为样本大小的倍数
        sample_size = 2  # int16 = 2 bytes
        if len(pcm_data) % sample_size != 0:
            # 截断到最近的样本边界
            pcm_data = pcm_data[:len(pcm_data) - (len(pcm_data) % sample_size)]

        if len(pcm_data) < sample_size:
            return b''

        # 转换为numpy数组进行分析
        try:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)

            # 检查是否有异常大的音量峰值（可能的爆炸音）
            max_amplitude = np.max(np.abs(audio_array))
            if max_amplitude > 25000:  # 接近int16最大值32767的阈值
                logger.debug(f"检测到异常音量峰值: {max_amplitude}，进行音量限制")
                # 进行音量限制
                audio_array = np.clip(audio_array, -25000, 25000)

            # 检查是否有大量的零值（可能的静音段）
            zero_ratio = np.count_nonzero(audio_array == 0) / len(audio_array)
            if zero_ratio > 0.95:  # 95%以上都是零值
                logger.debug("检测到大量静音数据，跳过播放")
                return b''

            # 返回处理后的数据
            return audio_array.tobytes()

        except Exception as e:
            logger.error(f"PCM数据验证失败: {e}")
            return pcm_data  # 验证失败时返回原始数据

    def _manage_buffer(self):
        """管理OGG缓冲区大小"""
        max_buffer_size = 200000  # 200KB
        if len(self.ogg_buffer) > max_buffer_size:
            # 寻找最后一个完整的OGG页面边界
            last_ogg_start = self.ogg_buffer.rfind(b'OggS')
            if last_ogg_start > 0:
                # 从最后一个OGG页面开始保留
                self.ogg_buffer = self.ogg_buffer[last_ogg_start:]
                # 重置PCM计数，因为缓冲区被截断了
                self.last_pcm_size = 0
                logger.debug(f"OGG缓冲区过大，从最后页面保留 {len(self.ogg_buffer)} 字节")
            else:
                # 清空缓冲区重新开始
                self.ogg_buffer.clear()
                self.last_pcm_size = 0
                logger.debug("OGG缓冲区过大且无有效页面，重置缓冲区")

    def reset(self):
        """重置转换器状态"""
        self.ogg_buffer.clear()
        self.last_pcm_size = 0
        logger.debug("OGG转换器已重置")

    def get_stats(self) -> dict:
        """获取转换器统计信息"""
        return self.stats.copy()

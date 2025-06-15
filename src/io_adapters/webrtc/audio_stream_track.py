import asyncio
import queue

import numpy as np
from aiortc import MediaStreamTrack

from src.audio.type import AudioType
from src.utils.logger import logger


class AudioStreamTrack(MediaStreamTrack):
    """自定义音频流轨道，用于发送音频数据给浏览器"""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self.audio_queue = queue.Queue(maxsize=200)  # 适中的队列大小，避免音频丢失
        self._timestamp = 0
        self._sample_rate = 48000  # 48kHz，与浏览器匹配
        self._samples_per_frame = int(self._sample_rate * 0.02)  # 20ms frames
        self._is_running = True

    def stop(self):
        """停止音频轨道"""
        self._is_running = False
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    async def recv(self):
        """接收音频帧"""
        # 如果已停止，返回空帧
        if not self._is_running:
            return None

        try:
            # 从队列获取预处理的OPUS帧数据
            frame_data = await asyncio.get_event_loop().run_in_executor(None, self.audio_queue.get, True, 1.0)
            # logger.debug(f"🎧 从队列获取OPUS帧数据: {len(frame_data) if frame_data else 0}字节")

            if frame_data is None or len(frame_data) == 0:
                # 生成静音帧
                samples = np.zeros(960, dtype=np.int16)  # logger.debug(f"🔇 生成静音帧: 960样本")
            else:
                # 直接使用预处理的int16数据
                samples = np.frombuffer(frame_data, dtype=np.int16)  # logger.debug(f"🎵 使用预处理帧: {len(samples)}样本")

            # 创建音频帧
            from av import AudioFrame
            from fractions import Fraction

            frame = AudioFrame(format="s16", layout="mono", samples=960)
            frame.sample_rate = 48000

            # 计算时间戳
            import time
            current_time = time.time()
            if not hasattr(self, '_start_time'):
                self._start_time = current_time
                self._timestamp = 0

            frame.pts = self._timestamp
            frame.time_base = Fraction(1, 48000)

            # 填充音频数据（确保960样本）
            if len(samples) < 960:
                padding = np.zeros(960 - len(samples), dtype=np.int16)
                samples = np.concatenate([samples, padding])
            elif len(samples) > 960:
                samples = samples[:960]

            frame.planes[0].update(samples.tobytes())
            self._timestamp += 960

            # logger.debug(f"🎵 创建OPUS帧: 960样本, PTS={frame.pts}")
            return frame

        except queue.Empty:
            # 如果队列为空，生成静音帧
            samples = np.zeros(self._samples_per_frame, dtype=np.int16)
            from av import AudioFrame
            from fractions import Fraction
            frame = AudioFrame(format="s16", layout="mono", samples=self._samples_per_frame)
            frame.sample_rate = self._sample_rate
            frame.pts = self._timestamp
            frame.time_base = Fraction(1, self._sample_rate)
            frame.planes[0].update(samples.tobytes())
            self._timestamp += self._samples_per_frame
            return frame
        except Exception as e:
            logger.debug(f"音频帧生成错误: {e}")
            # 返回静音帧
            samples = np.zeros(self._samples_per_frame, dtype=np.int16)
            from av import AudioFrame
            from fractions import Fraction
            frame = AudioFrame(format="s16", layout="mono", samples=self._samples_per_frame)
            frame.sample_rate = self._sample_rate
            frame.pts = self._timestamp
            frame.time_base = Fraction(1, self._sample_rate)
            frame.planes[0].update(samples.tobytes())
            self._timestamp += self._samples_per_frame
            return frame

    def add_audio_data(self, audio_data: bytes, audio_type: AudioType):
        """添加音频数据到发送队列，分割成OPUS帧"""
        if not self._is_running:
            return

        try:
            # 处理音频数据并分割成多个OPUS帧
            self._process_and_split_audio(audio_data, audio_type)
        except Exception as e:
            logger.error(f"❌ 处理音频数据失败: {e}")

    def _process_and_split_audio(self, audio_data: bytes, audio_type: AudioType):
        if audio_type == AudioType.pcm:
            self.audio_queue.put_nowait(audio_data)
            return

        """处理音频数据并分割成OPUS标准帧"""
        # 自动检测音频格式并解析
        if len(audio_data) % 4 == 0 and len(audio_data) % 2 == 0:
            # 尝试float32格式（火山引擎TTS原生格式）
            try:
                samples_f32 = np.frombuffer(audio_data, dtype=np.float32)
                max_val = np.max(np.abs(samples_f32)) if len(samples_f32) > 0 else 0.0

                if 0.001 <= max_val <= 1.5:  # float32典型范围
                    samples = np.clip(samples_f32, -1.0, 1.0)
                    samples = (samples * 32767).astype('int16')
                    logger.debug(f"🔍 检测为float32格式: {len(audio_data)}字节, 最大值={max_val:.6f}")
                else:
                    # 可能是int16格式（OGG转换后）
                    samples = np.frombuffer(audio_data, dtype=np.int16)
                    logger.debug(
                        f"🔍 检测为int16格式: {len(audio_data)}字节, 最大值={np.max(np.abs(samples)) if len(samples) > 0 else 0}"
                        )
            except Exception:
                # 解析失败，按int16处理
                samples = np.frombuffer(audio_data[:len(audio_data) // 2 * 2], dtype=np.int16)
                logger.debug(f"🔍 解析失败，按int16处理: {len(audio_data)}字节")
        else:
            # 长度不是4的倍数，只能是int16
            samples = np.frombuffer(audio_data[:len(audio_data) // 2 * 2], dtype=np.int16)
            logger.debug(f"🔍 按int16处理: {len(audio_data)}字节")

        # 重采样到48kHz (从24kHz)
        target_length = int(len(samples) * 48000 / 24000)
        if target_length > 0:
            indices = np.linspace(0, len(samples) - 1, target_length)
            samples = np.interp(indices, range(len(samples)), samples).astype('int16')

        # 分割成960样本的OPUS帧
        opus_frame_size = 960
        for i in range(0, len(samples), opus_frame_size):
            frame_samples = samples[i:i + opus_frame_size]

            # 如果不足960样本，填充零
            if len(frame_samples) < opus_frame_size:
                padding = np.zeros(opus_frame_size - len(frame_samples), dtype=np.int16)
                frame_samples = np.concatenate([frame_samples, padding])

            # 将帧数据转换为bytes并加入队列
            frame_bytes = frame_samples.tobytes()

            # 清理旧数据避免延迟累积
            while self.audio_queue.qsize() > 100:
                try:
                    self.audio_queue.get_nowait()  # logger.debug("清理旧音频数据以减少延迟")
                except queue.Empty:
                    break

            try:
                self.audio_queue.put_nowait(
                    frame_bytes
                    )
                # logger.debug(f"添加OPUS帧到队列: {len(frame_bytes)}字节，队列大小: {self.audio_queue.qsize()}")
            except queue.Full:
                logger.debug("⚠️ 音频发送队列已满，丢弃数据")
                break

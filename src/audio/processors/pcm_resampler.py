import numpy as np
from scipy.signal import resample

from src.audio.processors.base import AudioProcessor


class PcmResamplerProcessor(AudioProcessor):
    """一个无状态的处理器，负责重采样和格式转换。"""

    def __init__(self, source_sr: int, source_dtype: str, target_sr: int, target_dtype='int16'):
        self.source_sr = source_sr
        self.source_dtype = source_dtype
        self.target_sr = target_sr
        self.target_dtype = target_dtype

    def process(self, audio_data: bytes) -> bytes:
        if not audio_data:
            return b''

        # 1. 字节转Numpy
        samples = np.frombuffer(audio_data, dtype=self.source_dtype)

        # 2. 如果需要，重采样
        if self.source_sr != self.target_sr:
            # 使用scipy进行重采样
            samples = samples.astype(np.float32)
            num_target_samples = int(len(samples) * self.target_sr / self.source_sr)
            samples = resample(samples, num_target_samples)

        # 3. 转换到目标数据类型
        if self.target_dtype == 'int16':
            if samples.dtype.kind == 'f':
                samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)

        return samples.tobytes()

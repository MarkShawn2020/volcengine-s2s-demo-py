# src/audio/input_processor.py (新建文件)
import logging

import numpy as np

logger = logging.getLogger(__name__)


class AudioFrameProcessor:
    """
    处理输入的音频帧（例如从WebRTC），将其转换为目标格式。
    """

    def __init__(self, target_sample_rate: int = 16000, target_dtype: str = 'int16', buffer_duration_ms: int = 50):
        self.target_sample_rate = target_sample_rate
        self.target_dtype = target_dtype
        self.buffer_duration_ms = buffer_duration_ms

        # 音频缓冲区 - 累积小的音频块
        self.buffer = np.array([], dtype=np.int16)
        self.min_buffer_samples = int(target_sample_rate * buffer_duration_ms / 1000)  # 例如100ms的音频

        logger.info(
            f"音频输入处理器已初始化: "
            f"目标采样率={target_sample_rate}Hz, 目标格式={target_dtype}, "
            f"缓冲时长={buffer_duration_ms}ms ({self.min_buffer_samples} samples)"
            )

    def process_frame(self, frame) -> bytes | None:
        """
        处理一个 av.AudioFrame 对象。
        - 转换为 NumPy 数组
        - 确保单声道
        - 重采样到目标速率
        - 转换到目标数据类型
        - 返回字节流
        """
        if frame is None:
            return None

        audio_array = frame.to_ndarray()
        if audio_array.size == 0:
            return None

        # 1. 确保单声道 (取第一个通道或平均)
        if audio_array.shape[0] > 1:
            # logger.debug(f"输入为多声道 ({audio_array.shape[0]})，取第一个通道。")
            audio_array = audio_array[0, :]
        else:
            audio_array = audio_array.flatten()

        # 2. 重采样
        source_sample_rate = frame.sample_rate
        if source_sample_rate != self.target_sample_rate:
            if source_sample_rate == 0:
                logger.warning("音频帧采样率为0，无法重采样，跳过。")
                return None

            num_source_samples = len(audio_array)
            num_target_samples = int(num_source_samples * self.target_sample_rate / source_sample_rate)

            if num_target_samples == 0:
                return None

            # 使用线性插值进行重采样
            x_source = np.linspace(0, 1, num=num_source_samples)
            x_target = np.linspace(0, 1, num=num_target_samples)
            audio_array = np.interp(x_target, x_source, audio_array)
            # logger.debug(f"重采样: {source_sample_rate}Hz -> {self.target_sample_rate}Hz")

        # 3. 转换数据类型
        if audio_array.dtype.kind == 'f':  # 如果是浮点数
            if self.target_dtype == 'int16':
                audio_array = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
        elif audio_array.dtype != self.target_dtype:  # 如果是其他整数类型
            audio_array = audio_array.astype(self.target_dtype)

        # 4. 添加到缓冲区
        self.buffer = np.concatenate([self.buffer, audio_array])

        # 5. 检查是否有足够的数据输出
        if len(self.buffer) >= self.min_buffer_samples:
            # 输出缓冲区中的数据
            output_samples = self.buffer[:self.min_buffer_samples]
            self.buffer = self.buffer[self.min_buffer_samples:]  # 保留剩余部分

            result = output_samples.tobytes()
            duration_ms = len(output_samples) / self.target_sample_rate * 1000

            # 添加音频质量检查
            max_amplitude = np.max(np.abs(output_samples)) if len(output_samples) > 0 else 0
            rms = np.sqrt(np.mean(output_samples.astype(np.float32) ** 2)) if len(output_samples) > 0 else 0

            # logger.debug(f"🎤 AudioFrameProcessor输出(缓冲): RMS={rms:.1f}")

            return result
        else:
            # 缓冲区数据不足，不输出
            # logger.debug(f"🎤 缓冲区累积中: {len(self.buffer)}/{self.min_buffer_samples} samples")
            return None

    def flush(self) -> bytes | None:
        """刷新缓冲区，输出所有剩余的音频数据"""
        if len(self.buffer) > 0:
            result = self.buffer.tobytes()
            duration_ms = len(self.buffer) / self.target_sample_rate * 1000
            logger.info(
                f"🎤 AudioFrameProcessor刷新: {len(result)} bytes, {len(self.buffer)} samples, {duration_ms:.1f}ms"
                )
            self.buffer = np.array([], dtype=np.int16)  # 清空缓冲区
            return result
        return None

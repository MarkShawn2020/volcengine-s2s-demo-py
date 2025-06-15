# src/audio/input_processor.py (新建文件)
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AudioFrameProcessor:
    """
    处理输入的音频帧（例如从WebRTC），将其转换为目标格式。
    """

    def __init__(self, target_sample_rate: int = 16000, target_dtype: str = 'int16'):
        self.target_sample_rate = target_sample_rate
        self.target_dtype = target_dtype
        logger.info(
            f"音频输入处理器已初始化: "
            f"目标采样率={target_sample_rate}Hz, 目标格式={target_dtype}"
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
                audio_array = (audio_array * 32767).astype(np.int16)
        elif audio_array.dtype != self.target_dtype:  # 如果是其他整数类型
            audio_array = audio_array.astype(self.target_dtype)

        return audio_array.tobytes()
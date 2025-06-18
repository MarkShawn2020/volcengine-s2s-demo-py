import struct


def calculate_volume(audio_data: bytes) -> float:
    """计算音频数据的音量（RMS）"""
    if len(audio_data) == 0:
        return 0.0

    # 将bytes转换为int16数组
    audio_samples = struct.unpack(f'{len(audio_data) // 2}h', audio_data)

    # 计算RMS音量
    squares = [sample ** 2 for sample in audio_samples]
    mean_square = sum(squares) / len(squares)
    rms = (mean_square ** 0.5)

    # 归一化到0-1范围
    return min(rms / 32767.0, 1.0)

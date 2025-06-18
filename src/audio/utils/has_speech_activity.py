from src.audio.utils.calculate_volume import calculate_volume


def has_speech_activity(audio_data: bytes, threshold: float = 0.01) -> bool:
    """检测音频中是否有语音活动"""
    volume = calculate_volume(audio_data)
    return volume > threshold

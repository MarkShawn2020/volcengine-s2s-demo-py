def detect_audio_format(audio_data: bytes) -> str:
    """
    检测音频格式

    Args:
        audio_data: 音频数据

    Returns:
        音频格式 ("ogg" 或 "pcm")
    """
    if len(audio_data) < 4:
        return "pcm"

    # 检查 OGG 文件头 (4F 67 67 53)
    if audio_data[:4] == b'OggS':
        return "ogg"

    # 检查 WebM 文件头 (1A 45 DF A3)
    if audio_data[:4] == b'\x1A\x45\xDF\xA3':
        return "ogg"  # WebM 也用 OGG 解码器处理

    # 检查 Opus 在 OGG 中的特征
    if b'OpusHead' in audio_data[:64]:
        return "ogg"

    # 默认为 PCM
    return "pcm"

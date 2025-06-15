import wave

import src.volcengine.config


def save_pcm_to_wav(pcm_data: bytes, filename: str) -> None:
    """保存PCM数据为WAV文件"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(src.volcengine.config.input_audio_config["channels"])
        wf.setsampwidth(2)  # paInt16 = 2 bytes
        wf.setframerate(src.volcengine.config.input_audio_config["sample_rate"])
        wf.writeframes(pcm_data)

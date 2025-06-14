import uuid
import pyaudio
import os

# 配置信息
ws_connect_config = {
    "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
    "headers": {
        "X-Api-App-ID": os.getenv("VOLC_APP_ID"),
        "X-Api-Access-Key": os.getenv("VOLC_ACCESS_KEY"),
        "X-Api-Resource-Id": "volc.speech.dialog",
        "X-Api-App-Key": os.getenv("VOLC_APP_KEY"),
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
}

start_session_req = {
    # "tts": {
    #     "audio_config": {
    #         "channel": 1,
    #         "format": "pcm",
    #         "sample_rate": 24000
    #     },
    # },
    "dialog": {
        "bot_name": "豆包",
    }
}

input_audio_config = {
    "chunk": 3200,
    "format": "pcm",
    "channels": 1,
    "sample_rate": 16000,
    "bit_size": pyaudio.paInt16
}

output_audio_config = {
    "chunk": 3200,
    "format": "pcm",
    "channels": 1,
    "sample_rate": 24000,
    "bit_size": pyaudio.paInt16  # 改为 int16 避免格式转换问题
}

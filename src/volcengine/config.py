import os
import uuid

import pyaudio

ws_connect_config = {
    "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
    "headers": {
        "X-Api-App-ID": os.environ["VOLCENGINE_APP_ID"],
        "X-Api-Access-Key": os.environ["VOLCENGINE_ACCESS_TOKEN"],
        "X-Api-Resource-Id": "volc.speech.dialog",
        "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
}

"""
【重要】
- bitsize（如果指定tts回复，则要f32，否则i16）
- chunk 在使用耳机的时候，要低于1600
- channels 始终为 1 即可
"""
input_audio_config = {
    "bit_size": pyaudio.paInt16,
    "chunk": 1600,
    "format": "pcm",
    "channels": 1,
    "sample_rate": 16000,
}
ogg_output_audio_config = {
    "bit_size": pyaudio.paInt16,
    "chunk": 3200,
    "format": "pcm",
    "channels": 1,
    "sample_rate": 24000,
}
tts_output_audio_config = {
    "bit_size": pyaudio.paFloat32,
    "channels": 1,
    "format": "pcm",
    "sample_rate": 24000,
    "chunk": 3200
}
start_session_req = {"dialog": {"bot_name": "小塔"}, "tts": {"audio_config": tts_output_audio_config}}

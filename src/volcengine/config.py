import uuid

import pyaudio

from src.audio.type import AudioType, AudioConfig
from src.config import VOLCENGINE_AUDIO_TYPE, VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN, VOLCENGINE_BOT_NAME
from src.constants import (
    VOLCENGINE_SEND_AUDIO_SAMPLE_RATE, VOLCENGINE_RECV_PCM_AUDIO_SAMPLE_RATE,
    )

ws_connect_config = {
    "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
    "headers": {
        "X-Api-App-ID": VOLCENGINE_APP_ID,
        "X-Api-Access-Key": VOLCENGINE_ACCESS_TOKEN,
        "X-Api-Resource-Id": "volc.speech.dialog",
        "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
        "X-Api-Connect-Id": str(uuid.uuid4()),
        }
    }

"""
【重要】
- bitsize（如果指定tts/pcm回复，则要f32，否则i16）
- chunk 在使用耳机的时候，要低于1600
- channels 始终为 1 即可
"""
send_audio_config = AudioConfig.model_validate(
    {
        "bit_size": pyaudio.paInt16,
        "format": "pcm",
        "channels": 1,
        "sample_rate": VOLCENGINE_SEND_AUDIO_SAMPLE_RATE,
        "chunk": 1600
        }
    )

recv_pcm_audio_config = AudioConfig.model_validate(
    {
        "bit_size": pyaudio.paFloat32,
        "format": "pcm",
        "channels": 1,
        "sample_rate": VOLCENGINE_RECV_PCM_AUDIO_SAMPLE_RATE,
        "chunk": 1600
        }
    )

start_session_req = {
    "dialog": {
        "bot_name": VOLCENGINE_BOT_NAME
        },
    }

# 服务器默认直接返回pcm格式音频，客户端可以直接播放，代码量小，但传输较慢
# 开启OGG后，服务器将只返回ogg封装的opus音频，客户端自行解码后播放，性能较高
if VOLCENGINE_AUDIO_TYPE == AudioType.pcm:
    start_session_req["tts"] = {
        "audio_config": recv_pcm_audio_config.model_dump()
        }

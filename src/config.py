import os

from src.utils.logger import logger
from src.volcengine.config import start_session_req


# 服务器默认直接返回pcm格式音频，客户端可以直接播放，代码量小，但传输较慢
# 开启OGG后，服务器将只返回ogg封装的opus音频，客户端自行解码后播放，性能较高
ENABLE_OOG_AUDIO_FROM_SERVER = os.getenv("ENABLE_OGG", False)
logger.info(f"OGG Enabled: {ENABLE_OOG_AUDIO_FROM_SERVER}")
if ENABLE_OOG_AUDIO_FROM_SERVER:
    start_session_req.pop("tts")

IO_MODE = os.getenv("IO_MODE", "system").lower()
if IO_MODE not in ["system", "webrtc", "websocket"]:
    logger.warning(f"无效的IO_MODE: {IO_MODE}，使用默认值 'system'")
    IO_MODE = "system"

logger.info(f"IO Mode: {IO_MODE}")

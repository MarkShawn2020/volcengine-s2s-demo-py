import os

from src.utils.logger import logger

IO_MODE = os.getenv("IO_MODE", "system").lower()
if IO_MODE not in ["system", "webrtc", "websocket"]:
    logger.warning(f"无效的IO_MODE: {IO_MODE}，使用默认值 'system'")
    IO_MODE = "system"

logger.info(f"IO Mode: {IO_MODE}")

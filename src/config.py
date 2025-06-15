import os

from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.websocket.config import WebsocketConfig
from src.io_adapters.type import AdapterMode
from src.utils.logger import logger

ADAPTER_MODE: AdapterMode = os.getenv("ADAPTER_MODE", AdapterMode.system)
logger.info(f"Adapter Mode: {ADAPTER_MODE}")

webrtc_config = WebrtcConfig(
    host=os.getenv("WEBRTC_HOST", "localhost"), port=os.getenv("WEBRTC_PORT", 8765)
    )

websocket_config = WebsocketConfig(
    host=os.getenv("SOCKET_HOST", "localhost"), port=int(os.getenv("SOCKET_PORT", "8888"))
    )

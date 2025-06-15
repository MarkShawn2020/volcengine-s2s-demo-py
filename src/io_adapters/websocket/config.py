import os

from src.io_adapters.websocket.socket_manager import SocketConfig

socket_config: SocketConfig = SocketConfig(
    **{
        "host": os.getenv("SOCKET_HOST", "localhost"),
        "port": int(os.getenv("SOCKET_PORT", "8888")),
        }
    )

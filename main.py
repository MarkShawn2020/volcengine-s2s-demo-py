import asyncio

from src import config
from src.dialog_session import DialogSession


async def main() -> None:
    socket_mode = config.ENABLE_SOCKET_MODE
    webrtc_mode = config.ENABLE_WEBRTC_MODE
    session = DialogSession(config.ws_connect_config, socket_mode=socket_mode, webrtc_mode=webrtc_mode)
    await session.start()

if __name__ == "__main__":
    asyncio.run(main())

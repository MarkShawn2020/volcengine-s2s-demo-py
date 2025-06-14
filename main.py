import asyncio

from src import config
from src.audio_manager import DialogSession

async def main() -> None:
    session = DialogSession(config.ws_connect_config)
    await session.start()

if __name__ == "__main__":
    asyncio.run(main())

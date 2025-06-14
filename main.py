import asyncio

import src.volcengine.config
from src import config
from src.orchestrator import Orchestrator


async def main() -> None:
    io_mode = config.IO_MODE
    session = Orchestrator(src.volcengine.config.ws_connect_config, io_mode=io_mode)
    await session.start()

if __name__ == "__main__":
    asyncio.run(main())

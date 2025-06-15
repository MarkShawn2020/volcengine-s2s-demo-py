import asyncio

from src.orchestrator import Orchestrator


async def main() -> None:
    session = Orchestrator()
    await session.start()


if __name__ == "__main__":
    asyncio.run(main())

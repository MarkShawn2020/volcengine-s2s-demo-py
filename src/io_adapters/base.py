from abc import ABC, abstractmethod
from typing import Any, Dict

from src.utils.logger import logger


class AdapterBase(ABC):
    """实时音频输入输出基类 - 声明式架构"""

    def __init__(self, config: Dict[str, Any] = None, ):
        self.config = config
        self.is_running = False

    @abstractmethod
    async def on_pull(self, audio_chunk: bytes) -> None:
        """
        本函数接收上层程序的AI回复，转换播放或者推送到下游
        """
        pass

    @abstractmethod
    async def on_push(self) -> bytes:
        """
        本函数返回每一次读取的用户音频，以供上层程序发送给AI
        """
        pass

    @abstractmethod
    async def stop(self):
        pass

    def display_welcome_screen(self) -> None:
        """显示欢迎界面（由子类实现）"""
        logger.debug("你最好应该实现一个自定义的 welcome screen！")

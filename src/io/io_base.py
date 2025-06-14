from abc import ABC, abstractmethod
from typing import Callable, Optional, Any, Dict

from src.utils.logger import logger


class IOBase(ABC):
    """实时音频输入输出基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_running = False
        self.audio_input_callback: Optional[Callable[[bytes], None]] = None
        self.prepared_callback: Optional[Callable[[], None]] = None
        
    def set_audio_input_callback(self, callback: Callable[[bytes], None]) -> None:
        """设置音频输入回调函数"""
        self.audio_input_callback = callback
        
    def set_prepared_callback(self, callback: Callable[[], None]) -> None:
        """设置准备就绪回调函数"""
        self.prepared_callback = callback
        
    @abstractmethod
    async def start(self) -> None:
        """启动音频输入输出"""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """停止音频输入输出"""
        pass
        
    @abstractmethod
    async def send_audio_output(self, audio_data: bytes, format_type: str = "pcm") -> None:
        """发送音频输出数据"""
        pass
        
    @abstractmethod
    def display_welcome_screen(self) -> None:
        """显示欢迎界面"""
        pass
        
    @abstractmethod
    def cleanup(self) -> None:
        """清理资源"""
        pass
        
    def _handle_audio_input(self, audio_data: bytes) -> None:
        """处理音频输入数据"""
        if self.audio_input_callback and audio_data:
            try:
                self.audio_input_callback(audio_data)
            except Exception as e:
                logger.error(f"音频输入回调处理错误: {e}")
                
    def _on_prepared(self) -> None:
        """触发准备就绪回调"""
        if self.prepared_callback:
            try:
                self.prepared_callback()
            except Exception as e:
                logger.error(f"准备就绪回调处理错误: {e}")
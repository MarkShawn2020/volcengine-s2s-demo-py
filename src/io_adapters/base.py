from abc import ABC, abstractmethod
from typing import Callable, Optional, Any, Dict

from src.audio.processors.base import AudioProcessor
from src.audio.type import AudioConfig, AudioType
from src.config import VOLCENGINE_AUDIO_TYPE
from src.utils.logger import logger
from src.volcengine.config import input_audio_config, ogg_output_audio_config, start_session_req


class AdapterBase(ABC):
    """实时音频输入输出基类"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config
        self.is_running = False
        self.audio_input_callback: Optional[Callable[[bytes], None]] = None
        self.prepared_callback: Optional[Callable[[], None]] = None

        # 音频设备配置
        self.input_audio_config = AudioConfig(**input_audio_config)

        # 输出音频配置
        output_audio_config = ogg_output_audio_config
        tts_config = start_session_req.get("tts")
        if tts_config:
            tts_audio_config = tts_config.get("audio_config")
            if tts_audio_config:
                output_audio_config = tts_audio_config

        self.output_config = AudioConfig(**output_audio_config)

        # 音频处理流水线
        self.audio_pipeline: list[AudioProcessor] = []
        self._build_audio_pipeline()

    @abstractmethod
    def _build_audio_pipeline(self):
        """由子类实现，用于构建自己的音频处理流水线。"""
        pass

    async def send_audio_output(self, audio_data: bytes, audio_type: AudioType) -> None:
        """将音频数据送入流水线进行处理。"""
        if not audio_data:
            return

        # 依次通过流水线中的每个处理器
        data = audio_data
        for processor in self.audio_pipeline:
            data = processor.process(data)
            if not data:  # 如果某个环节没有输出，则中止
                break

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
    def display_welcome_screen(self) -> None:
        """显示欢迎界面"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理资源"""
        pass

    def _cleanup_pipeline(self) -> None:
        """清理资源，包括流水线中的处理器。"""
        for processor in self.audio_pipeline:
            processor.close()

    def _handle_audio_input(self, audio_data: bytes) -> None:
        """处理音频输入数据"""
        if self.audio_input_callback and audio_data:
            try:
                # logger.debug(f"🎯 调用音频输入回调: {len(audio_data)} bytes")
                self.audio_input_callback(audio_data)
            except Exception as e:
                logger.error(f"音频输入回调处理错误: {e}")
        elif not self.audio_input_callback:
            logger.warning("⚠️ 音频输入回调未设置，无法处理音频数据")
        elif not audio_data:
            logger.debug("收到空音频数据，跳过处理")

    def _on_prepared(self) -> None:
        """触发准备就绪回调"""
        if self.prepared_callback:
            try:
                self.prepared_callback()
            except Exception as e:
                logger.error(f"准备就绪回调处理错误: {e}")

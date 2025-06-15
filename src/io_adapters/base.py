from abc import ABC, abstractmethod
from typing import Callable, Optional, Any, Dict

from src.audio.processor import OggDecodingStrategy, PcmPassThroughStrategy
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

        self.processing_strategy = None # 新增成员

    def _initialize_audio_processor(self, pcm_output_callback: Callable[[bytes], None]):
        """根据配置初始化音频处理策略"""
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            logger.info("初始化 OGG->PCM 解码策略。")
            self.processing_strategy = OggDecodingStrategy(self.output_config, pcm_output_callback)
        else:
            logger.info("初始化 PCM 直通策略。")
            self.processing_strategy = PcmPassThroughStrategy(self.output_config, pcm_output_callback)

        # 启动策略
        self.processing_strategy.start()

    # send_audio_output 方法现在变得非常通用
    async def send_audio_output(self, audio_data: bytes, audio_type: AudioType) -> None:
        """接收上游音频数据，并交由处理策略进行处理"""
        if not audio_data or len(audio_data) == 0:
            return

        if self.processing_strategy:
            self.processing_strategy.process_input(audio_data)
        else:
            logger.warning("音频处理策略未初始化，无法处理输出音频。")

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

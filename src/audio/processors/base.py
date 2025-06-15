import abc


class AudioProcessor(abc.ABC):
    """音频处理模块的基类"""

    @abc.abstractmethod
    def process(self, audio_data: bytes) -> bytes:
        pass

    def flush(self) -> bytes | None:
        """处理内部可能剩余的缓冲数据"""
        return None

    def close(self):
        """清理资源"""
        pass

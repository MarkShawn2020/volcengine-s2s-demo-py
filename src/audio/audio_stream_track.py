import asyncio
import logging
from fractions import Fraction  # <--- 1. 导入 Fraction 类

from aiortc import MediaStreamTrack
from av import AudioFrame

logger = logging.getLogger(__name__)


class AudioStreamTrack(MediaStreamTrack):
    """
    一个健壮的、用于发送实时音频流的 aiortc 轨道。
    它内部维护一个连续的字节缓冲区，并按需生成固定时长的音频帧。
    """
    kind = "audio"

    def __init__(self, sample_rate: int = 48000):
        super().__init__()
        self._buffer = bytearray()
        self._buffer_lock = asyncio.Lock()

        self.SAMPLE_RATE = sample_rate  # 可配置采样率
        self.SAMPLES_PER_FRAME = int(self.SAMPLE_RATE * 0.020)
        self.BYTES_PER_FRAME = self.SAMPLES_PER_FRAME * 2

        self._pts = 0

        # 2. 【关键修复】使用 Fraction 对象来定义 time_base
        self._time_base = Fraction(1, self.SAMPLE_RATE)

        self._is_stopped = asyncio.Event()

    def stop(self):
        self._is_stopped.set()
        logger.info("AudioStreamTrack 已标记为停止。")

    async def add_p_c_m_data(self, pcm_s16le_data: bytes):
        async with self._buffer_lock:
            self._buffer.extend(pcm_s16le_data)

    async def recv(self) -> AudioFrame:
        # 等待直到缓冲区有足够的数据
        while len(self._buffer) < self.BYTES_PER_FRAME and not self._is_stopped.is_set():
            await asyncio.sleep(0.010)

        if self._is_stopped.is_set():
            return None

        async with self._buffer_lock:
            frame_data = self._buffer[:self.BYTES_PER_FRAME]
            self._buffer = self._buffer[self.BYTES_PER_FRAME:]

        frame = AudioFrame(format='s16', layout='mono', samples=self.SAMPLES_PER_FRAME)
        frame.planes[0].update(frame_data)
        frame.sample_rate = self.SAMPLE_RATE

        # 现在这里赋值的是一个 Fraction 对象，不会再报错
        frame.pts = self._pts
        frame.time_base = self._time_base
        self._pts += self.SAMPLES_PER_FRAME

        return frame

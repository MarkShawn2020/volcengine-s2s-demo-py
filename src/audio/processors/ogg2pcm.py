import logging
import queue
import threading

import ffmpeg
import pyaudio

from src.audio.processors.base import AudioProcessor

logger = logging.getLogger(__name__)


class Ogg2PcmProcessor(AudioProcessor):
    """一个有状态的处理器，负责将 OGG 流解码为 PCM 流。"""

    def __init__(self, output_config):
        self.sample_rate = output_config.sample_rate
        self.channels = output_config.channels
        self.pyaudio_format = output_config.bit_size

        # 内部队列，用于存放解码后的PCM数据
        self.pcm_queue = queue.Queue()
        self._is_running = threading.Event()
        
        # 输入缓冲区，用于积累足够的OGG数据再送给FFmpeg
        self._input_buffer = b''
        self._min_buffer_size = 1024  # 最小缓冲区大小

        format_map = {
            pyaudio.paFloat32: ('f32le', 4),
            pyaudio.paInt16: ('s16le', 2),
            }
        if self.pyaudio_format not in format_map:
            raise ValueError(f"不支持的 PyAudio 格式: {self.pyaudio_format}")

        self.ffmpeg_format, self.bytes_per_sample = format_map[self.pyaudio_format]
        self.frame_size = self.bytes_per_sample * self.channels

        logger.info(f"OGG解码器初始化：采样率={self.sample_rate}, 声道={self.channels}, 格式={self.ffmpeg_format}")

        try:
            self.ffmpeg_process = (
                ffmpeg
                .input('pipe:0', format='ogg')
                .output(
                    'pipe:1',
                    format=self.ffmpeg_format,
                    ac=self.channels,
                    ar=self.sample_rate
                    )
                .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
            )
        except ffmpeg.Error as e:
            raise RuntimeError(f"启动 FFmpeg 失败: {e.stderr.decode()}")

        self._is_running.set()

        # 启动后台线程
        self.stdout_reader_thread = threading.Thread(target=self._read_stdout)
        self.stdout_reader_thread.daemon = True
        self.stdout_reader_thread.start()

        self.stderr_reader_thread = threading.Thread(target=self._read_stderr)
        self.stderr_reader_thread.daemon = True
        self.stderr_reader_thread.start()

    def process(self, audio_data: bytes) -> bytes:
        """处理OGG音频数据，返回解码后的PCM数据"""
        if not audio_data:
            return b''

        self._feed_ogg_data(audio_data)
        
        # 收集所有可用的解码数据
        output_data = b''
        while True:
            chunk = self._get_decoded_pcm(block=False, timeout=0.01)
            if not chunk:
                break
            output_data += chunk
        
        return output_data

    def flush(self) -> bytes | None:
        """获取内部缓冲的所有剩余数据"""
        # 首先发送剩余的输入缓冲数据
        if self._input_buffer and self._is_running.is_set():
            try:
                self.ffmpeg_process.stdin.write(self._input_buffer)
                self.ffmpeg_process.stdin.flush()
                self._input_buffer = b''
            except (BrokenPipeError, OSError):
                pass
        
        # 收集所有剩余的解码数据
        remaining_data = b''
        while True:
            chunk = self._get_decoded_pcm(block=False, timeout=0.1)
            if not chunk:
                break
            remaining_data += chunk
        return remaining_data if remaining_data else None

    def close(self):
        """关闭解码器和 FFmpeg 进程"""
        if not self._is_running.is_set():
            return

        logger.info("正在关闭OGG解码器...")
        self._is_running.clear()

        # 关闭 stdin 以通知 FFmpeg 输入结束
        if self.ffmpeg_process and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.close()
            except OSError:
                pass

        # 等待后台线程结束
        self.stdout_reader_thread.join(timeout=2)
        self.stderr_reader_thread.join(timeout=2)

        # 确保进程被终止
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            logger.warning("FFmpeg 进程未正常退出，正在强制终止。")
            self.ffmpeg_process.kill()

        logger.info("OGG解码器已关闭。")
        self.ffmpeg_process = None

    def _feed_ogg_data(self, ogg_data: bytes):
        """向解码器喂入 OGG 数据 (非阻塞)"""
        if not self._is_running.is_set() or not ogg_data:
            return

        # 将数据添加到缓冲区
        self._input_buffer += ogg_data
        
        # 如果缓冲区足够大，或者这是流的开始，就发送数据
        if len(self._input_buffer) >= self._min_buffer_size:
            try:
                self.ffmpeg_process.stdin.write(self._input_buffer)
                self.ffmpeg_process.stdin.flush()
                self._input_buffer = b''  # 清空缓冲区
            except (BrokenPipeError, OSError):
                logger.warning("尝试写入已关闭的 FFmpeg stdin 管道。")
                self.close()

    def _get_decoded_pcm(self, block=True, timeout=None) -> bytes or None:
        """从内部队列获取解码后的 PCM 数据"""
        try:
            pcm_data = self.pcm_queue.get(block=block, timeout=timeout)
            # 如果收到哨兵值None，说明解码器已停止
            if pcm_data is None:
                return b''
            return pcm_data
        except queue.Empty:
            return b''

    def _read_stdout(self):
        """后台线程，持续从 FFmpeg 的 stdout 读取解码后的 PCM 数据"""
        # 减小chunk_size以降低延迟，约20ms的数据
        chunk_size = int(self.sample_rate * self.frame_size * 0.02)
        while self._is_running.is_set():
            try:
                pcm_data = self.ffmpeg_process.stdout.read(chunk_size)
                if not pcm_data:
                    logger.info("FFmpeg stdout 已关闭。")
                    break
                self.pcm_queue.put(pcm_data)
            except Exception as e:
                logger.error(f"读取 FFmpeg stdout 时出错: {e}")
                break

        self._is_running.clear()
        self.pcm_queue.put(None)

    def _read_stderr(self):
        """后台线程，持续读取 FFmpeg 的 stderr 用于日志记录"""
        while self._is_running.is_set():
            try:
                line = self.ffmpeg_process.stderr.readline()
                if not line:
                    break
                logger.debug(f"FFmpeg stderr: {line.decode('utf-8', errors='ignore').strip()}")
            except Exception as e:
                logger.error(f"读取 FFmpeg stderr 时出错: {e}")
                break

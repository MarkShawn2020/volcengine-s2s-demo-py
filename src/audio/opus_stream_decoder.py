import ffmpeg
import subprocess
import pyaudio
import threading
import queue
import logging

logger = logging.getLogger(__name__)


class OpusStreamDecoder:
    def __init__(self, output_sample_rate: int, output_channels: int, pyaudio_format: int):
        self.sample_rate = output_sample_rate
        self.channels = output_channels
        self.pyaudio_format = pyaudio_format

        # 内部队列，用于存放解码后的PCM数据
        self.pcm_queue = queue.Queue()
        self._is_running = threading.Event()

        format_map = {
            pyaudio.paFloat32: ('f32le', 4),
            pyaudio.paInt16: ('s16le', 2),
            # ... 其他格式
            }
        if self.pyaudio_format not in format_map:
            raise ValueError(f"不支持的 PyAudio 格式: {self.pyaudio_format}")

        self.ffmpeg_format, self.bytes_per_sample = format_map[self.pyaudio_format]
        self.frame_size = self.bytes_per_sample * self.channels

        logger.info(f"解码器初始化：采样率={self.sample_rate}, 声道={self.channels}, 格式={self.ffmpeg_format}")

        try:
            self.process = (
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

        # 启动一个后台线程专门读取 stdout
        self.stdout_reader_thread = threading.Thread(target=self._read_stdout)
        self.stdout_reader_thread.daemon = True
        self.stdout_reader_thread.start()

        # 启动一个后台线程专门读取 stderr (用于调试)
        self.stderr_reader_thread = threading.Thread(target=self._read_stderr)
        self.stderr_reader_thread.daemon = True
        self.stderr_reader_thread.start()

    def _read_stdout(self):
        """后台线程，持续从 FFmpeg 的 stdout 读取解码后的 PCM 数据"""
        # 每次读取一个与播放器 chunk 大小相关的值
        # 例如，一次读取 100ms 的数据
        chunk_size = int(self.sample_rate * self.frame_size * 0.1)
        while self._is_running.is_set():
            try:
                # read() 会阻塞直到有数据可读
                pcm_data = self.process.stdout.read(chunk_size)
                if not pcm_data:
                    # 如果读到空字节，说明管道已关闭，FFmpeg 进程可能已结束
                    logger.info("FFmpeg stdout 已关闭。")
                    break
                self.pcm_queue.put(pcm_data)
            except Exception as e:
                logger.error(f"读取 FFmpeg stdout 时出错: {e}")
                break

        # 线程结束时，也标记解码器停止运行
        self._is_running.clear()
        self.pcm_queue.put(None)  # 发送一个哨兵值，通知消费者结束

    def _read_stderr(self):
        """后台线程，持续读取 FFmpeg 的 stderr 用于日志记录"""
        while self._is_running.is_set():
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                logger.debug(f"FFmpeg stderr: {line.decode('utf-8', errors='ignore').strip()}")
            except Exception as e:
                logger.error(f"读取 FFmpeg stderr 时出错: {e}")
                break

    def feed_ogg_data(self, ogg_data: bytes):
        """向解码器喂入 OGG 数据 (非阻塞)"""
        if not self._is_running.is_set() or not ogg_data:
            return

        try:
            self.process.stdin.write(ogg_data)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            logger.warning("尝试写入已关闭的 FFmpeg stdin 管道。")
            self.close()

    def get_decoded_pcm(self, block=True, timeout=None) -> bytes or None:
        """
        从内部队列获取解码后的 PCM 数据。
        :return: pcm_data (bytes) 或 None (如果解码器已停止)
        """
        try:
            pcm_data = self.pcm_queue.get(block=block, timeout=timeout)
            return pcm_data
        except queue.Empty:
            return b''  # 如果超时或非阻塞模式下队列为空，返回空字节串

    def close(self):
        """关闭解码器和 FFmpeg 进程"""
        if not self._is_running.is_set():
            return

        logger.info("正在关闭解码器...")
        self._is_running.clear()

        # 关闭 stdin 以通知 FFmpeg 输入结束
        if self.process and self.process.stdin:
            try:
                self.process.stdin.close()
            except OSError:
                pass

        # 等待后台线程结束
        self.stdout_reader_thread.join(timeout=2)
        self.stderr_reader_thread.join(timeout=2)

        # 确保进程被终止
        if self.process and self.process.poll() is None:
            logger.warning("FFmpeg 进程未正常退出，正在强制终止。")
            self.process.kill()

        logger.info("解码器已关闭。")
        self.process = None
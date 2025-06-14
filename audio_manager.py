import asyncio
import uuid
import queue
import threading
import time
import logging
from typing import Optional, Dict, Any
import wave
import pyaudio
import signal
from dataclasses import dataclass
from pydub import AudioSegment
import io
import numpy as np

import config
from realtime_dialog_client import RealtimeDialogClient

# 配置日志
def setup_logging(level=logging.INFO):
    """配置日志系统"""
    # Python 3.7兼容性：移除已有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )

# 设置默认日志级别
setup_logging(logging.INFO)

# 创建音频管理器专用日志器
logger = logging.getLogger('AudioManager')

# 为不同模块设置不同的日志级别
def set_debug_mode(debug=False):
    """设置调试模式"""
    if debug:
        logger.setLevel(logging.DEBUG)
        setup_logging(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        setup_logging(logging.INFO)


@dataclass
class AudioConfig:
    """音频配置数据类"""
    format: str
    bit_size: int
    channels: int
    sample_rate: int
    chunk: int


class AudioDeviceManager:
    """音频设备管理类，处理音频输入输出"""

    def __init__(self, input_config: AudioConfig, output_config: AudioConfig):
        self.input_config = input_config
        self.output_config = output_config
        self.pyaudio = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None

    def open_input_stream(self) -> pyaudio.Stream:
        """打开音频输入流"""
        # p = pyaudio.PyAudio()
        default_input_device = self.pyaudio.get_default_input_device_info()
        logger.info(f"默认输入设备: {default_input_device['name']} (索引: {default_input_device['index']})")
        self.input_stream = self.pyaudio.open(
            input_device_index=default_input_device['index'],
            channels=self.input_config.channels,
            rate=self.input_config.sample_rate,
            frames_per_buffer=self.input_config.chunk,
            format=self.input_config.bit_size,
            input=True,
            # Add low latency settings for AirPods compatibility
            input_host_api_specific_stream_info=None,
        )
        logger.debug(f"输入音频流已打开: {self.input_stream}")
        return self.input_stream

    def open_output_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        logger.info(f"默认输出设备: {default_output_device['name']} (索引: {default_output_device['index']})")
        self.output_stream = self.pyaudio.open(
            format=self.output_config.bit_size,
            channels=self.output_config.channels,
            rate=self.output_config.sample_rate,
            output=True,
            frames_per_buffer=self.output_config.chunk,
            output_device_index=default_output_device['index'],
        )
        return self.output_stream

    def cleanup(self) -> None:
        """清理音频设备资源"""
        for stream in [self.input_stream, self.output_stream]:
            if stream:
                stream.stop_stream()
                stream.close()
        self.pyaudio.terminate()


class DialogSession:
    """对话会话管理类"""

    def __init__(self, ws_config: Dict[str, Any], debug_mode: bool = False):
        # 设置调试模式
        set_debug_mode(debug_mode)
        
        self.session_id = str(uuid.uuid4())
        logger.info(f"初始化对话会话，会话ID: {self.session_id}")
        
        self.client = RealtimeDialogClient(config=ws_config, session_id=self.session_id)
        self.audio_device = AudioDeviceManager(
            AudioConfig(**config.input_audio_config),
            AudioConfig(**config.output_audio_config)
        )
        self.output_config = AudioConfig(**config.output_audio_config)

        self.is_running = True
        self.is_session_finished = False

        signal.signal(signal.SIGINT, self._keyboard_signal)
        # 初始化音频队列和输出流 - 限制队列大小防止延迟累积
        self.audio_queue = queue.Queue(maxsize=50)
        self.output_stream = self.audio_device.open_output_stream()
        # 启动播放线程
        self.is_recording = True
        self.is_playing = True
        self.player_thread = threading.Thread(target=self._audio_player_thread)
        self.player_thread.daemon = True
        self.player_thread.start()
        
        # OGG 流缓存 - 改进的缓冲管理
        self.ogg_buffer = bytearray()
        self.last_pcm_size = 0  # 记录上次解码的PCM数据大小
        
        # 统计信息
        self.stats = {
            'ogg_pages_received': 0,
            'pcm_bytes_decoded': 0,
            'audio_queue_overflows': 0,
            'decoding_errors': 0
        }

    def _audio_player_thread(self):
        """音频播放线程 - 改进的错误处理"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_playing:
            try:
                # 从队列获取音频数据
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is not None and len(audio_data) > 0:
                    self.output_stream.write(audio_data)
                    consecutive_errors = 0  # 重置错误计数
                    
            except queue.Empty:
                # 队列为空时等待一小段时间
                time.sleep(0.1)
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"音频播放错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("连续播放错误过多，尝试重新初始化音频流")
                    try:
                        # 重新初始化输出流
                        if self.output_stream:
                            self.output_stream.stop_stream()
                            self.output_stream.close()
                        self.output_stream = self.audio_device.open_output_stream()
                        consecutive_errors = 0
                        logger.info("音频流重新初始化成功")
                    except Exception as reinit_error:
                        logger.error(f"音频流重新初始化失败: {reinit_error}")
                        time.sleep(1.0)
                else:
                    time.sleep(0.2)

    def _detect_audio_format(self, audio_data: bytes) -> str:
        """检测音频格式"""
        if len(audio_data) < 4:
            return "pcm"
        
        # 检查 OGG 文件头 (4F 67 67 53)
        if audio_data[:4] == b'OggS':
            return "ogg"
        
        # 检查 WebM 文件头 (1A 45 DF A3)
        if audio_data[:4] == b'\x1A\x45\xDF\xA3':
            return "ogg"  # WebM 也用 OGG 解码器处理
        
        # 检查 Opus 在 OGG 中的特征
        if b'OpusHead' in audio_data[:64]:
            return "ogg"
        
        # 根据配置判断：如果没有配置 TTS，很可能是压缩格式
        if not hasattr(config, 'start_session_req') or 'tts' not in config.start_session_req:
            # 没有 TTS 配置时，尝试作为压缩音频处理
            return "ogg"
        
        # 默认为 PCM
        return "pcm"
    
    def _process_ogg_stream(self, ogg_page: bytes) -> bytes:
        """处理 OGG 流式数据 - 改进的增量解码版本"""
        # 将新的 OGG 页面添加到缓冲区
        self.ogg_buffer.extend(ogg_page)
        self.stats['ogg_pages_received'] += 1
        logger.debug(f"接收OGG页面: {len(ogg_page)}字节, 缓冲区总大小: {len(self.ogg_buffer)}字节")
        
        # 尝试解码当前缓冲区的音频流
        try:
            audio = AudioSegment.from_file(io.BytesIO(bytes(self.ogg_buffer)), format="ogg")
            
            # 转换为目标格式
            audio = audio.set_frame_rate(self.output_config.sample_rate)
            audio = audio.set_channels(self.output_config.channels)
            audio = audio.set_sample_width(2)  # int16 = 2 bytes
            
            full_pcm_data = audio.raw_data
            
            if len(full_pcm_data) > 0:
                # 计算新增的PCM数据 - 使用更精确的方法
                if hasattr(self, 'last_pcm_size') and self.last_pcm_size > 0:
                    # 直接从上次的PCM数据长度开始截取
                    if len(full_pcm_data) > self.last_pcm_size:
                        new_pcm_data = full_pcm_data[self.last_pcm_size:]
                        # 更新已解码的PCM数据长度
                        self.last_pcm_size = len(full_pcm_data)
                        
                        if len(new_pcm_data) > 0:
                            # 验证音频数据质量
                            validated_data = self._validate_pcm_data(new_pcm_data)
                            if len(validated_data) > 0:
                                self.stats['pcm_bytes_decoded'] += len(validated_data)
                                logger.debug(f"增量解码 {len(validated_data)} 字节新PCM数据")
                                return validated_data
                    else:
                        # 没有新数据
                        return b''
                else:
                    # 第一次解码
                    self.last_pcm_size = len(full_pcm_data)
                    # 验证音频数据质量
                    validated_data = self._validate_pcm_data(full_pcm_data)
                    if len(validated_data) > 0:
                        self.stats['pcm_bytes_decoded'] += len(validated_data)
                        logger.debug(f"首次解码 {len(validated_data)} 字节PCM数据")
                        return validated_data
                
        except Exception as e:
            # 解码失败，记录统计
            self.stats['decoding_errors'] += 1
            # 检查是否是因为缓冲区数据不完整导致的失败
            if len(self.ogg_buffer) < 1000:  # 如果缓冲区很小，可能需要更多数据
                logger.debug("等待更多OGG数据进行解码")
            else:
                # 缓冲区较大但解码失败，可能是数据损坏
                logger.debug(f"OGG解码失败，缓冲区大小: {len(self.ogg_buffer)}")
        
        # 缓冲区管理：如果过大则保留最近的有效OGG数据
        max_buffer_size = 200000  # 200KB
        if len(self.ogg_buffer) > max_buffer_size:
            # 寻找最后一个完整的OGG页面边界
            last_ogg_start = self.ogg_buffer.rfind(b'OggS')
            if last_ogg_start > 0:
                # 从最后一个OGG页面开始保留
                self.ogg_buffer = self.ogg_buffer[last_ogg_start:]
                # 重置PCM计数，因为缓冲区被截断了
                self.last_pcm_size = 0
                logger.warning(f"OGG缓冲区过大，从最后页面保留 {len(self.ogg_buffer)} 字节")
            else:
                # 清空缓冲区重新开始
                self.ogg_buffer.clear()
                self.last_pcm_size = 0
                logger.warning("OGG缓冲区过大且无有效页面，重置缓冲区")
        
        # 返回空数据，等待更多OGG页面
        return b''
    
    def _validate_pcm_data(self, pcm_data: bytes) -> bytes:
        """验证和过滤PCM数据，防止爆炸嗞音"""
        if len(pcm_data) == 0:
            return b''
        
        # 检查数据长度是否为样本大小的倍数
        sample_size = 2  # int16 = 2 bytes
        if len(pcm_data) % sample_size != 0:
            # 截断到最近的样本边界
            pcm_data = pcm_data[:len(pcm_data) - (len(pcm_data) % sample_size)]
        
        if len(pcm_data) < sample_size:
            return b''
        
        # 转换为numpy数组进行分析
        try:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # 检查是否有异常大的音量峰值（可能的爆炸音）
            max_amplitude = np.max(np.abs(audio_array))
            if max_amplitude > 25000:  # 接近int16最大值32767的阈值
                logger.warning(f"检测到异常音量峰值: {max_amplitude}，进行音量限制")
                # 进行音量限制
                audio_array = np.clip(audio_array, -25000, 25000)
            
            # 检查是否有大量的零值（可能的静音段）
            zero_ratio = np.count_nonzero(audio_array == 0) / len(audio_array)
            if zero_ratio > 0.95:  # 95%以上都是零值
                logger.debug("检测到大量静音数据，跳过播放")
                return b''
            
            # 返回处理后的数据
            return audio_array.tobytes()
            
        except Exception as e:
            logger.error(f"PCM数据验证失败: {e}")
            return pcm_data  # 验证失败时返回原始数据

    def _convert_ogg_to_pcm(self, ogg_data: bytes) -> bytes:
        """将 OGG/Opus 音频转换为 PCM"""
        return self._process_ogg_stream(ogg_data)

    def _debug_audio_data(self, audio_data: bytes) -> None:
        """调试音频数据格式"""
        # 简化调试输出，避免过多信息
        if len(audio_data) >= 4 and audio_data[:4] == b'OggS':
            logger.debug(f"检测到OGG页面: {len(audio_data)}字节")

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        if response == {}:
            return
        """处理服务器响应"""
        if response['message_type'] == 'SERVER_ACK' and isinstance(response.get('payload_msg'), bytes):
            audio_data = response['payload_msg']
            
            if len(audio_data) == 0:
                return
            
            # 调试：分析音频数据
            self._debug_audio_data(audio_data)
            
            # 检测音频格式
            audio_format = self._detect_audio_format(audio_data)
            
            # 如果是 OGG 格式，处理流式数据
            if audio_format == "ogg":
                processed_audio = self._convert_ogg_to_pcm(audio_data)
                if len(processed_audio) > 0:
                    # 将处理后的PCM数据加入播放队列
                    try:
                        self.audio_queue.put(processed_audio, timeout=0.1)
                    except queue.Full:
                        self.stats['audio_queue_overflows'] += 1
                        logger.warning("音频队列已满，跳过此音频片段")
            else:
                # PCM格式直接播放
                try:
                    self.audio_queue.put(audio_data, timeout=0.1)
                except queue.Full:
                    self.stats['audio_queue_overflows'] += 1
                    logger.warning("音频队列已满，跳过此音频片段")
        elif response['message_type'] == 'SERVER_FULL_RESPONSE':
            logger.info(f"服务器响应: 事件{response.get('event', 'unknown')}")
            if response['event'] == 450:
                logger.info(f"清空缓存音频，会话ID: {response['session_id']}")
                # 清空音频队列
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        continue
                # 清空OGG缓冲区，准备下一轮对话
                self.ogg_buffer.clear()
                self.last_pcm_size = 0
                logger.info("已清空OGG缓冲区")
        elif response['message_type'] == 'SERVER_ERROR':
            logger.error(f"服务器错误: {response['payload_msg']}")
            raise Exception("服务器错误")

    def log_stats(self):
        """输出统计信息"""
        logger.info("=== 音频处理统计 ===")
        logger.info(f"接收OGG页面数: {self.stats['ogg_pages_received']}")
        logger.info(f"解码PCM字节数: {self.stats['pcm_bytes_decoded']}")
        logger.info(f"队列溢出次数: {self.stats['audio_queue_overflows']}")
        logger.info(f"解码错误次数: {self.stats['decoding_errors']}")
        logger.info("==================")

    def _keyboard_signal(self, sig, frame):
        logger.info("接收到键盘中断信号 (Ctrl+C)")
        self.log_stats()
        self.is_recording = False
        self.is_playing = False
        self.is_running = False

    async def receive_loop(self):
        try:
            while True:
                response = await self.client.receive_server_response()
                self.handle_server_response(response)
                if 'event' in response and (response['event'] == 152 or response['event'] == 153):
                    logger.info(f"接收到会话结束事件: {response['event']}")
                    self.is_session_finished = True
                    break
        except asyncio.CancelledError:
            logger.info("接收任务已取消")
        except Exception as e:
            logger.error(f"接收消息错误: {e}")

    async def process_microphone_input(self) -> None:
        """处理麦克风输入"""
        stream = self.audio_device.open_input_stream()
        logger.info("已打开麦克风，请讲话...")

        while self.is_recording:
            try:
                # 添加exception_on_overflow=False参数来忽略溢出错误
                audio_data = stream.read(config.input_audio_config["chunk"], exception_on_overflow=False)
                save_pcm_to_wav(audio_data, "output.wav")
                await self.client.task_request(audio_data)
                await asyncio.sleep(0.01)  # 避免CPU过度使用
            except Exception as e:
                logger.error(f"读取麦克风数据出错: {e}")
                await asyncio.sleep(0.1)  # 给系统一些恢复时间

    async def start(self) -> None:
        """启动对话会话"""
        try:
            await self.client.connect()
            asyncio.create_task(self.process_microphone_input())
            asyncio.create_task(self.receive_loop())

            while self.is_running:
                await asyncio.sleep(0.1)

            await self.client.finish_session()
            while not self.is_session_finished:
                await asyncio.sleep(0.1)
            await self.client.finish_connection()
            await asyncio.sleep(0.1)
            await self.client.close()
            logger.info(f"对话请求日志ID: {self.client.logid}")
            self.log_stats()
        except Exception as e:
            logger.error(f"会话错误: {e}")
        finally:
            self.audio_device.cleanup()


def save_pcm_to_wav(pcm_data: bytes, filename: str) -> None:
    """保存PCM数据为WAV文件"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(config.input_audio_config["channels"])
        wf.setsampwidth(2)  # paInt16 = 2 bytes
        wf.setframerate(config.input_audio_config["sample_rate"])
        wf.writeframes(pcm_data)

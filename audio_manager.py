import asyncio
import uuid
import queue
import threading
import time
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
        print(f"⭐️ default_input_device: {default_input_device}")
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
        print(f"⭐️ input_stream: {self.input_stream}")
        return self.input_stream

    def open_output_stream(self) -> pyaudio.Stream:
        """打开音频输出流"""
        default_output_device = self.pyaudio.get_default_output_device_info()
        print(f"⭐️ default_output_device: {default_output_device}")
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

    def __init__(self, ws_config: Dict[str, Any]):
        self.session_id = str(uuid.uuid4())
        self.client = RealtimeDialogClient(config=ws_config, session_id=self.session_id)
        self.audio_device = AudioDeviceManager(
            AudioConfig(**config.input_audio_config),
            AudioConfig(**config.output_audio_config)
        )
        self.output_config = AudioConfig(**config.output_audio_config)

        self.is_running = True
        self.is_session_finished = False

        signal.signal(signal.SIGINT, self._keyboard_signal)
        # 初始化音频队列和输出流
        self.audio_queue = queue.Queue()
        self.output_stream = self.audio_device.open_output_stream()
        # 启动播放线程
        self.is_recording = True
        self.is_playing = True
        self.player_thread = threading.Thread(target=self._audio_player_thread)
        self.player_thread.daemon = True
        self.player_thread.start()
        
        # OGG 流缓存
        self.ogg_buffer = bytearray()
        self.ogg_pages_count = 0

    def _audio_player_thread(self):
        """音频播放线程"""
        while self.is_playing:
            try:
                # 从队列获取音频数据
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is not None:
                    self.output_stream.write(audio_data)
            except queue.Empty:
                # 队列为空时等待一小段时间
                time.sleep(0.1)
            except Exception as e:
                print(f"音频播放错误: {e}")
                time.sleep(0.1)

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
        """处理 OGG 流式数据"""
        # 将新的 OGG 页面添加到缓冲区
        self.ogg_buffer.extend(ogg_page)
        self.ogg_pages_count += 1
        
        print(f"累积 OGG 页面: {self.ogg_pages_count}, 缓冲区大小: {len(self.ogg_buffer)} 字节")
        
        # 动态调整阈值：从3个页面开始尝试，最多等到8个页面
        min_pages = 3
        max_pages = 8
        
        if self.ogg_pages_count >= min_pages:
            for attempt_pages in range(min_pages, min(self.ogg_pages_count + 1, max_pages + 1)):
                try:
                    # 尝试解码整个缓冲区
                    audio = AudioSegment.from_file(io.BytesIO(bytes(self.ogg_buffer)), format="ogg")
                    
                    # 转换为目标格式
                    audio = audio.set_frame_rate(self.output_config.sample_rate)
                    audio = audio.set_channels(self.output_config.channels)
                    
                    # 根据输出配置设置样本格式 - 先尝试使用 int16 避免转换问题
                    audio = audio.set_sample_width(2)  # int16 = 2 bytes
                    pcm_data = audio.raw_data
                    
                    print(f"原始解码信息:")
                    print(f"- 采样率: {audio.frame_rate} Hz")
                    print(f"- 声道数: {audio.channels}")
                    print(f"- 样本宽度: {audio.sample_width} bytes")
                    print(f"- 数据长度: {len(pcm_data)} bytes")
                    
                    # 暂时使用 int16 格式，避免 float32 转换问题
                    # TODO: 如果需要 float32，稍后再优化转换
                    print(f"成功解码 OGG 流: {len(pcm_data)} 字节 PCM 数据")
                    
                    # 清空缓冲区，重新开始
                    self.ogg_buffer.clear()
                    self.ogg_pages_count = 0
                    
                    return pcm_data
                    
                except Exception as e:
                    # 继续尝试更多页面
                    continue
            
            # 所有尝试都失败了
            print(f"OGG 流解码失败，尝试了 {min_pages}-{min(self.ogg_pages_count, max_pages)} 个页面")
            
            # 如果页面太多或缓冲区太大，重置
            if self.ogg_pages_count >= max_pages or len(self.ogg_buffer) > 50000:
                print("重置 OGG 缓冲区")
                self.ogg_buffer.clear()
                self.ogg_pages_count = 0
        
        # 还没有足够的数据进行解码
        return b''
    
    def _convert_ogg_to_pcm(self, ogg_data: bytes) -> bytes:
        """将 OGG/Opus 音频转换为 PCM"""
        return self._process_ogg_stream(ogg_data)

    def _debug_audio_data(self, audio_data: bytes) -> None:
        """调试音频数据格式"""
        # 简化调试输出，避免过多信息
        if len(audio_data) >= 4 and audio_data[:4] == b'OggS':
            print(f"OGG页面: {len(audio_data)}字节")

    def handle_server_response(self, response: Dict[str, Any]) -> None:
        if response == {}:
            return
        """处理服务器响应"""
        if response['message_type'] == 'SERVER_ACK' and isinstance(response.get('payload_msg'), bytes):
            audio_data = response['payload_msg']
            
            # 调试：分析音频数据
            self._debug_audio_data(audio_data)
            
            # 检测音频格式
            audio_format = self._detect_audio_format(audio_data)
            
            # 如果是 OGG 格式，处理流式数据
            if audio_format == "ogg":
                audio_data = self._convert_ogg_to_pcm(audio_data)
                if len(audio_data) == 0:
                    return  # 等待更多数据
            
            if len(audio_data) > 0:
                self.audio_queue.put(audio_data)
        elif response['message_type'] == 'SERVER_FULL_RESPONSE':
            print(f"服务器响应: {response}")
            if response['event'] == 450:
                print(f"清空缓存音频: {response['session_id']}")
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        continue
        elif response['message_type'] == 'SERVER_ERROR':
            print(f"服务器错误: {response['payload_msg']}")
            raise Exception("服务器错误")

    def _keyboard_signal(self, sig, frame):
        print(f"receive keyboard Ctrl+C")
        self.is_recording = False
        self.is_playing = False
        self.is_running = False

    async def receive_loop(self):
        try:
            while True:
                response = await self.client.receive_server_response()
                self.handle_server_response(response)
                if 'event' in response and (response['event'] == 152 or response['event'] == 153):
                    print(f"receive session finished event: {response['event']}")
                    self.is_session_finished = True
                    break
        except asyncio.CancelledError:
            print("接收任务已取消")
        except Exception as e:
            print(f"接收消息错误: {e}")

    async def process_microphone_input(self) -> None:
        """处理麦克风输入"""
        stream = self.audio_device.open_input_stream()
        print("已打开麦克风，请讲话...")

        while self.is_recording:
            try:
                # 添加exception_on_overflow=False参数来忽略溢出错误
                audio_data = stream.read(config.input_audio_config["chunk"], exception_on_overflow=False)
                save_pcm_to_wav(audio_data, "output.wav")
                await self.client.task_request(audio_data)
                await asyncio.sleep(0.01)  # 避免CPU过度使用
            except Exception as e:
                print(f"读取麦克风数据出错: {e}")
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
            print(f"dialog request logid: {self.client.logid}")
        except Exception as e:
            print(f"会话错误: {e}")
        finally:
            self.audio_device.cleanup()


def save_pcm_to_wav(pcm_data: bytes, filename: str) -> None:
    """保存PCM数据为WAV文件"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(config.input_audio_config["channels"])
        wf.setsampwidth(2)  # paInt16 = 2 bytes
        wf.setframerate(config.input_audio_config["sample_rate"])
        wf.writeframes(pcm_data)

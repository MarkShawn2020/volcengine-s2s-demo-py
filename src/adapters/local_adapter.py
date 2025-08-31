import uuid
import asyncio
import logging
import threading
import queue
import json
import sys
from typing import Dict, Any, AsyncGenerator, Optional

from src.adapters.base import AudioAdapter, LocalConnectionConfig
from src.adapters.type import AdapterType
from src.volcengine.client import VolcengineClient
from src.volcengine import protocol
from src.audio.threads import recorder_thread, player_thread
from src.audio.utils.select_audio_device import select_audio_device
from src.audio.utils.voice_activity_detector import VoiceActivityDetector
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


def text_input_thread(adapter, stop_event: threading.Event, loop):
    """文字输入线程"""
    print("\n=== 文字输入模式已启动 ===")
    print("输入文本消息，按Enter发送（输入'quit'退出，输入'hello'调用welcome）：")
    
    while not stop_event.is_set():
        try:
            text = input("> ")
            if text.lower() == 'quit':
                break
            if text.strip():
                if text.lower() == 'hello':
                    # 调用welcome函数
                    future = asyncio.run_coroutine_threadsafe(
                        adapter.send_welcome(), 
                        loop
                    )
                    try:
                        future.result(timeout=5.0)
                        logger.info("已调用welcome函数")
                    except Exception as e:
                        logger.error(f"调用welcome函数失败: {e}")
                else:
                    # 按照官网文档要求发送三包
                    future = asyncio.run_coroutine_threadsafe(
                        adapter._send_chat_tts_text_packets(text), 
                        loop
                    )
                    try:
                        future.result(timeout=5.0)
                        logger.info(f"已发送文本: {text}")
                    except Exception as e:
                        logger.error(f"发送文本失败: {e}")
        except EOFError:
            break
        except Exception as e:
            logger.error(f"文字输入异常: {e}")
            break
    
    logger.info("文字输入线程结束")



class LocalAudioAdapter(AudioAdapter):
    """本地音频适配器 - 直接连接火山引擎"""
    
    def __init__(self, config: LocalConnectionConfig, input_device_index: int = None, output_device_index: int = None):
        super().__init__(config.params)
        self.config = config
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None
        self._text_input_thread = None
        # 支持预选择的设备索引（GUI模式）
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
    
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.LOCAL
    
    async def connect(self) -> bool:
        """建立与火山引擎的直接连接"""
        try:
            # 合并全局配置和额外参数
            client_config = {**ws_connect_config}
            if hasattr(self.config, 'params') and self.config.params:
                client_config.update(self.config.params)
            
            self.client = VolcengineClient(client_config, self.bot_name, self.tts_config)
            await self.client.start()
            
            if self.client.is_active:
                self.is_connected = True
                self.session_id = self.client.session_id
                # 启动响应接收任务
                self._receiver_task = asyncio.create_task(self._receive_responses())
                logger.info(f"本地适配器连接成功，会话ID: {self.session_id[:8]}...")

                # await self.send_welcome()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"本地适配器连接失败: {e}")
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass
        
        
        if self.client:
            await self.client.stop()
            self.client = None
        
        self.is_connected = False
        logger.info("本地适配器已断开连接")
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            await self.client.push_audio(audio_data)
            return True
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
            return False
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收音频数据流"""
        while self.is_connected:
            try:
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                if response.get('event') == protocol.ServerEvent.TTS_RESPONSE:
                    audio_data = response.get('payload_msg')
                    if isinstance(audio_data, bytes):
                        yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break
    
    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            await self.client.push_text(text)
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False
    
    async def send_chat_tts_text(self, text: str, start: bool = True, end: bool = True) -> bool:
        """发送ChatTTS文本消息"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            await self.client.push_chat_tts_text(text, start, end)
            return True
        except Exception as e:
            logger.error(f"发送ChatTTS文本失败: {e}")
            return False
    
    async def _send_chat_tts_text_packets(self, text: str) -> bool:
        """按照官网文档要求发送ChatTTS文本的三包"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            # 将文本分为两部分：第一包和中间包
            text_len = len(text)
            if text_len <= 2:
                # 文本太短，第一包包含所有内容，中间包为空
                first_part = text
                middle_part = ""
            else:
                # 将文本分为两部分
                split_pos = text_len // 2
                first_part = text[:split_pos]
                middle_part = text[split_pos:]
            
            # 第一包 (start=true, end=false)
            await self.client.push_chat_tts_text(first_part, start=True, end=False)
            logger.debug(f"发送第一包: {first_part}")
            
            # 中间包 (start=false, end=false)
            await self.client.push_chat_tts_text(middle_part, start=False, end=False)
            logger.debug(f"发送中间包: {middle_part}")
            
            # 最后一包 (start=false, end=true, content="")
            await self.client.push_chat_tts_text("", start=False, end=True)
            logger.debug("发送最后一包")
            
            return True
        except Exception as e:
            logger.error(f"发送ChatTTS文本包失败: {e}")
            return False
    
    async def setup_audio_devices(self, p, stop_event: threading.Event) -> tuple[Optional[threading.Thread], Optional[threading.Thread]]:
        """设置音频设备"""
        try:
            # 检查是否已经预选择了设备（GUI模式）
            if self.input_device_index is not None and self.output_device_index is not None:
                input_device_index = self.input_device_index
                output_device_index = self.output_device_index
                logger.info(f"使用预选择的设备 - 输入: {input_device_index}, 输出: {output_device_index}")
            else:
                # CLI模式：在单独线程中选择设备，避免阻塞事件循环
                import concurrent.futures
                
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 选择输入设备
                    input_device_index = await loop.run_in_executor(
                        executor, select_audio_device, p, "选择输入设备 (麦克风):", 'input'
                    )
                    if input_device_index is None:
                        return None, None

                    # 选择输出设备
                    output_device_index = await loop.run_in_executor(
                        executor, select_audio_device, p, "选择输出设备 (扬声器):", 'output'
                    )
                    if output_device_index is None:
                        return None, None

            # 启动录音和播放线程，使用更大的chunk_size
            chunk_size = 1600  # 使用1600帧，约100ms的音频
            send_queue = queue.Queue()
            play_queue = queue.Queue()
            
            player = threading.Thread(
                target=player_thread, args=(p, output_device_index, play_queue, chunk_size, stop_event)
            )
            recorder = threading.Thread(
                target=recorder_thread, args=(p, input_device_index, send_queue, chunk_size, stop_event)
            )

            # 启动文字输入线程（仅CLI模式）
            if self.input_device_index is None:  # CLI模式
                current_loop = asyncio.get_event_loop()
                # text_input = threading.Thread(
                #     target=text_input_thread, args=(self, stop_event, current_loop)
                # )

            recorder.start()
            player.start()
            # 暂时关闭文本输入线程
            # text_input.start()
            
            # 存储队列和线程供后续使用
            self._send_queue = send_queue
            self._play_queue = play_queue
            # self._text_input_thread = text_input

            logger.info("音频设备设置完成")
            return recorder, player

        except Exception as e:
            logger.error(f"音频设备设置失败: {e}")
            return None, None

    async def run_sender_task(self, send_queue: queue.Queue, stop_event: threading.Event) -> None:
        """运行发送任务"""
        logger.info("发送任务启动，启用语音活动检测")
        audio_count = 0
        sent_count = 0
        failed_count = 0
        max_failures = 10

        # 创建语音活动检测器
        vad = VoiceActivityDetector(threshold=0.001, min_speech_frames=2)

        while not stop_event.is_set() and self.is_connected:
            try:
                # 更短的超时，保证实时性
                audio_chunk = await asyncio.to_thread(send_queue.get, timeout=0.2)
                audio_count += 1

                # 检测语音活动
                should_send = True  # vad.process_frame(audio_chunk)

                if should_send:
                    # 发送音频数据
                    success = await self.send_audio(audio_chunk)
                    if success:
                        sent_count += 1
                        failed_count = 0  # 重置失败计数

                        # 显示音量指示 - 减少输出频率
                        volume = vad.get_volume(audio_chunk)
                        if sent_count % 100 == 0:  # 每100个包显示一次，减少日志输出
                            logger.info(f"🎤 发送语音 #{sent_count}, 音量: {volume:.3f}")
                    else:
                        failed_count += 1
                        logger.warning(f"发送音频失败 ({failed_count}/{max_failures})")
                        if failed_count >= max_failures:
                            logger.error("连续发送失败过多，可能连接有问题")
                            break
                else:
                    # 静音期间，减少日志输出
                    if audio_count % 500 == 0:  # 进一步减少静音日志
                        volume = vad.get_volume(audio_chunk)
                        logger.debug(f"🔇 静音检测中... 音量: {volume:.3f}")

            except queue.Empty:
                # 短暂等待，避免占用过多CPU
                await asyncio.sleep(0.01)
                continue
            except Exception as e:
                logger.error(f"发送任务异常: {e}")
                break

        logger.info(f"发送任务结束，处理 {audio_count} 个音频包，实际发送 {sent_count} 个")

    async def run_receiver_task(self, play_queue: queue.Queue, stop_event: threading.Event) -> None:
        """运行接收任务"""
        logger.info("接收任务启动")
        
        while self.is_connected and not stop_event.is_set():
            try:
                # 从适配器的响应队列获取数据
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                if not response or "error" in response:
                    continue

                event = response.get('event')
                if event == protocol.ServerEvent.TTS_RESPONSE:
                    # 音频响应 - 优化队列处理，减少日志输出
                    audio_data = response.get('payload_msg')
                    logger.debug(f"收到TTS音频数据: {type(audio_data)}, 大小: {len(audio_data) if isinstance(audio_data, bytes) else 'N/A'}")
                    # 避免满
                    if play_queue.full():
                        play_queue.get_nowait()
                    play_queue.put_nowait(response)

                # interrupt speaking
                elif event == protocol.ServerEvent.ASR_INFO:
                    while not play_queue.empty():
                        play_queue.get_nowait()
                elif event:
                    # 其他事件，友好显示
                    try:
                        event_name = protocol.ServerEvent(event).name
                        payload = response.get('payload_msg', {})
                        if isinstance(payload, dict):
                            logger.info(f"收到事件: {event_name} - {json.dumps(payload, ensure_ascii=False)}")
                        else:
                            logger.info(f"收到事件: {event_name}")
                    except ValueError:
                        logger.info(f"收到未知事件: {event}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收响应失败: {e}")
                break

    async def _receive_responses(self):
        """接收响应的后台任务"""
        while self.is_connected and self.client:
            try:
                response = await self.client.on_response()
                if response:
                    await self.response_queue.put(response)
            except Exception as e:
                logger.error(f"接收响应失败: {e}")
                break

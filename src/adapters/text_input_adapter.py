import asyncio
import json
import logging
import queue
import threading
from typing import AsyncGenerator, Optional

from src.adapters.base import AudioAdapter, LocalConnectionConfig
from src.adapters.type import AdapterType
from src.audio.threads import player_thread
from src.audio.utils.select_audio_device import select_audio_device
from src.config import WELCOME_MESSAGE
from src.volcengine import protocol
from src.volcengine.client import VolcengineClient
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


class TextInputAdapter(AudioAdapter):
    """文字输入适配器 - 用户输入文字，AI通过ChatTTS读出来"""
    
    def __init__(self, config: LocalConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None
        self._input_task = None
        self._send_queue = None
        self._play_queue = None
    
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TEXT_INPUT
    
    async def connect(self) -> bool:
        """建立与火山引擎的连接"""
        try:
            self.client = VolcengineClient(ws_connect_config)
            await self.client.start()
            
            if self.client.is_active:
                self.is_connected = True
                self.session_id = self.client.session_id
                self._receiver_task = asyncio.create_task(self._receive_responses())
                logger.info(f"文字输入适配器连接成功，会话ID: {self.session_id[:8]}...")
                
                await self.send_welcome()
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"文字输入适配器连接失败: {e}")
            return False
    
    async def send_welcome(self):
        await self.client.push_text(WELCOME_MESSAGE)
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass
        
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass
        
        if self.client:
            await self.client.stop()
            self.client = None
        
        self.is_connected = False
        logger.info("文字输入适配器已断开连接")
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """文字输入模式不发送音频"""
        return True
    
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
        """发送文本消息 - 使用ChatTTS接口，分三包发送"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            # 第一包：开始包
            await self.client.push_chat_tts_text("", start=True, end=False)
            
            # 第二包：中间包
            await self.client.push_chat_tts_text(text, start=False, end=False)
            
            # 第三包：结束包
            await self.client.push_chat_tts_text("", start=False, end=True)
            
            return True
        except Exception as e:
            logger.error(f"发送ChatTTS文本失败: {e}")
            return False
    
    async def setup_audio_devices(self, p, stop_event: threading.Event) -> tuple[
        Optional[threading.Thread], Optional[threading.Thread]]:
        """设置音频设备 - 只需要输出设备播放TTS"""
        try:
            # 只选择输出设备用于播放TTS
            output_device_index = select_audio_device(p, "选择输出设备 (扬声器):", 'output')
            if output_device_index is None:
                return None, None
            
            chunk_size = 1600
            play_queue = queue.Queue()
            
            player = threading.Thread(
                target=player_thread, args=(p, output_device_index, play_queue, chunk_size, stop_event)
            )
            player.start()
            
            # 设置队列属性
            self._send_queue = queue.Queue()  # 文字输入模式不需要发送队列，但要有这个属性
            self._play_queue = play_queue
            
            logger.info("音频输出设备设置完成")
            return None, player
        
        except Exception as e:
            logger.error(f"音频设备设置失败: {e}")
            return None, None
    
    async def run_sender_task(self, send_queue: queue.Queue, stop_event: threading.Event) -> None:
        """运行发送任务 - 处理用户文字输入"""
        logger.info("文字输入任务启动，请输入文字（输入 'quit' 或 'exit' 退出）:")
        
        self._input_task = asyncio.create_task(self._handle_text_input(stop_event))
        
        try:
            await self._input_task
        except asyncio.CancelledError:
            pass
        
        logger.info("文字输入任务结束")
    
    async def _handle_text_input(self, stop_event: threading.Event):
        """处理文字输入的协程"""
        while not stop_event.is_set() and self.is_connected:
            try:
                # 使用 asyncio.to_thread 在线程中执行 input()
                user_input = await asyncio.to_thread(input, "💬 请输入文字: ")
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    logger.info("用户请求退出")
                    stop_event.set()
                    break
                
                if user_input.strip():
                    logger.info(f"发送文字: {user_input}")
                    success = await self.send_text(user_input)
                    if not success:
                        logger.error("发送文字失败")
            
            except Exception as e:
                logger.error(f"处理文字输入异常: {e}")
                break
    
    async def run_receiver_task(self, play_queue: queue.Queue, stop_event: threading.Event) -> None:
        """运行接收任务"""
        logger.info("接收任务启动")
        received_count = 0
        
        while self.is_connected and not stop_event.is_set():
            try:
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                if not response or "error" in response:
                    continue
                
                event = response.get('event')
                if event == protocol.ServerEvent.TTS_RESPONSE:
                    audio_data = response.get('payload_msg')
                    received_count += 1
                    logger.info(f"收到TTS音频数据 #{received_count}: {type(audio_data)}, 大小: {len(audio_data) if isinstance(audio_data, bytes) else 'N/A'}")
                    
                    if play_queue.full():
                        play_queue.get_nowait()
                    play_queue.put_nowait(response)
                
                elif event:
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

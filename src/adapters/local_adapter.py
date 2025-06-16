import uuid
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator

from src.adapters.base import AudioAdapter, AdapterType, LocalConnectionConfig
from src.volcengine.client import VoicengineClient
from src.volcengine import protocol

logger = logging.getLogger(__name__)


class LocalAudioAdapter(AudioAdapter):
    """本地音频适配器 - 直接连接火山引擎"""
    
    def __init__(self, config: LocalConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None
    
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.LOCAL
    
    async def connect(self) -> bool:
        """建立与火山引擎的直接连接"""
        try:
            ws_config = {
                "base_url": self.config.get("base_url"),
                "headers": {
                    "X-Api-App-ID": self.config.get("app_id"),
                    "X-Api-Access-Key": self.config.get("access_token"),
                    "X-Api-Resource-Id": "volc.speech.dialog",
                    "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
                    "X-Api-Connect-Id": str(uuid.uuid4()),
                }
            }
            
            self.client = VoicengineClient(ws_config)
            await self.client.start()
            
            if self.client.is_active:
                self.is_connected = True
                self.session_id = self.client.session_id
                # 启动响应接收任务
                self._receiver_task = asyncio.create_task(self._receive_responses())
                logger.info(f"本地适配器连接成功，会话ID: {self.session_id[:8]}...")
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
            await self.client.request_say_hello(text)
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False
    
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
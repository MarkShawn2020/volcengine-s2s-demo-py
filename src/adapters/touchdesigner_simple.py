"""
TouchDesigner适配器 - 简化版本 (约100行)
就是UDP收发音频数据，连接豆包API
"""

import asyncio
import logging
import socket
import struct
from typing import AsyncGenerator

from src.adapters.base import AudioAdapter, ConnectionConfig
from src.adapters.type import AdapterType
from src.volcengine.client import VolcengineClient
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


class TouchDesignerConnectionConfig(ConnectionConfig):
    def __init__(self, td_ip: str, td_port: int, app_id: str, access_token: str, **kwargs):
        super().__init__(
            td_ip=td_ip,
            td_port=td_port,
            app_id=app_id,
            access_token=access_token,
            **kwargs
        )


class TouchDesignerSimpleAdapter(AudioAdapter):
    """TouchDesigner简单适配器"""

    def __init__(self, config: TouchDesignerConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        
        # UDP配置
        self.td_ip = self.config.get("td_ip", "localhost")
        self.td_port = self.config.get("td_port", 7000)
        self.listen_port = self.config.get("listen_port", 7001)
        
        self.udp_socket = None
        self.listen_socket = None

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCH_DESIGNER

    async def connect(self) -> bool:
        """连接豆包和设置UDP"""
        try:
            # 连接豆包
            self.client = VolcengineClient(ws_connect_config)
            await self.client.start()
            
            if not self.client.is_active:
                return False

            # 设置UDP
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.listen_socket.bind(('0.0.0.0', self.listen_port))
            self.listen_socket.setblocking(False)

            self.is_connected = True
            self.session_id = self.client.session_id

            # 启动任务
            asyncio.create_task(self._udp_listener())
            asyncio.create_task(self._receive_responses())

            logger.info(f"TouchDesigner适配器连接成功")
            return True

        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    async def _udp_listener(self):
        """监听TD发来的音频"""
        while self.is_connected:
            try:
                loop = asyncio.get_event_loop()
                data, addr = await loop.sock_recvfrom(self.listen_socket, 4096)

                if len(data) > 8:
                    length = struct.unpack('<I', data[:4])[0]
                    msg_type = struct.unpack('<I', data[4:8])[0]

                    if msg_type == 1:  # 音频数据
                        audio_data = data[8:8 + length]
                        await self.client.push_audio(audio_data)

            except Exception as e:
                await asyncio.sleep(0.1)

    async def _receive_responses(self):
        """接收豆包响应"""
        while self.is_connected and self.client:
            try:
                response = await self.client.on_response()
                if response:
                    await self.response_queue.put(response)
            except Exception as e:
                break

    async def disconnect(self) -> None:
        """断开连接"""
        self.is_connected = False
        
        if self.udp_socket:
            self.udp_socket.close()
        if self.listen_socket:
            self.listen_socket.close()
        if self.client:
            await self.client.stop()

    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频到豆包"""
        if not self.is_connected:
            return False
        try:
            await self.client.push_audio(audio_data)
            return True
        except:
            return False

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收豆包音频并发送到TD"""
        while self.is_connected:
            try:
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                
                if response.get('event') == 'tts_response':
                    audio_data = response.get('payload_msg')
                    if isinstance(audio_data, bytes):
                        # 发送到TD
                        await self._send_to_td(audio_data)
                        yield audio_data
                        
            except asyncio.TimeoutError:
                continue

    async def _send_to_td(self, audio_data: bytes):
        """发送音频到TD"""
        try:
            # 构造UDP包
            packet = struct.pack('<II', len(audio_data), 1) + audio_data
            
            loop = asyncio.get_event_loop()
            await loop.sock_sendto(self.udp_socket, packet, (self.td_ip, self.td_port))
            
            logger.debug(f"发送音频到TD: {len(audio_data)} 字节")
            
        except Exception as e:
            logger.warning(f"发送到TD失败: {e}")

    async def send_text(self, text: str) -> bool:
        """发送文本到豆包"""
        if not self.is_connected:
            return False
        try:
            await self.client.push_text(text)
            return True
        except:
            return False
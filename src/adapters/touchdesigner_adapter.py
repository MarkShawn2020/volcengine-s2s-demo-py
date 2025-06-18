import asyncio
import logging
import socket
import struct
from typing import AsyncGenerator

from src.adapters.base import AudioAdapter, AdapterType, ConnectionConfig
from src.volcengine import protocol
from src.volcengine.client import VoicengineClient
from src.volcengine.config import ws_connect_config

logger = logging.getLogger(__name__)


class TouchDesignerConnectionConfig(ConnectionConfig):
    """TouchDesigner连接配置"""

    def __init__(self, td_ip: str, td_port: int, app_id: str, access_token: str, **kwargs):
        super().__init__(
            td_ip=td_ip,
            td_port=td_port,
            app_id=app_id,
            access_token=access_token,
            base_url="wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
            **kwargs
            )


class TouchDesignerAudioAdapter(AudioAdapter):
    """TouchDesigner音频适配器 - 通过UDP与TD通信，直接连接豆包"""

    def __init__(self, config: TouchDesignerConnectionConfig):
        super().__init__(config.params)
        self.client = None
        self.response_queue = asyncio.Queue()
        self._receiver_task = None

        # UDP相关
        self.td_ip = self.config.get("td_ip", "localhost")
        self.td_port = self.config.get("td_port", 7002)
        self.listen_port = self.config.get("listen_port", 7001)  # 监听TD发送的音频

        self.udp_socket = None
        self.listen_socket = None
        self._udp_listener_task = None

        # 音频格式配置 (根据豆包要求: 16kHz, 16-bit, mono)
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2  # 16-bit = 2 bytes

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCH_DESIGNER

    async def connect(self) -> bool:
        """建立与豆包的连接和TD的UDP通信"""
        try:
            # 1. 建立与豆包的WebSocket连接

            self.client = VoicengineClient(ws_connect_config)
            await self.client.start()

            if not self.client.is_active:
                logger.error("豆包客户端连接失败")
                return False

            # 2. 设置UDP通信
            await self._setup_udp_communication()

            self.is_connected = True
            self.session_id = self.client.session_id

            # 启动响应接收任务
            self._receiver_task = asyncio.create_task(self._receive_responses())

            logger.info(f"TouchDesigner适配器连接成功，会话ID: {self.session_id[:8]}...")
            logger.info(f"UDP监听端口: {self.listen_port}, TD目标: {self.td_ip}:{self.td_port}")
            return True

        except Exception as e:
            logger.error(f"TouchDesigner适配器连接失败: {e}")
            return False

    async def _setup_udp_communication(self):
        """设置UDP通信"""
        # 创建发送socket (发送音频到TD)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 创建监听socket (接收TD的音频)
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_socket.bind(('0.0.0.0', self.listen_port))
        self.listen_socket.setblocking(False)

        # 启动UDP监听任务
        self._udp_listener_task = asyncio.create_task(self._udp_listener())

        logger.info(f"UDP通信设置完成，监听端口: {self.listen_port}")

    async def _udp_listener(self):
        """监听来自TouchDesigner的音频数据"""
        logger.info("开始监听TouchDesigner音频数据")

        while self.is_connected:
            try:
                # 非阻塞接收UDP数据
                loop = asyncio.get_event_loop()
                data, addr = await loop.sock_recvfrom(self.listen_socket, 4096)

                if len(data) > 8:  # 至少要有头部信息
                    # 解析音频数据包格式: [4字节长度][4字节类型][音频数据]
                    length = struct.unpack('<I', data[:4])[0]
                    msg_type = struct.unpack('<I', data[4:8])[0]

                    if msg_type == 1:  # 音频数据类型
                        audio_data = data[8:8 + length]
                        if len(audio_data) > 0:
                            # 转发到豆包
                            await self.send_audio(audio_data)
                            logger.debug(f"从TD接收并转发音频: {len(audio_data)} 字节")
                    elif msg_type == 2:  # 文本消息类型
                        text_data = data[8:8 + length].decode('utf-8')
                        await self.send_text(text_data)
                        logger.info(f"从TD接收并转发文本: {text_data}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"UDP监听异常: {e}")
                await asyncio.sleep(0.1)

    async def disconnect(self) -> None:
        """断开连接"""
        logger.info("开始断开TouchDesigner适配器连接")

        # 停止UDP监听
        if self._udp_listener_task:
            self._udp_listener_task.cancel()
            try:
                await self._udp_listener_task
            except asyncio.CancelledError:
                pass

        # 关闭socket
        if self.udp_socket:
            self.udp_socket.close()
        if self.listen_socket:
            self.listen_socket.close()

        # 停止响应接收任务
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        # 断开豆包连接
        if self.client:
            await self.client.stop()
            self.client = None

        self.is_connected = False
        logger.info("TouchDesigner适配器已断开连接")

    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据到豆包"""
        if not self.is_connected or not self.client:
            return False

        try:
            await self.client.push_audio(audio_data)
            return True
        except Exception as e:
            logger.error(f"发送音频到豆包失败: {e}")
            return False

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收来自豆包的音频数据流"""
        while self.is_connected:
            try:
                response = await asyncio.wait_for(self.response_queue.get(), timeout=1.0)
                if response.get('event') == protocol.ServerEvent.TTS_RESPONSE:
                    audio_data = response.get('payload_msg')
                    if isinstance(audio_data, bytes):
                        # 同时发送到TouchDesigner
                        await self._send_audio_to_td(audio_data)
                        yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break

    async def _send_audio_to_td(self, audio_data: bytes):
        """发送音频数据到TouchDesigner"""
        try:
            # UDP最大数据包大小限制 (通常是65507字节，但我们用更安全的大小)
            max_udp_size = 8192 - 8  # 减去头部8字节

            # 如果音频数据太大，需要分片发送
            if len(audio_data) > max_udp_size:
                # 分片发送
                chunk_size = max_udp_size
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                for i in range(total_chunks):
                    start = i * chunk_size
                    end = min(start + chunk_size, len(audio_data))
                    chunk = audio_data[start:end]

                    # 构造分片包: [4字节长度][4字节类型(4=音频分片)][2字节chunk_id][2字节total_chunks][音频数据]
                    length = len(chunk) + 4  # 加上chunk_id和total_chunks的4字节
                    msg_type = 4  # 音频分片类型

                    packet = (struct.pack('<I', length) + struct.pack('<I', msg_type) + struct.pack(
                        '<H',
                        i
                        ) + struct.pack('<H', total_chunks) + chunk)

                    # 发送到TouchDesigner
                    loop = asyncio.get_event_loop()
                    await loop.sock_sendto(self.udp_socket, packet, (self.td_ip, self.td_port))

                logger.debug(f"发送音频到TD (分片): {len(audio_data)} 字节, {total_chunks} 个分片")
            else:
                # 构造UDP数据包: [4字节长度][4字节类型(1=音频)][音频数据]
                length = len(audio_data)
                msg_type = 1  # 音频类型

                packet = struct.pack('<I', length) + struct.pack('<I', msg_type) + audio_data

                # 发送到TouchDesigner
                loop = asyncio.get_event_loop()
                await loop.sock_sendto(self.udp_socket, packet, (self.td_ip, self.td_port))

                logger.debug(f"发送音频到TD: {len(audio_data)} 字节")

        except Exception as e:
            logger.warning(f"发送音频到TouchDesigner失败: {e}")

    async def send_text(self, text: str) -> bool:
        """发送文本消息到豆包"""
        if not self.is_connected or not self.client:
            return False

        try:
            await self.client.request_say_hello(text)

            # 同时发送状态到TouchDesigner
            await self._send_status_to_td(f"发送文本: {text}")

            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def _send_status_to_td(self, status: str):
        """发送状态信息到TouchDesigner"""
        try:
            status_data = status.encode('utf-8')
            length = len(status_data)
            msg_type = 3  # 状态类型

            packet = struct.pack('<I', length) + struct.pack('<I', msg_type) + status_data

            loop = asyncio.get_event_loop()
            await loop.sock_sendto(self.udp_socket, packet, (self.td_ip, self.td_port))

        except Exception as e:
            logger.warning(f"发送状态到TouchDesigner失败: {e}")

    async def _receive_responses(self):
        """接收豆包响应的后台任务"""
        while self.is_connected and self.client:
            try:
                response = await self.client.on_response()
                if response:
                    await self.response_queue.put(response)

                    # 发送事件状态到TouchDesigner
                    if response.get('event'):
                        event_name = str(response.get('event'))
                        await self._send_status_to_td(f"事件: {event_name}")

            except Exception as e:
                logger.error(f"接收豆包响应失败: {e}")
                break

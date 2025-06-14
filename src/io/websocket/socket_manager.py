import asyncio
import json
import queue
import socket
import threading
from dataclasses import dataclass
from typing import Optional, Callable

from src.utils.logger import logger


class SocketAudioManager:
    """Socket音频管理类，处理socket客户端的音频输入输出"""

    def __init__(self, config: SocketConfig):
        self.config = config
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_address: Optional[tuple] = None

        # 音频处理回调
        self.audio_input_callback: Optional[Callable[[bytes], None]] = None

        # 控制标志
        self.is_running = False
        self.is_connected = False

        # 线程和队列
        self.receive_thread: Optional[threading.Thread] = None
        self.audio_output_queue = queue.Queue()

    async def start_server(self) -> None:
        """启动Socket服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.config.host, self.config.port))
            self.server_socket.listen(1)
            self.is_running = True

            logger.info(f"🔌 Socket服务器启动: {self.config.host}:{self.config.port}")
            logger.info("等待客户端连接...")

            # 在单独线程中等待连接
            await asyncio.get_event_loop().run_in_executor(None, self._accept_connection)

        except Exception as e:
            logger.error(f"Socket服务器启动失败: {e}")
            raise

    def _accept_connection(self) -> None:
        """接受客户端连接"""
        try:
            self.client_socket, self.client_address = self.server_socket.accept()
            self.is_connected = True
            logger.info(f"✅ 客户端已连接: {self.client_address}")

            # 启动接收线程
            self.receive_thread = threading.Thread(target=self._receive_audio_thread)
            self.receive_thread.daemon = True
            self.receive_thread.start()

        except Exception as e:
            logger.error(f"接受连接失败: {e}")

    def _receive_audio_thread(self) -> None:
        """接收音频数据的线程"""
        buffer = b""

        while self.is_running and self.is_connected:
            try:
                # 接收数据头（4字节长度）
                while len(buffer) < 4:
                    chunk = self.client_socket.recv(4 - len(buffer))
                    if not chunk:
                        logger.info("客户端断开连接")
                        self.is_connected = False
                        return
                    buffer += chunk

                # 解析数据长度
                data_length = int.from_bytes(buffer[:4], byteorder='big')
                buffer = buffer[4:]

                # 接收音频数据
                while len(buffer) < data_length:
                    chunk = self.client_socket.recv(data_length - len(buffer))
                    if not chunk:
                        logger.info("客户端断开连接")
                        self.is_connected = False
                        return
                    buffer += chunk

                # 提取音频数据
                audio_data = buffer[:data_length]
                buffer = buffer[data_length:]

                # 调用音频输入回调
                if self.audio_input_callback and len(audio_data) > 0:
                    logger.debug(f"🎤 接收到音频数据: {len(audio_data)}字节")
                    self.audio_input_callback(audio_data)

            except Exception as e:
                logger.error(f"接收音频数据错误: {e}")
                self.is_connected = False
                break

    def send_audio_output(self, audio_data: bytes, format_type: str = "pcm") -> None:
        """发送音频输出到客户端"""
        if not self.is_connected or not self.client_socket:
            return

        try:
            # 创建消息
            message = {
                "type": "audio_output",
                "format": format_type,
                "data_length": len(audio_data)
            }

            # 发送消息头
            message_json = json.dumps(message).encode('utf-8')
            message_length = len(message_json)

            # 发送: 消息长度(4字节) + 消息内容 + 音频数据
            self.client_socket.send(message_length.to_bytes(4, byteorder='big'))
            self.client_socket.send(message_json)
            self.client_socket.send(audio_data)

            logger.debug(f"🔊 发送音频数据: {len(audio_data)}字节 ({format_type})")

        except Exception as e:
            logger.error(f"发送音频输出错误: {e}")
            self.is_connected = False

    def set_audio_input_callback(self, callback: Callable[[bytes], None]) -> None:
        """设置音频输入回调函数"""
        self.audio_input_callback = callback

    def cleanup(self) -> None:
        """清理Socket资源"""
        self.is_running = False
        self.is_connected = False

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)

        logger.info("Socket连接已清理")


@dataclass
class SocketConfig:
    """Socket配置数据类"""
    host: str
    port: int

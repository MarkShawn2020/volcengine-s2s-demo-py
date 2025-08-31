import asyncio
import gzip
import json
import logging
import time
import uuid
from typing import Dict, Any

import websockets
from websockets import ClientConnection, State

from src.volcengine import protocol

logger = logging.getLogger(__name__)


async def connect_ws(config):
    return await websockets.connect(
        config['base_url'], additional_headers=config['headers'], ping_interval=5
        )


seq = 0


class VolcengineClient:
    def __init__(self, config: Dict[str, Any], bot_name: str = "小塔", tts_config: Dict[str, Any] = None):
        self.config = config
        self.bot_name = bot_name
        self.tts_config = tts_config

        self.ws: ClientConnection | None = None
        self.logid = ""

        self.is_running = False
        self.is_connected = False  # connection
        self.is_alive = False  # session
        self.session_id = str(uuid.uuid4())
        
        # 保活机制相关
        self.keep_alive_enabled = True
        self.keep_alive_interval = 5.0  # 5秒发送一次静音音频
        self.connection_timeout = config.get('reconnect_timeout', 300.0)  # 默认5分钟，测试用
        self.keep_alive_task: asyncio.Task | None = None
        self.connection_start_time = 0.0
        self.last_audio_time = 0.0
        self.is_reconnecting = False  # 防止重连重入
        self.keep_alive_count = 0  # 累计保活次数
        
        logger.info(f"🚀 启动对话会话 (ID: {self.session_id[:8]}...)")

    @property
    def is_active(self) -> bool:
        return (self.ws is not None and self.ws.state == State.OPEN and self.is_alive)

    async def start(self) -> None:
        """建立WebSocket连接"""
        try:
            self.is_running = True
            logger.info(f"url: {self.config['base_url']}, headers: {self.config['headers']}")
            self.ws = await connect_ws(self.config)
            self.logid = self.ws.response_headers.get("X-Tt-Logid") if hasattr(self.ws, 'response_headers') else None
            logger.info(f"dialog server response logid: {self.logid}")

            await self.request_start_connection()

            await self.request_start_session()
            
            # 记录连接开始时间
            self.connection_start_time = time.time()
            self.last_audio_time = time.time()
            self.keep_alive_count = 0
            
            # 启动保活任务
            if self.keep_alive_enabled and (self.keep_alive_task is None or self.keep_alive_task.done()):
                self.keep_alive_task = asyncio.create_task(self.keep_alive_worker())
                logger.info(f"保活任务已启动，间隔:{self.keep_alive_interval}秒，重连超时:{self.connection_timeout}秒")

        except Exception as e:
            logger.warning(f"failed to connect, reason: {e}")

    async def request_start_connection(self) -> None:
        """
        区别于 @connect_websocket_server，这个是用于主动向火山发起一次连接请求，即：
        1. connect to server
        2. build a connection
        3. build a session
        """
        try:
            start_connection_request = bytearray(protocol.generate_header())
            start_connection_request.extend(int(1).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            start_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            start_connection_request.extend(payload_bytes)
            logger.info("requesting start-connection")
            await self.ws.send(start_connection_request)
            logger.info("requested start-connection")
            self.is_connected = True
        except Exception as e:
            logger.warning(f"failed to request start-connection, reason: {e}")

    async def request_stop_connection(self):
        """发送结束连接请求"""
        if not self.is_connected: return

        self.is_connected = False
        try:
            finish_connection_request = bytearray(protocol.generate_header())
            finish_connection_request.extend(int(2).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_connection_request.extend(payload_bytes)
            logger.info("requesting stop-connection")
            await self.ws.send(finish_connection_request)
            logger.info("requested stop-connection")

        except Exception as e:
            logger.warning(f"failed to finish connection: {e}")

    async def request_start_session(self) -> None:
        """发送StartSession请求"""
        try:
            # 动态构建start_session_req
            request_params = {
                "dialog": {
                    "bot_name": self.bot_name
                }
            }
            
            # 添加TTS配置（如果提供）
            if self.tts_config:
                request_params["tts"] = self.tts_config
            payload_bytes = str.encode(json.dumps(request_params))
            payload_bytes = gzip.compress(payload_bytes)
            start_session_request = bytearray(protocol.generate_header())
            start_session_request.extend(int(100).to_bytes(4, 'big'))
            start_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            start_session_request.extend(str.encode(self.session_id))
            start_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            start_session_request.extend(payload_bytes)
            logger.info("requesting start-session")
            await self.ws.send(start_session_request)
            logger.info("requested start-session")
            self.is_alive = True
        except Exception as e:
            logger.warning(f"failed to request start-session, reason: {e}")

    async def request_stop_session(self):
        """发送结束会话请求"""
        if not self.is_active: return

        self.is_alive = False
        try:
            finish_session_request = bytearray(protocol.generate_header())
            finish_session_request.extend(int(102).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            finish_session_request.extend(str.encode(self.session_id))
            finish_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_session_request.extend(payload_bytes)
            logger.info("requesting stop-session")
            await self.ws.send(finish_session_request)
            logger.info("requested stop-session")
        except Exception as e:
            logger.warning(f"failed to stop session, reason: {e}")

    async def push_text(self, content: str) -> None:
        """发送SayHello事件"""
        say_hello_request = bytearray(protocol.generate_header())
        say_hello_request.extend(int(300).to_bytes(4, 'big'))  # SayHello事件ID: 300
        say_hello_request.extend((len(self.session_id)).to_bytes(4, 'big'))
        say_hello_request.extend(str.encode(self.session_id))

        payload_data = {
            "content": content
            }
        payload_bytes = str.encode(json.dumps(payload_data, ensure_ascii=False))
        payload_bytes = gzip.compress(payload_bytes)
        say_hello_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        say_hello_request.extend(payload_bytes)
        logger.info(f"requesting say-hello, content: {content}")
        await self.ws.send(say_hello_request)
        logger.info(f"requested say-hello")

    async def push_chat_tts_text(self, content: str, start: bool = True, end: bool = True) -> None:
        """发送ChatTTSText事件"""
        chat_tts_request = bytearray(protocol.generate_header())
        chat_tts_request.extend(int(500).to_bytes(4, 'big'))  # ChatTTSText事件ID: 500
        chat_tts_request.extend((len(self.session_id)).to_bytes(4, 'big'))
        chat_tts_request.extend(str.encode(self.session_id))

        payload_data = {
            "start": start,
            "end": end,
            "content": content
        }
        payload_bytes = str.encode(json.dumps(payload_data, ensure_ascii=False))
        payload_bytes = gzip.compress(payload_bytes)
        chat_tts_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        chat_tts_request.extend(payload_bytes)
        
        logger.info(f"requesting chat-tts-text, content: {content}, start: {start}, end: {end}")
        await self.ws.send(chat_tts_request)
        logger.info(f"requested chat-tts-text")

    def generate_silence_audio(self, duration_ms: int = 100) -> bytes:
        """生成静音音频数据 (PCM格式: 16kHz, int16, 小端序)"""
        sample_rate = 16000
        samples_count = int(sample_rate * duration_ms / 1000)
        silence_data = bytearray(samples_count * 2)  # int16 = 2 bytes per sample
        return bytes(silence_data)

    async def push_audio(self, audio: bytes) -> None:
        global seq

        if not self.is_active: return

        try:
            seq += 1
            task_request = bytearray(
                protocol.generate_header(
                    message_type=protocol.CLIENT_AUDIO_ONLY_REQUEST, serial_method=protocol.NO_SERIALIZATION
                    )
                )
            task_request.extend(int(200).to_bytes(4, 'big'))
            task_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            task_request.extend(str.encode(self.session_id))
            payload_bytes = gzip.compress(audio)
            task_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
            task_request.extend(payload_bytes)
            push_result = await self.ws.send(task_request)
            
            # 更新最后音频发送时间
            self.last_audio_time = time.time()
            
            if seq % 100 == 0:
                logger.debug(f"({seq}) 🏠 --> 📡 {len(payload_bytes)} bytes, result: {push_result}")

        except Exception as e:
            logger.warning(f"failed to upload audio, reason: {e}")

    async def on_response(self) -> Dict[str, Any] | None:
        if not self.is_active: return None

        try:
            # logger.debug("waiting for response")
            # 设置超时，让程序能够定期检查is_running状态
            response = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
            data = protocol.parse_response(response)
            # logger.debug(f"on parsed-response")
            return data
        except asyncio.TimeoutError:
            # 超时时返回None，让调用方重新检查is_running状态
            return None
        except Exception as e:
            logger.warning(f"failed to receive server response, reason: {e}")

    async def keep_alive_worker(self) -> None:
        """保活任务：定期发送静音音频"""
        while self.is_running and self.keep_alive_enabled:
            try:
                await asyncio.sleep(self.keep_alive_interval)
                
                if not self.is_active:
                    continue
                
                # 检查是否需要发送静音音频
                current_time = time.time()
                if current_time - self.last_audio_time >= self.keep_alive_interval:
                    silence_audio = self.generate_silence_audio(100)  # 100ms静音
                    await self.push_audio(silence_audio)
                    self.keep_alive_count += 1
                    logger.debug(f"发送保活静音音频 #{self.keep_alive_count}")
                
                # 检查连接是否需要重连
                connection_duration = current_time - self.connection_start_time
                if connection_duration >= self.connection_timeout:
                    logger.info(f"连接时间过长({connection_duration:.1f}秒 >= {self.connection_timeout}秒)，准备重连")
                    await self.reconnect()
                    # 重连后跳出当前循环，让新的保活任务接管
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"保活任务异常: {e}")

    async def reconnect(self) -> None:
        """轻量级重连：只重启session，保持WebSocket连接"""
        if self.is_reconnecting:
            logger.debug("已在重连中，跳过")
            return
            
        self.is_reconnecting = True
        try:
            logger.info("开始会话重连...")
            
            # 停止当前会话
            if self.is_alive:
                try:
                    await self.request_stop_session()
                except Exception as e:
                    logger.warning(f"停止会话失败: {e}")
            
            # 重新生成会话ID并启动新会话
            self.session_id = str(uuid.uuid4())
            self.connection_start_time = time.time()
            self.last_audio_time = time.time() 
            self.keep_alive_count = 0
            
            try:
                await self.request_start_session()
                logger.info(f"会话重连成功，新会话ID: {self.session_id[:8]}...")
            except Exception as e:
                logger.warning(f"启动新会话失败: {e}")
                self.is_running = False
            
        except Exception as e:
            logger.warning(f"会话重连失败: {e}")
            self.is_running = False
        finally:
            self.is_reconnecting = False

    async def stop(self) -> None:
        """优雅关闭WebSocket连接，包括发送结束请求"""
        if not self.is_running: return

        logger.info("stopping")
        self.is_running = False

        try:
            # 停止保活任务
            if self.keep_alive_task and not self.keep_alive_task.done():
                self.keep_alive_task.cancel()
                try:
                    await self.keep_alive_task
                except asyncio.CancelledError:
                    pass
                self.keep_alive_task = None
                logger.info("保活任务已停止")
            
            # 尝试发送结束会话请求
            await self.request_stop_session()

            # 尝试发送结束连接请求
            await self.request_stop_connection()

            if self.ws:
                await self.ws.close()
                self.ws = None
            logger.info("stopped")
        except Exception as e:
            logger.warning(f"failed to stop, reason: {e}")

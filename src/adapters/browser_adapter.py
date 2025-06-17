import json
import asyncio
import logging
import uuid
from typing import Dict, Any, AsyncGenerator
import websockets

from src.adapters.base import AudioAdapter, AdapterType, BrowserConnectionConfig
from src.volcengine.client import VoicengineClient
from src.volcengine import protocol

logger = logging.getLogger(__name__)


class BrowserAudioAdapter(AudioAdapter):
    """浏览器音频适配器 - 内嵌代理服务器"""
    
    def __init__(self, config: BrowserConnectionConfig):
        super().__init__(config.params)
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self._receiver_task = None
        self.proxy_server = None
        self.server_task = None
    
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.BROWSER
    
    async def connect(self) -> bool:
        """启动内嵌代理服务器"""
        try:
            host = "localhost"
            port = self._find_available_port(8765)
            proxy_url = f"ws://{host}:{port}"
            
            # 启动内嵌代理服务器
            self.proxy_server = ProxyServer(host, port, self.config)
            self.server_task = asyncio.create_task(self.proxy_server.start())
            
            # 等待服务器启动
            await asyncio.sleep(0.5)
            
            # 连接到代理服务器
            self.ws = await websockets.connect(proxy_url)
            
            # 发送认证信息
            auth_message = {
                "type": "auth",
                "app_id": self.config.get("app_id"),
                "access_token": self.config.get("access_token")
            }
            await self.ws.send(json.dumps(auth_message))
            
            # 等待认证响应
            response = await self.ws.recv()
            auth_response = json.loads(response)
            
            if auth_response.get("type") == "auth_success":
                self.is_connected = True
                self.session_id = auth_response.get("session_id")
                # 启动接收任务
                self._receiver_task = asyncio.create_task(self._receive_messages())
                logger.info(f"浏览器适配器连接成功，会话ID: {self.session_id[:8]}...")
                logger.info(f"代理服务器运行在 {proxy_url}")
                return True
            else:
                logger.error(f"认证失败: {auth_response}")
                return False
                
        except Exception as e:
            logger.error(f"浏览器适配器连接失败: {e}")
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
        
        self.is_connected = False
        logger.info("浏览器适配器已断开连接")
    
    def _find_available_port(self, start_port: int) -> int:
        """查找可用端口"""
        import socket
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"无法在{start_port}-{start_port+99}范围内找到可用端口")
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据"""
        if not self.is_connected or not self.ws:
            return False
        
        try:
            message = {
                "type": "audio",
                "data": audio_data.hex()  # 转换为十六进制字符串
            }
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
            return False
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收音频数据流"""
        while self.is_connected:
            try:
                audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break
    
    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if not self.is_connected or not self.ws:
            return False
        
        try:
            message = {
                "type": "text",
                "content": text
            }
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False
    
    async def _receive_messages(self):
        """接收消息的后台任务"""
        while self.is_connected and self.ws:
            try:
                message = await self.ws.recv()
                
                # 检查消息类型：二进制数据（音频）或文本数据（JSON）
                if isinstance(message, bytes):
                    # 二进制音频数据，直接放入队列
                    await self.audio_queue.put(message)
                    logger.debug(f"收到二进制音频数据: {len(message)}字节")
                else:
                    # 文本消息，解析为JSON
                    try:
                        data = json.loads(message)
                        if data.get("type") == "audio":
                            # 将十六进制字符串转换回字节
                            audio_data = bytes.fromhex(data.get("data", ""))
                            await self.audio_queue.put(audio_data)
                        elif data.get("type") == "event":
                            logger.info(f"收到事件: {data}")
                    except json.JSONDecodeError:
                        logger.warning(f"收到无效JSON消息: {message}")
                    
            except Exception as e:
                logger.error(f"接收消息失败: {e}")
                break


class ProxyServer:
    """内嵌代理服务器"""
    
    def __init__(self, host: str, port: int, config: Dict[str, Any]):
        self.host = host
        self.port = port
        self.config = config
        self.clients: Dict[str, 'ProxyClient'] = {}
    
    async def start(self):
        """启动代理服务器"""
        logger.info(f"启动内嵌代理服务器 ws://{self.host}:{self.port}")
        
        async def handler(websocket):
            return await self.handle_client(websocket)
        
        async with websockets.serve(handler, self.host, self.port):
            await asyncio.Future()
    
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = str(uuid.uuid4())
        logger.info(f"新客户端连接: {client_id}")
        
        proxy_client = ProxyClient(client_id, websocket, self.config)
        self.clients[client_id] = proxy_client
        
        try:
            await proxy_client.handle()
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {client_id} 正常断开连接")
        except Exception as e:
            logger.error(f"客户端 {client_id} 处理异常: {e}")
        finally:
            await proxy_client.cleanup()
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"客户端 {client_id} 连接关闭")


class ProxyClient:
    """代理客户端"""
    
    def __init__(self, client_id: str, websocket, config: Dict[str, Any]):
        self.client_id = client_id
        self.websocket = websocket
        self.config = config
        self.volcengine_client = None
        self.is_authenticated = False
        self.receive_task = None
        self.running = True
    
    async def handle(self):
        """处理客户端消息"""
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    await self._send_error("Invalid JSON format")
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    await self._send_error(str(e))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} WebSocket连接关闭")
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")
    
    async def _handle_message(self, data: Dict[str, Any]):
        """处理具体消息"""
        message_type = data.get("type")
        
        if message_type == "auth":
            await self._handle_auth(data)
        elif message_type == "audio":
            await self._handle_audio(data)
        elif message_type == "text":
            await self._handle_text(data)
        elif message_type == "ping":
            await self._send_message({"type": "pong"})
        else:
            await self._send_error(f"Unknown message type: {message_type}")
    
    async def _handle_auth(self, data: Dict[str, Any]):
        """处理认证"""
        try:
            app_id = self.config.get("app_id")
            access_token = self.config.get("access_token")
            
            if not app_id or not access_token:
                await self._send_error("Missing app_id or access_token")
                return
            
            ws_config = {
                "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
                "headers": {
                    "X-Api-App-ID": app_id,
                    "X-Api-Access-Key": access_token,
                    "X-Api-Resource-Id": "volc.speech.dialog",
                    "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
                    "X-Api-Connect-Id": str(uuid.uuid4()),
                }
            }
            
            self.volcengine_client = VoicengineClient(ws_config)
            
            from src.volcengine.config import start_session_req
            start_session_req["tts"] = {
                "audio_config": {
                    "format": "pcm",
                    "sample_rate": 24000,
                    "channel": 1
                }
            }
            logger.info("已配置PCM音频格式请求：24kHz Float32")
            
            await self.volcengine_client.start()
            
            if self.volcengine_client.is_active:
                self.is_authenticated = True
                self.receive_task = asyncio.create_task(self._receive_from_volcengine())
                
                await self._send_message({
                    "type": "auth_success",
                    "session_id": self.volcengine_client.session_id
                })
                logger.info(f"客户端 {self.client_id} 认证成功")
            else:
                await self._send_error("Failed to connect to Volcengine")
                
        except Exception as e:
            logger.error(f"认证失败: {e}")
            await self._send_error(f"Authentication failed: {str(e)}")
    
    async def _handle_audio(self, data: Dict[str, Any]):
        """处理音频数据"""
        if not self.is_authenticated or not self.volcengine_client:
            await self._send_error("Not authenticated")
            return
        
        try:
            audio_hex = data.get("data", "")
            audio_data = bytes.fromhex(audio_hex)
            await self.volcengine_client.push_audio(audio_data)
        except Exception as e:
            logger.error(f"处理音频失败: {e}")
            await self._send_error(f"Audio processing failed: {str(e)}")
    
    async def _handle_text(self, data: Dict[str, Any]):
        """处理文本消息"""
        if not self.is_authenticated or not self.volcengine_client:
            await self._send_error("Not authenticated")
            return
        
        try:
            content = data.get("content", "")
            await self.volcengine_client.request_say_hello(content)
        except Exception as e:
            logger.error(f"处理文本失败: {e}")
            await self._send_error(f"Text processing failed: {str(e)}")
    
    async def _receive_from_volcengine(self):
        """从火山引擎接收响应"""
        while self.running and self.is_authenticated and self.volcengine_client:
            try:
                response = await self.volcengine_client.on_response()
                if response:
                    await self._handle_volcengine_response(response)
                elif not self.volcengine_client.is_active:
                    logger.warning("火山引擎连接已断开")
                    break
            except Exception as e:
                logger.error(f"接收火山引擎响应失败: {e}")
                break
        
        logger.info(f"客户端 {self.client_id} 火山引擎接收任务结束")
    
    async def _handle_volcengine_response(self, response: Dict[str, Any]):
        """处理火山引擎响应"""
        event = response.get('event')
        
        if event == protocol.ServerEvent.TTS_RESPONSE:
            audio_data = response.get('payload_msg')
            if isinstance(audio_data, bytes):
                await self._send_audio_binary(audio_data)
        elif event == protocol.ServerEvent.ASR_INFO:
            logger.info("🛑 检测到用户语音活动，转发ASR_INFO事件")
            await self._send_message({
                "type": "event",
                "event": event,
                "data": response.get('payload_msg', {})
            })
        else:
            await self._send_message({
                "type": "event",
                "event": event,
                "data": response.get('payload_msg', {})
            })
    
    async def _send_message(self, message: Dict[str, Any]):
        """发送消息到浏览器"""
        if not self.running:
            return
        
        try:
            await self.websocket.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} 连接已关闭，无法发送消息")
            self.running = False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    async def _send_audio_binary(self, audio_data: bytes):
        """直接发送二进制音频数据"""
        if not self.running:
            return
        
        try:
            await self.websocket.send(audio_data)
            logger.debug(f"发送二进制音频数据: {len(audio_data)}字节")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} 连接已关闭，无法发送音频")
            self.running = False
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
    
    async def _send_error(self, error_message: str):
        """发送错误消息"""
        await self._send_message({
            "type": "error",
            "message": error_message
        })
    
    async def cleanup(self):
        """清理资源"""
        self.running = False
        
        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
        
        if self.volcengine_client:
            try:
                await self.volcengine_client.stop()
            except Exception as e:
                logger.error(f"关闭火山引擎客户端失败: {e}")
            self.volcengine_client = None
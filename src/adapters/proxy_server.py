import asyncio
import json
import uuid
import logging
import websockets
from typing import Dict, Any

from src.volcengine.client import VoicengineClient
from src.volcengine import protocol

logger = logging.getLogger(__name__)


class ProxyServer:
    """代理服务器 - 解决浏览器WebSocket自定义header限制"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, 'ProxyClient'] = {}
    
    async def start(self):
        """启动代理服务器"""
        logger.info(f"启动代理服务器 ws://{self.host}:{self.port}")
        
        # 兼容新版本websockets库的处理方法
        async def handler(websocket):
            return await self.handle_client(websocket)
        
        async with websockets.serve(handler, self.host, self.port):
            await asyncio.Future()  # 运行forever
    
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = str(uuid.uuid4())
        logger.info(f"新客户端连接: {client_id}")
        
        proxy_client = ProxyClient(client_id, websocket)
        self.clients[client_id] = proxy_client
        
        try:
            await proxy_client.handle()
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {client_id} 正常断开连接")
        except Exception as e:
            logger.error(f"客户端 {client_id} 处理异常: {e}")
        finally:
            # 清理资源
            await proxy_client.cleanup()
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"客户端 {client_id} 连接关闭")


class ProxyClient:
    """代理客户端 - 管理单个浏览器连接"""
    
    def __init__(self, client_id: str, websocket):
        self.client_id = client_id
        self.websocket = websocket
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
            app_id = data.get("app_id")
            access_token = data.get("access_token")
            
            if not app_id or not access_token:
                await self._send_error("Missing app_id or access_token")
                return
            
            # 创建火山引擎连接配置
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
            
            # 建立与火山引擎的连接
            self.volcengine_client = VoicengineClient(ws_config)
            
            # 配置PCM音频格式请求 (与main_simple.py保持一致)
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
                # 启动接收任务
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
            # 从十六进制字符串转换回字节
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
            # 音频响应 - 直接发送二进制数据
            audio_data = response.get('payload_msg')
            if isinstance(audio_data, bytes):
                await self._send_audio_binary(audio_data)
        else:
            # 其他事件
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
            # 发送二进制数据，浏览器将收到ArrayBuffer
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


if __name__ == "__main__":
    # 运行代理服务器
    import logging
    import argparse
    
    # 命令行参数
    parser = argparse.ArgumentParser(description="代理服务器")
    parser.add_argument("--host", default="localhost", help="服务器主机")
    parser.add_argument("--port", type=int, default=8765, help="服务器端口")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = ProxyServer(host=args.host, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("代理服务器停止")
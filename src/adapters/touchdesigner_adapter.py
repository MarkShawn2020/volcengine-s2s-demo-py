import asyncio
import json
import logging
import socket
import struct
import threading
import time
from typing import Dict, Any, AsyncGenerator

from src.adapters.base import AudioAdapter, AdapterType, TouchDesignerConnectionConfig
from src.volcengine.client import VoicengineClient

logger = logging.getLogger(__name__)


class TouchDesignerAudioAdapter(AudioAdapter):
    """TouchDesigner音频适配器 - 通过UDP/TCP与TouchDesigner通信"""
    
    def __init__(self, config: TouchDesignerConnectionConfig):
        super().__init__(config.params)
        
        # 网络连接
        self.control_server = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        self.td_control_socket = None
        
        # 任务和线程
        self.control_server_task = None
        self.audio_input_task = None
        self.audio_output_task = None
        self._running = False
        
        # 音频队列
        self.audio_queue = asyncio.Queue()
        self.outgoing_audio_queue = asyncio.Queue()
        
        # 火山引擎客户端
        self.volcengine_client = None
        self.receive_task = None
        
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCH_DESIGNER
    
    async def connect(self) -> bool:
        """启动TouchDesigner适配器服务器"""
        try:
            logger.info("启动TouchDesigner适配器服务器...")
            
            # 创建火山引擎连接
            await self._setup_volcengine_client()
            
            # 启动服务器
            await self._start_servers()
            
            # 启动音频处理任务
            await self._start_audio_tasks()
            
            self.is_connected = True
            self._running = True
            
            logger.info(f"TouchDesigner适配器启动成功")
            logger.info(f"控制端口: {self.config.get('control_port')}")
            logger.info(f"音频输入端口: {self.config.get('audio_input_port')}")
            logger.info(f"音频输出端口: {self.config.get('audio_output_port')}")
            logger.info("等待TouchDesigner连接...")
            
            return True
            
        except Exception as e:
            logger.error(f"TouchDesigner适配器连接失败: {e}")
            return False
    
    async def disconnect(self) -> None:
        """断开连接并清理资源"""
        logger.info("断开TouchDesigner适配器连接...")
        
        self._running = False
        self.is_connected = False
        
        # 停止任务
        if self.control_server_task:
            self.control_server_task.cancel()
        if self.audio_input_task:
            self.audio_input_task.cancel()
        if self.audio_output_task:
            self.audio_output_task.cancel()
        if self.receive_task:
            self.receive_task.cancel()
        
        # 关闭套接字
        if self.td_control_socket:
            try:
                self.td_control_socket.close()
            except:
                pass
        if self.audio_input_socket:
            try:
                self.audio_input_socket.close()
            except:
                pass
        if self.audio_output_socket:
            try:
                self.audio_output_socket.close()
            except:
                pass
        
        # 停止火山引擎客户端
        if self.volcengine_client:
            try:
                await self.volcengine_client.stop()
            except Exception as e:
                logger.error(f"停止火山引擎客户端失败: {e}")
        
        logger.info("TouchDesigner适配器已断开连接")
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据到火山引擎"""
        if not self.is_connected or not self.volcengine_client:
            return False
        
        try:
            await self.volcengine_client.push_audio(audio_data)
            return True
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
            return False
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收音频数据流"""
        while self.is_connected and self._running:
            try:
                audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收音频失败: {e}")
                break
    
    async def send_text(self, text: str) -> bool:
        """发送文本消息到火山引擎"""
        if not self.is_connected or not self.volcengine_client:
            return False
        
        try:
            await self.volcengine_client.request_say_hello(text)
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False
    
    async def _setup_volcengine_client(self):
        """设置火山引擎客户端"""
        ws_config = {
            "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
            "headers": {
                "X-Api-App-ID": self.config.get("app_id"),
                "X-Api-Access-Key": self.config.get("access_token"),
                "X-Api-Resource-Id": "volc.speech.dialog",
                "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
                "X-Api-Connect-Id": f"td_{int(time.time())}"
            }
        }
        
        self.volcengine_client = VoicengineClient(ws_config)
        
        # 配置PCM音频格式
        from src.volcengine.config import start_session_req
        start_session_req["tts"] = {
            "audio_config": {
                "format": "pcm",
                "sample_rate": 24000,
                "channel": 1
            }
        }
        
        await self.volcengine_client.start()
        
        if self.volcengine_client.is_active:
            self.session_id = self.volcengine_client.session_id
            self.receive_task = asyncio.create_task(self._receive_from_volcengine())
            logger.info(f"火山引擎连接成功，会话ID: {self.session_id[:8]}...")
        else:
            raise Exception("火山引擎连接失败")
    
    async def _start_servers(self):
        """启动服务器"""
        # 查找可用端口
        self._find_available_ports()
        
        # 启动控制服务器
        self.control_server_task = asyncio.create_task(self._control_server())
        
        # 启动音频UDP服务器
        await self._setup_audio_sockets()
    
    async def _setup_audio_sockets(self):
        """设置音频UDP套接字"""
        # 音频输入套接字（接收TouchDesigner音频）
        self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_input_socket.bind(('0.0.0.0', self.config.get('audio_input_port')))
        self.audio_input_socket.setblocking(False)
        
        # 音频输出套接字（发送音频到TouchDesigner）
        self.audio_output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_output_socket.setblocking(False)
    
    async def _start_audio_tasks(self):
        """启动音频处理任务"""
        self.audio_input_task = asyncio.create_task(self._audio_input_handler())
        self.audio_output_task = asyncio.create_task(self._audio_output_handler())
    
    async def _control_server(self):
        """TCP控制服务器"""
        server = await asyncio.start_server(
            self._handle_control_client,
            '0.0.0.0',
            self.config.get('control_port')
        )
        
        logger.info(f"控制服务器启动在端口 {self.config.get('control_port')}")
        
        async with server:
            await server.serve_forever()
    
    async def _handle_control_client(self, reader, writer):
        """处理控制客户端连接"""
        addr = writer.get_extra_info('peername')
        logger.info(f"TouchDesigner控制连接来自: {addr}")
        
        try:
            # 发送初始化消息
            await self._send_control_message(writer, {
                'type': 'init',
                'session_id': self.session_id,
                'status': 'ready'
            })
            
            while self._running:
                try:
                    # 读取消息长度
                    length_data = await asyncio.wait_for(reader.read(4), timeout=1.0)
                    if not length_data:
                        break
                    
                    message_length = struct.unpack('<I', length_data)[0]
                    
                    # 读取消息内容
                    message_data = await reader.read(message_length)
                    message = json.loads(message_data.decode('utf-8'))
                    
                    await self._handle_control_message(writer, message)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"控制消息处理错误: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"控制连接错误: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"TouchDesigner控制连接断开: {addr}")
    
    async def _handle_control_message(self, writer, message: Dict[str, Any]):
        """处理控制消息"""
        msg_type = message.get('type')
        
        if msg_type == 'text':
            content = message.get('content', '')
            logger.info(f"收到TouchDesigner文本: {content}")
            await self.send_text(content)
            
        elif msg_type == 'ping':
            await self._send_control_message(writer, {'type': 'pong'})
            
        elif msg_type == 'status':
            await self._send_control_message(writer, {
                'type': 'status_response',
                'connected': self.is_connected,
                'session_id': self.session_id
            })
        else:
            logger.warning(f"未知控制消息类型: {msg_type}")
    
    async def _send_control_message(self, writer, message: Dict[str, Any]):
        """发送控制消息"""
        try:
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            writer.write(length_header + message_bytes)
            await writer.drain()
        except Exception as e:
            logger.error(f"发送控制消息失败: {e}")
    
    async def _audio_input_handler(self):
        """音频输入处理器（从TouchDesigner接收音频）"""
        logger.info("音频输入处理器启动")
        
        while self._running:
            try:
                # 非阻塞接收
                try:
                    data, addr = self.audio_input_socket.recvfrom(4096 + 12)
                except socket.error:
                    await asyncio.sleep(0.001)  # 1ms延迟
                    continue
                
                if len(data) < 12:
                    continue
                
                # 解析音频包头
                timestamp, data_length = struct.unpack('<QI', data[:12])
                audio_data = data[12:12 + data_length]
                
                if len(audio_data) > 0:
                    # 发送到火山引擎
                    await self.send_audio(audio_data)
                    logger.debug(f"收到TouchDesigner音频: {len(audio_data)}字节")
                
            except Exception as e:
                logger.error(f"音频输入处理错误: {e}")
                await asyncio.sleep(0.1)
        
        logger.info("音频输入处理器结束")
    
    async def _audio_output_handler(self):
        """音频输出处理器（发送音频到TouchDesigner）"""
        logger.info("音频输出处理器启动")
        
        while self._running:
            try:
                # 从队列获取音频数据
                audio_data = await asyncio.wait_for(self.outgoing_audio_queue.get(), timeout=1.0)
                
                if audio_data and len(audio_data) > 0:
                    # 发送到TouchDesigner
                    timestamp = int(time.time() * 1000000)
                    header = struct.pack('<QI', timestamp, len(audio_data))
                    packet = header + audio_data
                    
                    try:
                        self.audio_output_socket.sendto(
                            packet, 
                            (self.config.get('td_ip'), self.config.get('audio_output_port'))
                        )
                        logger.debug(f"发送音频到TouchDesigner: {len(audio_data)}字节")
                    except socket.error as e:
                        logger.warning(f"发送音频到TouchDesigner失败: {e}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"音频输出处理错误: {e}")
                await asyncio.sleep(0.1)
        
        logger.info("音频输出处理器结束")
    
    async def _receive_from_volcengine(self):
        """从火山引擎接收响应"""
        logger.info("火山引擎接收任务启动")
        
        while self._running and self.is_connected and self.volcengine_client:
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
        
        logger.info("火山引擎接收任务结束")
    
    def _find_available_ports(self):
        """查找可用端口"""
        import socket
        
        # 查找控制端口
        control_port = self.config.get('control_port', 7003)
        for port in range(control_port, control_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    if hasattr(self.config, 'params'):
                        self.config.params['control_port'] = port
                    else:
                        self.config['control_port'] = port
                    break
            except OSError:
                continue
        else:
            raise RuntimeError(f"无法找到可用的控制端口（尝试范围：{control_port}-{control_port+99}）")
        
        # 查找音频输入端口
        audio_input_port = self.config.get('audio_input_port', 7001)
        for port in range(audio_input_port, audio_input_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(('localhost', port))
                    if hasattr(self.config, 'params'):
                        self.config.params['audio_input_port'] = port
                    else:
                        self.config['audio_input_port'] = port
                    break
            except OSError:
                continue
        else:
            raise RuntimeError(f"无法找到可用的音频输入端口（尝试范围：{audio_input_port}-{audio_input_port+99}）")
        
        # 查找音频输出端口（TouchDesigner监听的端口不需要测试，由TouchDesigner负责）
        audio_output_port = self.config.get('audio_output_port', 7002)
        if hasattr(self.config, 'params'):
            self.config.params['audio_output_port'] = audio_output_port
        else:
            self.config['audio_output_port'] = audio_output_port
    
    async def _handle_volcengine_response(self, response: Dict[str, Any]):
        """处理火山引擎响应"""
        from src.volcengine import protocol
        
        event = response.get('event')
        
        if event == protocol.ServerEvent.TTS_RESPONSE:
            # 音频响应 - 发送到TouchDesigner
            audio_data = response.get('payload_msg')
            if isinstance(audio_data, bytes):
                await self.outgoing_audio_queue.put(audio_data)
                # 也放入本地队列供统一接口使用
                await self.audio_queue.put(audio_data)
        
        elif event == protocol.ServerEvent.ASR_INFO:
            logger.info("🛑 检测到用户语音活动")
            # 清空输出队列，打断AI语音
            while not self.outgoing_audio_queue.empty():
                try:
                    self.outgoing_audio_queue.get_nowait()
                except:
                    break
        
        else:
            # 其他事件记录日志
            logger.info(f"收到火山引擎事件: {event}")
import asyncio
import json
import logging
import struct
import socket
from typing import Dict, Any, AsyncGenerator
from pathlib import Path

from src.adapters.base import AudioAdapter, AdapterType, ConnectionConfig

logger = logging.getLogger(__name__)


class TouchDesignerConnectionConfig(ConnectionConfig):
    """TouchDesigner连接配置"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.td_ip = kwargs.get('td_ip', 'localhost')
        self.td_port = kwargs.get('td_port', 7000)
        self.audio_input_port = kwargs.get('audio_input_port', 7001)
        self.audio_output_port = kwargs.get('audio_output_port', 7002)
        self.control_port = kwargs.get('control_port', 7003)


class TouchDesignerAdapter(AudioAdapter):
    """TouchDesigner音频适配器 - 通过UDP/TCP协议与TouchDesigner通信"""
    
    def __init__(self, config: TouchDesignerConnectionConfig):
        super().__init__(config.params)
        self.config = config
        
        # 网络连接
        self.control_socket = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        
        # 音频缓冲
        self.audio_input_queue = asyncio.Queue(maxsize=100)
        self.audio_output_queue = asyncio.Queue(maxsize=100)
        
        # 任务管理
        self._receiver_task = None
        self._sender_task = None
        self._control_task = None
        
        # 统计信息
        self.stats = {
            'audio_sent': 0,
            'audio_received': 0,
            'control_messages': 0,
            'errors': 0
        }
    
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCHDESIGNER
    
    async def connect(self) -> bool:
        """连接到TouchDesigner"""
        try:
            # 创建控制连接 (TCP)
            await self._connect_control()
            
            # 创建音频输入连接 (UDP)
            await self._connect_audio_input()
            
            # 创建音频输出连接 (UDP)
            await self._connect_audio_output()
            
            # 发送初始化消息
            await self._send_control_message({
                'type': 'init',
                'app_id': self.config.params.get('app_id'),
                'session_id': self.session_id,
                'audio_config': {
                    'sample_rate': 16000,
                    'channels': 1,
                    'format': 'pcm16'
                }
            })
            
            # 启动后台任务
            self._receiver_task = asyncio.create_task(self._audio_receiver_task())
            self._sender_task = asyncio.create_task(self._audio_sender_task())
            self._control_task = asyncio.create_task(self._control_task_handler())
            
            self.is_connected = True
            logger.info(f"TouchDesigner适配器连接成功 - 控制端口:{self.config.control_port}, "
                       f"音频输入:{self.config.audio_input_port}, 音频输出:{self.config.audio_output_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"TouchDesigner适配器连接失败: {e}")
            await self.disconnect()
            return False
    
    async def _connect_control(self):
        """建立控制连接 (TCP)"""
        try:
            reader, writer = await asyncio.open_connection(
                self.config.td_ip, self.config.control_port
            )
            self.control_socket = {'reader': reader, 'writer': writer}
            logger.info(f"控制连接已建立: {self.config.td_ip}:{self.config.control_port}")
        except Exception as e:
            raise Exception(f"无法建立控制连接: {e}")
    
    async def _connect_audio_input(self):
        """建立音频输入连接 (UDP发送)"""
        try:
            self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_input_socket.setblocking(False)
            logger.info(f"音频输入UDP socket已创建，目标: {self.config.td_ip}:{self.config.audio_input_port}")
        except Exception as e:
            raise Exception(f"无法创建音频输入连接: {e}")
    
    async def _connect_audio_output(self):
        """建立音频输出连接 (UDP接收)"""
        try:
            self.audio_output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_output_socket.bind(('0.0.0.0', self.config.audio_output_port))
            self.audio_output_socket.setblocking(False)
            logger.info(f"音频输出UDP socket已绑定到端口: {self.config.audio_output_port}")
        except Exception as e:
            raise Exception(f"无法创建音频输出连接: {e}")
    
    async def disconnect(self) -> None:
        """断开连接"""
        self.is_connected = False
        
        # 取消任务
        for task in [self._receiver_task, self._sender_task, self._control_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 发送断开消息
        if self.control_socket:
            try:
                await self._send_control_message({'type': 'disconnect'})
            except:
                pass
        
        # 关闭连接
        if self.control_socket:
            try:
                self.control_socket['writer'].close()
                await self.control_socket['writer'].wait_closed()
            except:
                pass
            self.control_socket = None
        
        if self.audio_input_socket:
            try:
                self.audio_input_socket.close()
            except:
                pass
            self.audio_input_socket = None
        
        if self.audio_output_socket:
            try:
                self.audio_output_socket.close()
            except:
                pass
            self.audio_output_socket = None
        
        logger.info("TouchDesigner适配器已断开连接")
        logger.info(f"统计信息: {self.stats}")
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """发送音频数据到TouchDesigner"""
        if not self.is_connected or not self.audio_input_socket:
            return False
        
        try:
            # 创建音频包头 (时间戳 + 数据长度)
            timestamp = int(asyncio.get_event_loop().time() * 1000000)  # 微秒时间戳
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data
            
            # 通过UDP发送
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.audio_input_socket.sendto,
                packet,
                (self.config.td_ip, self.config.audio_input_port)
            )
            
            self.stats['audio_sent'] += 1
            return True
            
        except Exception as e:
            logger.error(f"发送音频到TouchDesigner失败: {e}")
            self.stats['errors'] += 1
            return False
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """接收TouchDesigner的音频数据流"""
        while self.is_connected:
            try:
                audio_data = await asyncio.wait_for(
                    self.audio_output_queue.get(), 
                    timeout=1.0
                )
                yield audio_data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收TouchDesigner音频失败: {e}")
                break
    
    async def send_text(self, text: str) -> bool:
        """发送文本消息到TouchDesigner"""
        if not self.is_connected:
            return False
        
        try:
            await self._send_control_message({
                'type': 'text',
                'content': text,
                'timestamp': asyncio.get_event_loop().time()
            })
            return True
        except Exception as e:
            logger.error(f"发送文本到TouchDesigner失败: {e}")
            return False
    
    async def _send_control_message(self, message: Dict[str, Any]):
        """发送控制消息"""
        if not self.control_socket:
            raise Exception("控制连接未建立")
        
        try:
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            writer = self.control_socket['writer']
            writer.write(length_header + message_bytes)
            await writer.drain()
            
            self.stats['control_messages'] += 1
            logger.debug(f"发送控制消息: {message['type']}")
            
        except Exception as e:
            logger.error(f"发送控制消息失败: {e}")
            raise
    
    async def _audio_receiver_task(self):
        """音频接收任务"""
        while self.is_connected and self.audio_output_socket:
            try:
                # 异步接收UDP数据
                data, addr = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.audio_output_socket.recvfrom,
                    4096 + 12  # 音频数据 + 头部
                )
                
                if len(data) < 12:  # 头部最小长度
                    continue
                
                # 解析包头
                timestamp, data_length = struct.unpack('<QI', data[:12])
                audio_data = data[12:12+data_length]
                
                if len(audio_data) != data_length:
                    logger.warning(f"音频数据长度不匹配: 期望{data_length}, 实际{len(audio_data)}")
                    continue
                
                # 放入队列
                try:
                    self.audio_output_queue.put_nowait(audio_data)
                    self.stats['audio_received'] += 1
                except asyncio.QueueFull:
                    # 队列满时丢弃最老的数据
                    try:
                        self.audio_output_queue.get_nowait()
                        self.audio_output_queue.put_nowait(audio_data)
                    except asyncio.QueueEmpty:
                        pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"音频接收任务异常: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(0.1)
    
    async def _audio_sender_task(self):
        """音频发送任务 - 从队列发送音频到TouchDesigner"""
        while self.is_connected:
            try:
                # 这个任务主要处理发送队列，实际发送在send_audio中完成
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"音频发送任务异常: {e}")
                await asyncio.sleep(0.1)
    
    async def _control_task_handler(self):
        """控制消息处理任务"""
        if not self.control_socket:
            return
        
        reader = self.control_socket['reader']
        
        while self.is_connected:
            try:
                # 读取消息长度
                length_data = await reader.readexactly(4)
                message_length = struct.unpack('<I', length_data)[0]
                
                if message_length > 1024 * 1024:  # 1MB限制
                    logger.warning(f"控制消息过大: {message_length}")
                    continue
                
                # 读取消息内容
                message_data = await reader.readexactly(message_length)
                message_json = message_data.decode('utf-8')
                message = json.loads(message_json)
                
                await self._handle_control_message(message)
                
            except asyncio.CancelledError:
                break
            except asyncio.IncompleteReadError:
                logger.info("TouchDesigner控制连接断开")
                break
            except Exception as e:
                logger.error(f"控制消息处理异常: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(0.1)
    
    async def _handle_control_message(self, message: Dict[str, Any]):
        """处理TouchDesigner发来的控制消息"""
        message_type = message.get('type')
        
        if message_type == 'ping':
            # 回复pong
            await self._send_control_message({'type': 'pong'})
            
        elif message_type == 'status_request':
            # 发送状态信息
            await self._send_control_message({
                'type': 'status',
                'connected': self.is_connected,
                'session_id': self.session_id,
                'stats': self.stats
            })
            
        elif message_type == 'audio_config':
            # 音频配置更新
            config = message.get('config', {})
            logger.info(f"TouchDesigner音频配置更新: {config}")
            
        elif message_type == 'volume_control':
            # 音量控制
            volume = message.get('volume', 1.0)
            logger.info(f"TouchDesigner音量控制: {volume}")
            
        else:
            logger.debug(f"收到TouchDesigner控制消息: {message_type}")


# TouchDesigner端示例代码生成
def generate_touchdesigner_code():
    """生成TouchDesigner端的Python代码示例"""
    return '''
# TouchDesigner Python代码示例
# 在Text DAT中使用此代码与Python适配器通信

import socket
import struct
import json
import threading
import time

class VolcEngineInterface:
    def __init__(self):
        self.control_socket = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        self.connected = False
        
        # 配置
        self.python_ip = 'localhost'
        self.control_port = 7003
        self.audio_input_port = 7002  # TD发送音频
        self.audio_output_port = 7001  # TD接收音频
        
    def connect(self):
        """连接到Python适配器"""
        try:
            # 控制连接
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.python_ip, self.control_port))
            
            # 音频输出连接 (TD发送)
            self.audio_output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 音频输入连接 (TD接收)
            self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_input_socket.bind(('0.0.0.0', self.audio_input_port))
            
            self.connected = True
            print("连接成功")
            
            # 启动接收线程
            threading.Thread(target=self._control_receiver, daemon=True).start()
            threading.Thread(target=self._audio_receiver, daemon=True).start()
            
        except Exception as e:
            print(f"连接失败: {e}")
    
    def send_audio(self, audio_data):
        """发送音频数据"""
        if not self.connected or not self.audio_output_socket:
            return
        
        try:
            timestamp = int(time.time() * 1000000)
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data
            
            self.audio_output_socket.sendto(packet, (self.python_ip, self.audio_output_port))
        except Exception as e:
            print(f"发送音频失败: {e}")
    
    def send_control_message(self, message):
        """发送控制消息"""
        if not self.connected or not self.control_socket:
            return
        
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            self.control_socket.send(length_header + message_bytes)
        except Exception as e:
            print(f"发送控制消息失败: {e}")
    
    def _control_receiver(self):
        """控制消息接收线程"""
        while self.connected:
            try:
                length_data = self.control_socket.recv(4)
                if not length_data:
                    break
                
                message_length = struct.unpack('<I', length_data)[0]
                message_data = self.control_socket.recv(message_length)
                message = json.loads(message_data.decode('utf-8'))
                
                self._handle_control_message(message)
                
            except Exception as e:
                print(f"控制接收错误: {e}")
                break
    
    def _audio_receiver(self):
        """音频接收线程"""
        while self.connected:
            try:
                data, addr = self.audio_input_socket.recvfrom(4096 + 12)
                
                if len(data) < 12:
                    continue
                
                timestamp, data_length = struct.unpack('<QI', data[:12])
                audio_data = data[12:12+data_length]
                
                # 在这里处理接收到的音频数据
                self._handle_audio_data(audio_data)
                
            except Exception as e:
                print(f"音频接收错误: {e}")
                break
    
    def _handle_control_message(self, message):
        """处理控制消息"""
        msg_type = message.get('type')
        if msg_type == 'init':
            print("收到初始化消息")
        elif msg_type == 'text':
            print(f"收到文本: {message.get('content')}")
        # 更多消息类型处理...
    
    def _handle_audio_data(self, audio_data):
        """处理音频数据"""
        # 将音频数据发送到TouchDesigner的Audio Device Out等
        # 这里需要根据具体的TouchDesigner设置来实现
        pass

# 使用示例
interface = VolcEngineInterface()
interface.connect()

# 发送文本消息
interface.send_control_message({
    'type': 'text', 
    'content': '你好'
})

# 发送音频数据 (需要从TouchDesigner的音频输入获取)
# audio_data = ... # 从Audio Device In或其他源获取
# interface.send_audio(audio_data)
'''


# 保存TouchDesigner示例代码到文件
def save_touchdesigner_example():
    """保存TouchDesigner示例代码到文件"""
    code = generate_touchdesigner_code()
    file_path = Path(__file__).parent.parent.parent / 'docs' / 'touchdesigner_example.py'
    file_path.parent.mkdir(exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
    
    logger.info(f"TouchDesigner示例代码已保存到: {file_path}")


if __name__ == "__main__":
    save_touchdesigner_example()
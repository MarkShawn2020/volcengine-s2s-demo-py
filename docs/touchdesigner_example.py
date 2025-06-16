
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

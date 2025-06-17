# TouchDesigner语音接口 - 完整版
# 将此代码放入TouchDesigner的Text DAT中

import socket
import struct
import json
import threading
import time
import collections
import math

# 全局接口实例
volc_interface = None

def initialize():
    """初始化语音接口"""
    global volc_interface
    if volc_interface is None:
        volc_interface = VolcEngineInterface()
        volc_interface.connect()
    return volc_interface

def send_text(message):
    """发送文本消息"""
    if volc_interface and volc_interface.connected:
        volc_interface.send_control_message({
            'type': 'text',
            'content': message
        })
        print(f"发送文本: {message}")
    else:
        print("接口未连接")

def send_audio_from_chop(chop_name):
    """从CHOP获取音频数据并发送"""
    if not volc_interface or not volc_interface.connected:
        print("接口未连接")
        return
    
    try:
        chop = op(chop_name)
        if chop and chop.numSamples > 0:
            # 获取音频数据（假设是单声道）
            channel = chop[0] if chop.numChans > 0 else None
            if channel is None:
                return
            
            audio_data = channel.vals
            
            # 转换为16位PCM格式
            pcm_data = []
            for sample in audio_data:
                # 限制到 [-1.0, 1.0] 范围
                sample = max(-1.0, min(1.0, sample))
                pcm_val = int(sample * 32767)
                # 小端格式
                pcm_data.append(pcm_val & 0xFF)
                pcm_data.append((pcm_val >> 8) & 0xFF)
            
            volc_interface.send_audio(bytes(pcm_data))
    
    except Exception as e:
        print(f"发送音频失败: {e}")

def get_audio_buffer():
    """获取接收到的音频缓冲区"""
    if volc_interface:
        return volc_interface.get_audio_buffer()
    return []

def get_connection_status():
    """获取连接状态"""
    if volc_interface:
        return volc_interface.connected
    return False

def reconnect():
    """重新连接"""
    if volc_interface:
        volc_interface.disconnect()
        time.sleep(1)
        volc_interface.connect()

class VolcEngineInterface:
    def __init__(self):
        self.control_socket = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        self.connected = False
        self._stop_threads = False
        
        # 配置
        self.python_ip = 'localhost'
        self.control_port = 7003  # 控制端口
        self.audio_input_port = 7001  # TD发送音频到Python
        self.audio_output_port = 7002  # TD接收Python音频
        
        # 音频缓冲区（循环缓冲）
        self.audio_buffer = collections.deque(maxlen=48000)  # 1秒缓冲
        self.audio_lock = threading.Lock()
        
        # 状态
        self.last_heartbeat = time.time()
        self.session_id = None
        
    def connect(self):
        """连接到Python适配器"""
        try:
            print("正在连接到Python适配器...")
            
            # 控制连接
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.settimeout(5.0)  # 5秒超时
            self.control_socket.connect((self.python_ip, self.control_port))
            self.control_socket.settimeout(None)  # 连接后移除超时
            
            # 音频输出连接 (TD发送)
            self.audio_output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 音频输入连接 (TD接收)
            self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_input_socket.bind(('0.0.0.0', self.audio_input_port))
            self.audio_input_socket.settimeout(0.1)  # 100ms超时，避免阻塞
            
            self.connected = True
            self._stop_threads = False
            print("TouchDesigner语音接口连接成功!")
            
            # 启动接收线程
            threading.Thread(target=self._control_receiver, daemon=True).start()
            threading.Thread(target=self._audio_receiver, daemon=True).start()
            threading.Thread(target=self._heartbeat_thread, daemon=True).start()
            
        except Exception as e:
            print(f"连接失败: {e}")
            self.disconnect()
    
    def disconnect(self):
        """断开连接"""
        print("断开连接...")
        self.connected = False
        self._stop_threads = True
        
        if self.control_socket:
            try:
                self.control_socket.close()
            except:
                pass
            self.control_socket = None
        
        if self.audio_output_socket:
            try:
                self.audio_output_socket.close()
            except:
                pass
            self.audio_output_socket = None
        
        if self.audio_input_socket:
            try:
                self.audio_input_socket.close()
            except:
                pass
            self.audio_input_socket = None
    
    def send_audio(self, audio_data):
        """发送音频数据"""
        if not self.connected or not self.audio_output_socket:
            return False
        
        try:
            timestamp = int(time.time() * 1000000)  # 微秒时间戳
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data
            
            self.audio_output_socket.sendto(packet, (self.python_ip, self.audio_input_port))
            return True
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False
    
    def send_control_message(self, message):
        """发送控制消息"""
        if not self.connected or not self.control_socket:
            return False
        
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            self.control_socket.send(length_header + message_bytes)
            return True
        except Exception as e:
            print(f"发送控制消息失败: {e}")
            self.connected = False
            return False
    
    def get_audio_buffer(self):
        """获取音频缓冲区数据"""
        with self.audio_lock:
            if self.audio_buffer:
                data = list(self.audio_buffer)
                self.audio_buffer.clear()
                return data
        return []
    
    def get_audio_samples(self, count=1024):
        """获取指定数量的音频样本"""
        with self.audio_lock:
            if len(self.audio_buffer) >= count:
                samples = []
                for _ in range(count):
                    if self.audio_buffer:
                        samples.append(self.audio_buffer.popleft())
                return samples
        return []
    
    def get_audio_level(self):
        """获取音频电平（RMS）"""
        with self.audio_lock:
            if not self.audio_buffer:
                return 0.0
            
            # 计算最近1024个样本的RMS
            samples = list(self.audio_buffer)[-1024:]
            if not samples:
                return 0.0
            
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            return rms
    
    def _control_receiver(self):
        """控制消息接收线程"""
        print("控制接收线程启动")
        
        while self.connected and not self._stop_threads:
            try:
                # 读取消息长度
                length_data = self.control_socket.recv(4)
                if not length_data:
                    print("控制连接断开")
                    break
                
                message_length = struct.unpack('<I', length_data)[0]
                
                # 读取消息内容
                message_data = self.control_socket.recv(message_length)
                if not message_data:
                    break
                
                message = json.loads(message_data.decode('utf-8'))
                self._handle_control_message(message)
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"控制接收错误: {e}")
                break
        
        self.connected = False
        print("控制接收线程结束")
    
    def _audio_receiver(self):
        """音频接收线程"""
        print("音频接收线程启动")
        
        while self.connected and not self._stop_threads:
            try:
                data, addr = self.audio_input_socket.recvfrom(4096 + 12)
                
                if len(data) < 12:
                    continue
                
                # 解析音频包头
                timestamp, data_length = struct.unpack('<QI', data[:12])
                audio_data = data[12:12 + data_length]
                
                if len(audio_data) > 0:
                    # 转换PCM数据为浮点数
                    samples = []
                    for i in range(0, len(audio_data) - 1, 2):
                        sample = struct.unpack('<h', audio_data[i:i + 2])[0]
                        samples.append(sample / 32768.0)  # 归一化到 [-1, 1]
                    
                    # 添加到缓冲区
                    with self.audio_lock:
                        self.audio_buffer.extend(samples)
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"音频接收错误: {e}")
                break
        
        print("音频接收线程结束")
    
    def _heartbeat_thread(self):
        """心跳线程"""
        while self.connected and not self._stop_threads:
            try:
                time.sleep(5)  # 每5秒发送一次心跳
                if self.connected:
                    self.send_control_message({'type': 'ping'})
            except:
                break
    
    def _handle_control_message(self, message):
        """处理控制消息"""
        msg_type = message.get('type')
        
        if msg_type == 'init':
            self.session_id = message.get('session_id')
            print(f"收到初始化消息，会话ID: {self.session_id}")
        
        elif msg_type == 'text':
            content = message.get('content', '')
            print(f"AI回复: {content}")
            
        elif msg_type == 'pong':
            self.last_heartbeat = time.time()
            
        elif msg_type == 'status_response':
            status = message.get('connected', False)
            session = message.get('session_id', '')
            print(f"服务器状态: {'连接' if status else '断开'}, 会话: {session}")
        
        else:
            print(f"收到未知消息类型: {msg_type}")

# 全局函数供TouchDesigner调用

def start_interface():
    """启动接口"""
    return initialize()

def stop_interface():
    """停止接口"""
    global volc_interface
    if volc_interface:
        volc_interface.disconnect()
        volc_interface = None

def is_connected():
    """检查连接状态"""
    return get_connection_status()

def send_hello():
    """发送问候"""
    send_text("你好")

def send_question():
    """发送问题"""
    send_text("今天天气怎么样？")

def get_audio_level():
    """获取音频电平"""
    if volc_interface:
        return volc_interface.get_audio_level()
    return 0.0

def update_audio_visualization():
    """更新音频可视化（在Execute DAT中调用）"""
    if not volc_interface or not volc_interface.connected:
        return
    
    # 获取音频电平
    level = volc_interface.get_audio_level()
    
    # 更新可视化组件
    try:
        # 更新音频电平显示
        level_chop = op('audio_level')
        if level_chop:
            level_chop.par.value0 = level
        
        # 更新波形显示
        waveform_chop = op('waveform')
        if waveform_chop:
            samples = volc_interface.get_audio_samples(1024)
            if samples:
                # 这里可以设置波形数据
                pass
                
    except Exception as e:
        print(f"可视化更新错误: {e}")

# 自动初始化
print("TouchDesigner语音接口模块加载完成")
print("调用 start_interface() 开始连接")
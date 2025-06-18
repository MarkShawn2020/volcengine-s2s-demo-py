"""
TouchDesigner音频处理模块
用于在TouchDesigner中处理音频输入输出和与Python后端的UDP通信
"""

import socket
import struct
import threading
import time
import wave
import io
import numpy as np


class TDAudioHandler:
    """TouchDesigner音频处理器"""
    
    def __init__(self, python_host='localhost', python_port=7001, listen_port=7000):
        """
        初始化音频处理器
        
        Args:
            python_host: Python后端主机地址
            python_port: Python后端监听端口
            listen_port: 本地监听端口(接收Python后端的音频)
        """
        self.python_host = python_host
        self.python_port = python_port
        self.listen_port = listen_port
        
        # UDP socket
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 状态
        self.is_running = False
        self.receive_thread = None
        
        # 回调函数
        self.on_audio_received = None  # 接收到音频时的回调
        self.on_status_received = None  # 接收到状态时的回调
        
        # 音频格式配置
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2
        
    def start(self):
        """启动音频处理器"""
        if self.is_running:
            return
            
        try:
            # 绑定接收socket
            self.recv_socket.bind(('0.0.0.0', self.listen_port))
            self.recv_socket.settimeout(1.0)
            
            self.is_running = True
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            print(f"TouchDesigner音频处理器已启动")
            print(f"监听端口: {self.listen_port}")
            print(f"发送目标: {self.python_host}:{self.python_port}")
            
        except Exception as e:
            print(f"启动音频处理器失败: {e}")
            self.is_running = False
            
    def stop(self):
        """停止音频处理器"""
        self.is_running = False
        
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)
            
        try:
            self.send_socket.close()
            self.recv_socket.close()
        except:
            pass
            
        print("TouchDesigner音频处理器已停止")
        
    def send_audio(self, audio_data):
        """
        发送音频数据到Python后端
        
        Args:
            audio_data: 音频数据 (bytes 或 numpy array)
        """
        if not self.is_running:
            return False
            
        try:
            # 转换音频数据为bytes
            if isinstance(audio_data, np.ndarray):
                # 确保是16位整数格式
                if audio_data.dtype != np.int16:
                    audio_data = (audio_data * 32767).astype(np.int16)
                audio_bytes = audio_data.tobytes()
            else:
                audio_bytes = audio_data
                
            # 构造UDP包: [4字节长度][4字节类型(1=音频)][音频数据]
            length = len(audio_bytes)
            msg_type = 1  # 音频类型
            
            packet = struct.pack('<I', length) + struct.pack('<I', msg_type) + audio_bytes
            
            # 发送到Python后端
            self.send_socket.sendto(packet, (self.python_host, self.python_port))
            
            return True
            
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False
            
    def send_text(self, text):
        """
        发送文本消息到Python后端
        
        Args:
            text: 文本内容
        """
        if not self.is_running:
            return False
            
        try:
            text_bytes = text.encode('utf-8')
            length = len(text_bytes)
            msg_type = 2  # 文本类型
            
            packet = struct.pack('<I', length) + struct.pack('<I', msg_type) + text_bytes
            
            self.send_socket.sendto(packet, (self.python_host, self.python_port))
            
            print(f"发送文本: {text}")
            return True
            
        except Exception as e:
            print(f"发送文本失败: {e}")
            return False
            
    def _receive_loop(self):
        """接收循环"""
        print("开始接收来自Python后端的数据")
        
        while self.is_running:
            try:
                data, addr = self.recv_socket.recvfrom(8192)
                
                if len(data) >= 8:
                    # 解析包头
                    length = struct.unpack('<I', data[:4])[0]
                    msg_type = struct.unpack('<I', data[4:8])[0]
                    
                    if msg_type == 1:  # 音频数据
                        audio_data = data[8:8+length]
                        if self.on_audio_received:
                            self.on_audio_received(audio_data)
                        else:
                            print(f"接收到音频数据: {len(audio_data)} 字节")
                            
                    elif msg_type == 3:  # 状态信息
                        status_data = data[8:8+length].decode('utf-8', errors='ignore')
                        if self.on_status_received:
                            self.on_status_received(status_data)
                        else:
                            print(f"状态: {status_data}")
                            
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"接收数据异常: {e}")
                    
    def audio_to_numpy(self, audio_data):
        """
        将音频数据转换为numpy数组
        
        Args:
            audio_data: 音频字节数据
            
        Returns:
            numpy.ndarray: 音频数组
        """
        try:
            # 假设是16位PCM数据
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            # 归一化到-1.0到1.0
            return audio_array.astype(np.float32) / 32768.0
        except Exception as e:
            print(f"音频转换失败: {e}")
            return np.array([])
            
    def numpy_to_audio(self, audio_array):
        """
        将numpy数组转换为音频数据
        
        Args:
            audio_array: 音频numpy数组 (归一化的float32)
            
        Returns:
            bytes: 音频字节数据
        """
        try:
            # 转换为16位整数
            audio_int16 = (audio_array * 32767).astype(np.int16)
            return audio_int16.tobytes()
        except Exception as e:
            print(f"音频转换失败: {e}")
            return b''


# TouchDesigner专用的简化接口
class TDSimpleAudio:
    """TouchDesigner简化音频接口"""
    
    def __init__(self):
        self.handler = TDAudioHandler()
        self.latest_audio = None
        self.latest_status = ""
        
        # 设置回调
        self.handler.on_audio_received = self._on_audio
        self.handler.on_status_received = self._on_status
        
    def _on_audio(self, audio_data):
        """音频接收回调"""
        self.latest_audio = self.handler.audio_to_numpy(audio_data)
        
    def _on_status(self, status):
        """状态接收回调"""
        self.latest_status = status
        
    def start(self):
        """启动"""
        self.handler.start()
        
    def stop(self):
        """停止"""
        self.handler.stop()
        
    def send_audio(self, audio_array):
        """发送音频 (numpy数组)"""
        if audio_array is not None and len(audio_array) > 0:
            audio_bytes = self.handler.numpy_to_audio(audio_array)
            return self.handler.send_audio(audio_bytes)
        return False
        
    def send_text(self, text):
        """发送文本"""
        return self.handler.send_text(text)
        
    def get_latest_audio(self):
        """获取最新接收的音频"""
        audio = self.latest_audio
        self.latest_audio = None  # 清空，避免重复处理
        return audio
        
    def get_latest_status(self):
        """获取最新状态"""
        return self.latest_status
        
    @property
    def is_running(self):
        """是否运行中"""
        return self.handler.is_running


# 全局实例，方便TouchDesigner使用
td_audio = TDSimpleAudio()


def start_audio():
    """启动音频处理"""
    td_audio.start()


def stop_audio():
    """停止音频处理"""
    td_audio.stop()


def send_audio(audio_data):
    """发送音频数据"""
    return td_audio.send_audio(audio_data)


def send_text(text):
    """发送文本"""
    return td_audio.send_text(text)


def get_audio():
    """获取最新音频"""
    return td_audio.get_latest_audio()


def get_status():
    """获取最新状态"""
    return td_audio.get_latest_status()


def is_running():
    """检查是否运行"""
    return td_audio.is_running


if __name__ == "__main__":
    # 测试代码
    print("TouchDesigner音频处理器测试")
    
    def test_audio_callback(audio_data):
        print(f"接收到音频: {len(audio_data)} 字节")
        
    def test_status_callback(status):
        print(f"接收到状态: {status}")
    
    handler = TDAudioHandler()
    handler.on_audio_received = test_audio_callback
    handler.on_status_received = test_status_callback
    
    handler.start()
    
    try:
        # 发送测试文本
        handler.send_text("测试消息")
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("停止测试")
        handler.stop()
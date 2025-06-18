# TouchDesigner简单测试代码
# 将此代码复制到TouchDesigner的Text DAT中进行快速测试

import socket
import struct
import json
import threading
import time

class SimpleTest:
    def __init__(self):
        self.control_socket = None
        self.connected = False
        
        # 配置 - 与Python适配器输出一致
        self.python_ip = 'localhost'
        self.control_port = 7003
        
    def test_connection(self):
        """测试与Python适配器的连接"""
        try:
            print("正在测试连接到Python适配器...")
            
            # 尝试连接控制端口
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.settimeout(5.0)
            self.control_socket.connect((self.python_ip, self.control_port))
            
            print("✅ 控制连接成功!")
            
            # 发送测试消息
            test_message = {
                'type': 'text',
                'content': '测试消息'
            }
            
            message_json = json.dumps(test_message)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            self.control_socket.send(length_header + message_bytes)
            print("✅ 测试消息已发送")
            
            # 等待响应
            try:
                length_data = self.control_socket.recv(4)
                if length_data:
                    message_length = struct.unpack('<I', length_data)[0]
                    message_data = self.control_socket.recv(message_length)
                    response = json.loads(message_data.decode('utf-8'))
                    print(f"✅ 收到响应: {response}")
                else:
                    print("⚠️ 无响应数据")
            except socket.timeout:
                print("⚠️ 响应超时")
            
            self.control_socket.close()
            return True
            
        except Exception as e:
            print(f"❌ 连接测试失败: {e}")
            if self.control_socket:
                self.control_socket.close()
            return False
    
    def test_audio_ports(self):
        """测试音频端口可用性"""
        print("测试音频端口...")
        
        # 测试音频输入端口 (TD发送到Python)
        try:
            audio_out_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_data = b"test_audio_data"
            timestamp = int(time.time() * 1000000)
            header = struct.pack('<QI', timestamp, len(test_data))
            packet = header + test_data
            
            audio_out_socket.sendto(packet, (self.python_ip, 7001))
            audio_out_socket.close()
            print("✅ 音频输入端口 (7001) 测试成功")
        except Exception as e:
            print(f"❌ 音频输入端口测试失败: {e}")
        
        # 测试音频输出端口 (Python发送到TD)
        try:
            audio_in_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            audio_in_socket.bind(('0.0.0.0', 7002))
            audio_in_socket.settimeout(2.0)
            print("✅ 音频输出端口 (7002) 绑定成功")
            audio_in_socket.close()
        except Exception as e:
            print(f"❌ 音频输出端口测试失败: {e}")

# 创建测试实例
test = SimpleTest()

# 运行测试
def run_test():
    """运行完整测试"""
    print("=" * 50)
    print("TouchDesigner 连接测试")
    print("=" * 50)
    
    # 测试控制连接
    if test.test_connection():
        print("✅ 控制连接测试通过")
    else:
        print("❌ 控制连接测试失败")
    
    print("-" * 30)
    
    # 测试音频端口
    test.test_audio_ports()
    
    print("=" * 50)
    print("测试完成")
    print("如果所有测试通过，您可以继续设置完整的音频链")

# 自动运行测试
print("TouchDesigner测试模块已加载")
print("调用 run_test() 开始测试连接")
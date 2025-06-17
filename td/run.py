# TouchDesigner语音接口
import socket
import struct
import json
import threading
import time

# 全局接口实例
volc_interface = None


def initialize():
    """初始化语音接口"""
    global volc_interface
    volc_interface = VolcEngineInterface()
    volc_interface.connect()


def send_text(message):
    """发送文本消息"""
    if volc_interface:
        volc_interface.send_control_message(
            {
                'type': 'text',
                'content': message
                }
            )


def send_audio_from_chop(chop_name):
    """从CHOP获取音频数据并发送"""
    if not volc_interface:
        return

    chop = op(chop_name)
    if chop and chop.numSamples > 0:
        # 获取音频数据
        audio_data = chop[0].vals

        # 转换为PCM格式
        pcm_data = []
        for sample in audio_data:
            pcm_val = int(sample * 32767)
            pcm_data.append(pcm_val & 0xFF)
            pcm_data.append((pcm_val >> 8) & 0xFF)

        volc_interface.send_audio(bytes(pcm_data))


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

        # 音频缓冲
        self.audio_buffer = []

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
            self.audio_input_socket.settimeout(0.1)  # 非阻塞

            self.connected = True
            print("TouchDesigner语音接口连接成功")

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

    def get_audio_buffer(self):
        """获取音频缓冲区数据"""
        if self.audio_buffer:
            data = self.audio_buffer.copy()
            self.audio_buffer.clear()
            return data
        return []

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

                # 处理控制消息
                msg_type = message.get('type')
                if msg_type == 'text':
                    print(f"AI回复: {message.get('content')}")

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
                audio_data = data[12:12 + data_length]

                # 将音频数据添加到缓冲区
                self.audio_buffer.extend(audio_data)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"音频接收错误: {e}")
                break


# 自动初始化
initialize()
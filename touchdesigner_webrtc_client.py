"""
TouchDesigner WebRTC客户端示例脚本

这个脚本展示了如何在TouchDesigner中使用WebSocket DAT与WebRTC适配器通信。
将此脚本的内容放入TouchDesigner的Script DAT中使用。

使用方法:
1. 在TouchDesigner中创建一个WebSocket DAT
2. 设置WebSocket DAT的Network Address为运行适配器的服务器地址
3. 设置端口为8080 (或配置的信令端口)
4. 创建一个Script DAT，将下面的代码放入其中
5. 在WebSocket DAT的回调中调用相应的函数
"""

import json
import base64
import logging

# TouchDesigner全局对象
# me, op, parent 等在TouchDesigner环境中可用

class TouchDesignerWebRTCClient:
    """TouchDesigner WebRTC客户端"""
    
    def __init__(self, websocket_dat_name="websocket1"):
        self.websocket_dat = op(websocket_dat_name)
        self.connected = False
        self.session_id = None
        
        # 音频相关
        self.audio_in_chop = None  # 输入音频CHOP
        self.audio_out_chop = None # 输出音频CHOP
        
        print("TouchDesigner WebRTC客户端初始化完成")
    
    def connect_to_adapter(self, server_ip="localhost", server_port=8080):
        """连接到WebRTC适配器"""
        try:
            # 配置WebSocket DAT
            self.websocket_dat.par.netaddress = server_ip
            self.websocket_dat.par.port = server_port
            self.websocket_dat.par.active = True
            
            print(f"尝试连接到WebRTC适配器: {server_ip}:{server_port}")
            
        except Exception as e:
            print(f"连接失败: {e}")
    
    def on_websocket_connect(self, dat):
        """WebSocket连接建立时的回调"""
        print("WebSocket连接已建立")
        self.connected = True
        
        # 发送SDP offer
        self.send_webrtc_offer()
    
    def on_websocket_disconnect(self, dat):
        """WebSocket断开连接时的回调"""
        print("WebSocket连接已断开")
        self.connected = False
        self.session_id = None
    
    def on_websocket_message(self, dat, rowIndex, message):
        """接收到WebSocket消息时的回调"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "answer":
                self.handle_webrtc_answer(data)
            elif message_type == "audio-response":
                self.handle_audio_response(data)
            elif message_type == "status":
                self.handle_status_message(data)
            else:
                print(f"未知消息类型: {message_type}")
                
        except json.JSONDecodeError:
            print(f"无效的JSON消息: {message}")
        except Exception as e:
            print(f"处理消息失败: {e}")
    
    def send_webrtc_offer(self):
        """发送WebRTC SDP offer"""
        offer = {
            "type": "offer",
            "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",  # 简化的SDP
            "timestamp": me.time.absFrame
        }
        
        self.send_message(offer)
        print("已发送WebRTC offer")
    
    def handle_webrtc_answer(self, data):
        """处理WebRTC SDP answer"""
        print(f"收到WebRTC answer")
        self.session_id = data.get("session_id")
        print(f"会话ID: {self.session_id}")
    
    def handle_audio_response(self, data):
        """处理音频响应"""
        try:
            # 解码base64音频数据
            audio_b64 = data.get("audio", "")
            audio_data = base64.b64decode(audio_b64)
            
            print(f"收到音频数据: {len(audio_data)} 字节")
            
            # 在TouchDesigner中，你可以将音频数据写入Audio Device Out CHOP
            # 或者通过其他方式播放音频
            self.play_audio(audio_data)
            
        except Exception as e:
            print(f"处理音频响应失败: {e}")
    
    def handle_status_message(self, data):
        """处理状态消息"""
        status = data.get("message", "")
        print(f"状态: {status}")
    
    def send_audio(self, audio_data):
        """发送音频数据"""
        try:
            # 将音频数据编码为base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "audio-data",
                "audio": audio_b64,
                "length": len(audio_data),
                "timestamp": me.time.absFrame
            }
            
            self.send_message(message)
            
        except Exception as e:
            print(f"发送音频失败: {e}")
    
    def send_text(self, text):
        """发送文本消息"""
        try:
            message = {
                "type": "text-message",
                "text": text,
                "timestamp": me.time.absFrame
            }
            
            self.send_message(message)
            print(f"发送文本: {text}")
            
        except Exception as e:
            print(f"发送文本失败: {e}")
    
    def send_message(self, message):
        """发送消息到WebSocket"""
        if self.connected and self.websocket_dat:
            try:
                json_message = json.dumps(message)
                self.websocket_dat.sendText(json_message)
            except Exception as e:
                print(f"发送消息失败: {e}")
    
    def play_audio(self, audio_data):
        """播放音频数据"""
        # 在TouchDesigner中实现音频播放
        # 这里需要根据具体的TouchDesigner音频设置来实现
        # 例如：将音频数据写入Audio Device Out CHOP
        
        if self.audio_out_chop:
            # 这里应该实现将音频数据写入CHOP的逻辑
            # TouchDesigner的具体实现会依赖于你的音频路由设置
            pass
        
        print(f"播放音频: {len(audio_data)} 字节")
    
    def capture_audio(self):
        """捕获音频数据"""
        # 从TouchDesigner的Audio Device In CHOP或其他音频源捕获音频
        if self.audio_in_chop and self.audio_in_chop.numSamples > 0:
            # 获取音频数据
            # 这里需要将CHOP数据转换为字节格式
            # 具体实现会依赖于TouchDesigner的音频格式
            
            # 示例：假设我们有一个包含音频数据的CHOP
            try:
                # 获取最新的音频样本
                samples = []
                for i in range(self.audio_in_chop.numChans):
                    channel = self.audio_in_chop[i]
                    for j in range(channel.numSamples):
                        samples.append(channel[j])
                
                # 转换为字节数据 (16-bit PCM)
                import struct
                audio_bytes = b''
                for sample in samples:
                    # 将浮点样本转换为16位整数
                    sample_int = int(sample * 32767)
                    sample_int = max(-32768, min(32767, sample_int))
                    audio_bytes += struct.pack('<h', sample_int)
                
                if len(audio_bytes) > 0:
                    self.send_audio(audio_bytes)
                
            except Exception as e:
                print(f"捕获音频失败: {e}")
    
    def set_audio_chops(self, audio_in_chop_name=None, audio_out_chop_name=None):
        """设置音频输入输出CHOP"""
        if audio_in_chop_name:
            self.audio_in_chop = op(audio_in_chop_name)
            print(f"设置音频输入CHOP: {audio_in_chop_name}")
        
        if audio_out_chop_name:
            self.audio_out_chop = op(audio_out_chop_name)
            print(f"设置音频输出CHOP: {audio_out_chop_name}")


# 全局客户端实例
webrtc_client = None

def initialize_client():
    """初始化WebRTC客户端"""
    global webrtc_client
    webrtc_client = TouchDesignerWebRTCClient("websocket1")  # 替换为你的WebSocket DAT名称
    webrtc_client.set_audio_chops("audioin1", "audioout1")   # 替换为你的音频CHOP名称
    return webrtc_client

def connect_to_server(server_ip="localhost", server_port=8080):
    """连接到服务器"""
    if webrtc_client:
        webrtc_client.connect_to_adapter(server_ip, server_port)

def send_text_message(text):
    """发送文本消息"""
    if webrtc_client:
        webrtc_client.send_text(text)

def capture_and_send_audio():
    """捕获并发送音频"""
    if webrtc_client:
        webrtc_client.capture_audio()

# WebSocket DAT回调函数
# 将这些函数设置为WebSocket DAT的回调

def onConnect(dat):
    """WebSocket连接回调"""
    if webrtc_client:
        webrtc_client.on_websocket_connect(dat)

def onDisconnect(dat):
    """WebSocket断开回调"""
    if webrtc_client:
        webrtc_client.on_websocket_disconnect(dat)

def onReceiveText(dat, rowIndex, message):
    """WebSocket消息接收回调"""
    if webrtc_client:
        webrtc_client.on_websocket_message(dat, rowIndex, message)

# 使用示例：
# 1. 在TouchDesigner中创建Script DAT，将以上代码放入
# 2. 在另一个Script DAT中执行：
#    client = mod.your_script_dat.initialize_client()
#    mod.your_script_dat.connect_to_server("127.0.0.1", 8080)
# 3. 设置WebSocket DAT的回调指向这些函数
# 4. 使用 mod.your_script_dat.send_text_message("Hello") 发送消息
# 5. 使用 mod.your_script_dat.capture_and_send_audio() 发送音频
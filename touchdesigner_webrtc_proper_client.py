"""
TouchDesigner WebRTC 真正客户端脚本

这个脚本展示了如何在TouchDesigner中使用WebRTC DAT和AudioStreamOut CHOP
与真正的WebRTC适配器进行通信。

使用的TouchDesigner组件：
1. WebRTC DAT - 用于WebRTC连接管理
2. AudioStreamOut CHOP - 用于音频流输出
3. Audio Device In CHOP - 用于音频输入捕获
4. Audio Device Out CHOP - 用于本地音频播放
5. WebSocket DAT - 用于信令服务器连接

设置步骤：
1. 创建WebRTC DAT
2. 创建WebSocket DAT用于信令
3. 创建AudioStreamOut CHOP并连接到WebRTC DAT
4. 创建Audio Device In CHOP用于音频输入
5. 创建Audio Device Out CHOP用于音频播放
"""

import json
import logging

# TouchDesigner全局对象
# me, op, parent 等在TouchDesigner环境中可用

class TouchDesignerWebRTCProperClient:
    """TouchDesigner WebRTC真正客户端"""
    
    def __init__(self, 
                 webrtc_dat_name="webrtc1",
                 websocket_dat_name="websocket1", 
                 audio_stream_out_name="audiostreamout1",
                 audio_in_name="audioin1",
                 audio_out_name="audioout1"):
        
        # 核心组件
        self.webrtc_dat = op(webrtc_dat_name)
        self.websocket_dat = op(websocket_dat_name)
        self.audio_stream_out = op(audio_stream_out_name)
        self.audio_in_chop = op(audio_in_name)
        self.audio_out_chop = op(audio_out_name)
        
        # 状态
        self.connected = False
        self.webrtc_connected = False
        self.session_id = None
        
        print("TouchDesigner WebRTC真正客户端初始化完成")
        
    def setup_components(self, server_ip="localhost", signaling_port=8080):
        """设置TouchDesigner组件"""
        
        # 1. 配置WebSocket DAT (用于信令)
        self.websocket_dat.par.netaddress = server_ip
        self.websocket_dat.par.port = signaling_port
        self.websocket_dat.par.active = False  # 先不激活
        
        # 2. 配置WebRTC DAT
        # 注意：WebRTC DAT的具体参数可能因TouchDesigner版本而异
        if hasattr(self.webrtc_dat.par, 'signalingmethod'):
            self.webrtc_dat.par.signalingmethod = 'websocket'  # 使用WebSocket信令
        
        # 3. 配置AudioStreamOut CHOP
        self.audio_stream_out.par.mode = 'WebRTC'  # 设置为WebRTC模式
        self.audio_stream_out.par.webrtc = self.webrtc_dat  # 连接到WebRTC DAT
        self.audio_stream_out.par.active = False  # 先不激活
        
        # 4. 配置Audio Device In CHOP (音频输入)
        if self.audio_in_chop:
            self.audio_in_chop.par.device = ''  # 使用默认输入设备
            self.audio_in_chop.par.active = True
        
        # 5. 配置Audio Device Out CHOP (音频输出/扬声器播放)
        if self.audio_out_chop:
            self.audio_out_chop.par.device = ''  # 使用默认输出设备
            self.audio_out_chop.par.active = True
        
        print(f"组件设置完成，信令服务器: {server_ip}:{signaling_port}")
    
    def connect_to_adapter(self):
        """连接到WebRTC适配器"""
        try:
            # 激活WebSocket连接
            self.websocket_dat.par.active = True
            print("开始连接到WebRTC适配器...")
            
        except Exception as e:
            print(f"连接失败: {e}")
    
    def on_websocket_connect(self, dat):
        """WebSocket连接建立时的回调"""
        print("WebSocket信令连接已建立")
        self.connected = True
        
        # 开始WebRTC连接流程
        self._initiate_webrtc_connection()
    
    def on_websocket_disconnect(self, dat):
        """WebSocket断开连接时的回调"""
        print("WebSocket信令连接已断开")
        self.connected = False
        self.webrtc_connected = False
        self.session_id = None
        
        # 停止音频流
        self.audio_stream_out.par.active = False
    
    def on_websocket_message(self, dat, rowIndex, message):
        """接收到WebSocket信令消息时的回调"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "answer":
                self._handle_webrtc_answer(data)
            elif message_type == "ice-candidate":
                self._handle_ice_candidate(data)
            else:
                print(f"未知信令消息类型: {message_type}")
                
        except json.JSONDecodeError:
            print(f"无效的JSON消息: {message}")
        except Exception as e:
            print(f"处理信令消息失败: {e}")
    
    def _initiate_webrtc_connection(self):
        """发起WebRTC连接"""
        try:
            # 在TouchDesigner中，WebRTC连接通常通过WebRTC DAT的方法发起
            # 具体方法可能因版本而异
            
            # 激活WebRTC DAT
            if hasattr(self.webrtc_dat.par, 'active'):
                self.webrtc_dat.par.active = True
            
            # 如果WebRTC DAT支持创建offer
            if hasattr(self.webrtc_dat, 'createOffer'):
                self.webrtc_dat.createOffer()
            else:
                # 手动发送offer消息
                self._send_webrtc_offer()
                
            print("WebRTC连接流程已启动")
            
        except Exception as e:
            print(f"发起WebRTC连接失败: {e}")
    
    def _send_webrtc_offer(self):
        """发送WebRTC offer (如果需要手动发送)"""
        # 这是一个简化的示例，实际的SDP offer应该由WebRTC DAT生成
        offer = {
            "type": "offer",
            "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
        }
        
        self._send_signaling_message(offer)
        print("已发送WebRTC offer")
    
    def _handle_webrtc_answer(self, data):
        """处理WebRTC answer"""
        try:
            # 将answer设置到WebRTC DAT
            if hasattr(self.webrtc_dat, 'setRemoteDescription'):
                self.webrtc_dat.setRemoteDescription(data["sdp"], "answer")
            
            self.session_id = data.get("session_id")
            print(f"收到WebRTC answer，会话ID: {self.session_id}")
            
            # 启动音频流输出
            self._start_audio_streaming()
            
        except Exception as e:
            print(f"处理WebRTC answer失败: {e}")
    
    def _handle_ice_candidate(self, data):
        """处理ICE candidate"""
        try:
            # 添加ICE candidate到WebRTC DAT
            if hasattr(self.webrtc_dat, 'addIceCandidate'):
                self.webrtc_dat.addIceCandidate(data)
            
            print("已添加ICE candidate")
            
        except Exception as e:
            print(f"处理ICE candidate失败: {e}")
    
    def _start_audio_streaming(self):
        """启动音频流"""
        try:
            # 连接音频输入到AudioStreamOut CHOP
            if self.audio_in_chop and self.audio_stream_out:
                # 在TouchDesigner中，通常通过连线或代码设置输入
                self.audio_stream_out.inputCOMPs = [self.audio_in_chop]
            
            # 激活AudioStreamOut CHOP
            self.audio_stream_out.par.active = True
            
            self.webrtc_connected = True
            print("音频流已启动")
            
        except Exception as e:
            print(f"启动音频流失败: {e}")
    
    def _send_signaling_message(self, message):
        """发送信令消息"""
        if self.connected and self.websocket_dat:
            try:
                json_message = json.dumps(message)
                self.websocket_dat.sendText(json_message)
            except Exception as e:
                print(f"发送信令消息失败: {e}")
    
    def send_text_message(self, text):
        """发送文本消息（通过信令通道）"""
        try:
            message = {
                "type": "text",
                "content": text,
                "timestamp": me.time.absFrame
            }
            
            self._send_signaling_message(message)
            print(f"发送文本: {text}")
            
        except Exception as e:
            print(f"发送文本失败: {e}")
    
    def play_received_audio(self, audio_data: bytes):
        """播放接收到的音频数据到扬声器"""
        try:
            # 在TouchDesigner中，接收到的音频通常通过WebRTC DAT自动处理
            # 如果需要手动播放，可以将音频数据写入Audio Device Out CHOP
            
            if self.audio_out_chop:
                # 这里需要将bytes转换为CHOP数据格式
                # 具体实现依赖于TouchDesigner的音频API
                print(f"播放音频: {len(audio_data)} 字节")
            
        except Exception as e:
            print(f"播放音频失败: {e}")
    
    def get_connection_status(self):
        """获取连接状态"""
        return {
            "websocket_connected": self.connected,
            "webrtc_connected": self.webrtc_connected,
            "session_id": self.session_id,
            "audio_streaming": self.audio_stream_out.par.active.eval() if self.audio_stream_out else False
        }
    
    def disconnect(self):
        """断开连接"""
        try:
            # 停止音频流
            if self.audio_stream_out:
                self.audio_stream_out.par.active = False
            
            # 关闭WebRTC连接
            if self.webrtc_dat and hasattr(self.webrtc_dat.par, 'active'):
                self.webrtc_dat.par.active = False
            
            # 关闭WebSocket连接
            if self.websocket_dat:
                self.websocket_dat.par.active = False
            
            self.connected = False
            self.webrtc_connected = False
            self.session_id = None
            
            print("已断开所有连接")
            
        except Exception as e:
            print(f"断开连接失败: {e}")


# 全局客户端实例
webrtc_proper_client = None

def initialize_proper_client():
    """初始化WebRTC真正客户端"""
    global webrtc_proper_client
    
    webrtc_proper_client = TouchDesignerWebRTCProperClient(
        webrtc_dat_name="webrtc1",           # WebRTC DAT名称
        websocket_dat_name="websocket1",     # WebSocket DAT名称  
        audio_stream_out_name="audiostreamout1",  # AudioStreamOut CHOP名称
        audio_in_name="audioin1",            # Audio Device In CHOP名称
        audio_out_name="audioout1"           # Audio Device Out CHOP名称
    )
    
    return webrtc_proper_client

def setup_and_connect(server_ip="localhost", signaling_port=8080):
    """设置组件并连接"""
    if webrtc_proper_client:
        webrtc_proper_client.setup_components(server_ip, signaling_port)
        webrtc_proper_client.connect_to_adapter()

def send_text_message(text):
    """发送文本消息"""
    if webrtc_proper_client:
        webrtc_proper_client.send_text_message(text)

def get_status():
    """获取连接状态"""
    if webrtc_proper_client:
        return webrtc_proper_client.get_connection_status()
    return {}

def disconnect():
    """断开连接"""
    if webrtc_proper_client:
        webrtc_proper_client.disconnect()

# WebSocket DAT回调函数
def onConnect(dat):
    """WebSocket连接回调"""
    if webrtc_proper_client:
        webrtc_proper_client.on_websocket_connect(dat)

def onDisconnect(dat):
    """WebSocket断开回调"""
    if webrtc_proper_client:
        webrtc_proper_client.on_websocket_disconnect(dat)

def onReceiveText(dat, rowIndex, message):
    """WebSocket消息接收回调"""
    if webrtc_proper_client:
        webrtc_proper_client.on_websocket_message(dat, rowIndex, message)

# WebRTC DAT回调函数（如果支持）
def onWebRTCConnect(dat):
    """WebRTC连接建立回调"""
    print("WebRTC连接已建立")

def onWebRTCDisconnect(dat):
    """WebRTC断开连接回调"""
    print("WebRTC连接已断开")

def onWebRTCAudioTrack(dat, track):
    """WebRTC音频轨道回调"""
    print(f"收到WebRTC音频轨道: {track}")

"""
使用示例：

1. 在TouchDesigner中设置组件：
   - 创建WebRTC DAT命名为 "webrtc1"
   - 创建WebSocket DAT命名为 "websocket1"
   - 创建AudioStreamOut CHOP命名为 "audiostreamout1"
   - 创建Audio Device In CHOP命名为 "audioin1"
   - 创建Audio Device Out CHOP命名为 "audioout1"

2. 在Script DAT中放入此脚本

3. 设置WebSocket DAT的回调指向这些函数：
   - onConnect
   - onDisconnect  
   - onReceiveText

4. 在另一个Script DAT中执行：
   client = mod.your_script_dat.initialize_proper_client()
   mod.your_script_dat.setup_and_connect("127.0.0.1", 8080)

5. 使用功能：
   mod.your_script_dat.send_text_message("Hello")
   status = mod.your_script_dat.get_status()
   mod.your_script_dat.disconnect()

注意事项：
- 确保python端启动了TouchDesignerProperWebRTCAudioAdapter
- AudioStreamOut CHOP将自动通过WebRTC发送音频
- Audio Device Out CHOP用于本地扬声器播放
- WebRTC连接建立后，音频将双向流动
"""
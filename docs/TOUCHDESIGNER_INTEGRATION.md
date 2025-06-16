# TouchDesigner集成指南

## 概述

TouchDesigner适配器为创意工作者提供了专业级的音频接入方案，支持实时音频处理、可视化效果和互动装置。

## 架构设计

### 通信架构
```
TouchDesigner ←→ Python适配器 ←→ 火山引擎API
    (UDP/TCP)      (WebSocket)
```

### 端口分配
- **控制端口 7003** (TCP): 命令和状态通信
- **音频输入 7001** (UDP): Python接收TouchDesigner音频
- **音频输出 7002** (UDP): Python发送音频到TouchDesigner

## 快速开始

### 1. 启动Python适配器
```bash
python main.py --adapter touchdesigner --td-ip localhost
```

### 2. TouchDesigner配置

#### 创建Text DAT
1. 在TouchDesigner中创建新的Text DAT
2. 将以下代码复制到Text DAT中：

```python
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
        volc_interface.send_control_message({
            'type': 'text',
            'content': message
        })

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
                audio_data = data[12:12+data_length]
                
                # 将音频数据添加到缓冲区
                self.audio_buffer.extend(audio_data)
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"音频接收错误: {e}")
                break

# 自动初始化
initialize()
```

#### 创建CHOP网络

1. **Audio Device In CHOP**: 捕获麦克风输入
2. **Audio Filter CHOP**: 音频预处理（可选）
3. **Audio Device Out CHOP**: 播放AI回复音频

#### 创建控制界面

使用Button COMP创建控制按钮：

```python
# 在Button的onOffToOn回调中
def onOffToOn(comp):
    if comp.name == 'send_hello':
        send_text("你好")
    elif comp.name == 'send_question':
        send_text("今天天气怎么样？")
```

## 高级功能

### 实时音频可视化

```python
# 在DAT Execute中添加音频可视化
def onFrameStart(frame):
    if volc_interface and volc_interface.connected:
        audio_data = volc_interface.get_audio_buffer()
        if audio_data:
            # 将音频数据转换为可视化
            update_audio_visualization(audio_data)

def update_audio_visualization(audio_data):
    """更新音频可视化"""
    # 将PCM数据转换为浮点数
    samples = []
    for i in range(0, len(audio_data)-1, 2):
        sample = struct.unpack('<h', audio_data[i:i+2])[0]
        samples.append(sample / 32768.0)
    
    # 更新波形显示CHOP
    waveform_chop = op('waveform_chop')
    if waveform_chop:
        waveform_chop.par.value0 = samples[-1] if samples else 0
```

### 音频效果处理

```python
# 音频实时效果
def apply_audio_effects(audio_data):
    """应用音频效果"""
    # 简单的音量放大
    amplified = []
    for i in range(0, len(audio_data)-1, 2):
        sample = struct.unpack('<h', audio_data[i:i+2])[0]
        sample = int(sample * 1.5)  # 放大1.5倍
        sample = max(-32768, min(32767, sample))  # 限幅
        amplified.extend(struct.pack('<h', sample))
    
    return bytes(amplified)
```

### 智能触发系统

```python
# 声音检测触发
class VoiceActivityDetector:
    def __init__(self, threshold=0.01, min_duration=0.5):
        self.threshold = threshold
        self.min_duration = min_duration
        self.is_speaking = False
        self.speech_start_time = 0
    
    def process_audio(self, audio_data):
        """处理音频，检测语音活动"""
        # 计算音频能量
        energy = self.calculate_energy(audio_data)
        
        current_time = time.time()
        
        if energy > self.threshold:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = current_time
                print("检测到语音开始")
        else:
            if self.is_speaking:
                if current_time - self.speech_start_time > self.min_duration:
                    self.is_speaking = False
                    print("语音结束，触发处理")
                    self.on_speech_end()
    
    def calculate_energy(self, audio_data):
        """计算音频能量"""
        total_energy = 0
        sample_count = len(audio_data) // 2
        
        for i in range(0, len(audio_data)-1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0]
            total_energy += sample * sample
        
        return total_energy / sample_count if sample_count > 0 else 0
    
    def on_speech_end(self):
        """语音结束时的处理"""
        # 可以在这里触发特定的动作
        pass
```

## 创意应用示例

### 1. 音频反应式粒子系统

```python
# 粒子系统控制
def update_particles_from_audio():
    if volc_interface:
        audio_data = volc_interface.get_audio_buffer()
        if audio_data:
            # 计算音频频谱
            fft_data = compute_fft(audio_data)
            
            # 更新粒子参数
            particle_system = op('particle_system')
            particle_system.par.birthrate = fft_data[0] * 100  # 低频控制生成率
            particle_system.par.life = fft_data[1] * 5        # 中频控制生命周期
            particle_system.par.speed = fft_data[2] * 10      # 高频控制速度
```

### 2. 3D空间音频定位

```python
# 3D音频可视化
def create_3d_audio_visualization():
    """创建3D音频可视化"""
    # 根据音频频率分量创建3D对象
    for freq_band in range(10):
        sphere = op(f'sphere_{freq_band}')
        if sphere:
            # 根据频率强度调整大小和位置
            intensity = get_frequency_intensity(freq_band)
            sphere.par.scale = intensity
            sphere.par.ty = freq_band * 0.5
            sphere.par.r = intensity * 255  # 红色分量
```

### 3. 实时歌词显示

```python
# 歌词同步显示
class LyricsDisplay:
    def __init__(self):
        self.current_text = ""
        self.text_display = op('text_display')
    
    def update_lyrics(self, text):
        """更新歌词显示"""
        self.current_text = text
        if self.text_display:
            self.text_display.par.text = text
    
    def animate_text(self):
        """文字动画效果"""
        if self.text_display:
            # 淡入淡出效果
            self.text_display.par.opacity = abs(math.sin(time.time() * 2))
```

## 性能优化

### 音频缓冲优化

```python
# 优化音频缓冲区管理
class AudioBufferManager:
    def __init__(self, max_buffer_size=4096):
        self.max_buffer_size = max_buffer_size
        self.buffer = collections.deque(maxlen=max_buffer_size)
    
    def add_audio(self, audio_data):
        """添加音频数据"""
        self.buffer.extend(audio_data)
    
    def get_latest_audio(self, sample_count):
        """获取最新的音频样本"""
        if len(self.buffer) >= sample_count:
            return list(self.buffer)[-sample_count:]
        return list(self.buffer)
```

### 网络连接优化

```python
# 连接监控和自动重连
def monitor_connection():
    """监控连接状态"""
    if volc_interface and not volc_interface.connected:
        print("连接断开，尝试重连...")
        volc_interface.connect()
```

## 故障排除

### 常见问题

1. **连接失败**
   - 检查Python适配器是否运行
   - 验证IP地址和端口配置
   - 确认防火墙设置

2. **音频无声**
   - 检查Audio Device In/Out配置
   - 验证音频缓冲区数据
   - 测试音频设备硬件

3. **延迟过高**
   - 减小音频缓冲区大小
   - 优化网络连接
   - 降低音频处理复杂度

### 调试技巧

```python
# 添加调试信息
def debug_audio_flow():
    """调试音频流"""
    print(f"连接状态: {volc_interface.connected if volc_interface else 'None'}")
    print(f"缓冲区大小: {len(volc_interface.audio_buffer) if volc_interface else 0}")
    print(f"网络状态: {check_network_status()}")

def check_network_status():
    """检查网络状态"""
    try:
        socket.create_connection(('localhost', 7003), timeout=1)
        return "正常"
    except:
        return "异常"
```

## 扩展开发

### 自定义协议扩展

```python
# 扩展控制协议
def send_custom_command(command, params):
    """发送自定义命令"""
    message = {
        'type': 'custom',
        'command': command,
        'params': params,
        'timestamp': time.time()
    }
    volc_interface.send_control_message(message)

# 示例：音量控制
send_custom_command('volume_control', {'level': 0.8})

# 示例：音效切换
send_custom_command('effect_switch', {'effect': 'reverb', 'strength': 0.5})
```

### 插件开发框架

```python
# TouchDesigner插件基类
class TouchDesignerPlugin:
    def __init__(self, name):
        self.name = name
        self.enabled = True
    
    def on_audio_received(self, audio_data):
        """音频接收事件"""
        pass
    
    def on_text_received(self, text):
        """文本接收事件"""
        pass
    
    def on_connection_changed(self, connected):
        """连接状态变化事件"""
        pass

# 示例插件：音频录制
class AudioRecorderPlugin(TouchDesignerPlugin):
    def __init__(self):
        super().__init__("AudioRecorder")
        self.recording = False
        self.recorded_data = []
    
    def start_recording(self):
        self.recording = True
        self.recorded_data = []
    
    def stop_recording(self):
        self.recording = False
        return self.recorded_data
    
    def on_audio_received(self, audio_data):
        if self.recording:
            self.recorded_data.extend(audio_data)
```

---

通过这个完整的TouchDesigner集成指南，您可以创建专业级的音频互动装置和创意项目。系统提供了丰富的扩展接口，支持各种创意需求。
# TouchDesigner 配置指南

## 概述

本指南详细说明如何在TouchDesigner中配置不同类型的适配器，与豆包语音服务进行实时对话。

## 支持的适配器类型

1. **UDP适配器** - 最简单，使用UDP通信
2. **WebRTC适配器（简化版）** - 使用WebSocket信令
3. **WebRTC适配器（真正版）** - 完整WebRTC实现，需要aiortc

---

## 方案一：UDP适配器（推荐新手）

### Python端启动
```bash
python main.py --adapter touchdesigner --td-ip localhost --td-port 7000
```

### TouchDesigner端配置

#### 1. 基础组件设置
在TouchDesigner中创建以下组件：

**Audio Device In CHOP**
- Name: `audioin1`
- Device: 选择你的麦克风设备
- Active: `On`
- Sample Rate: `16000`
- Format: `16 Bit Int`
- Channels: `Mono`

**Audio Device Out CHOP**
- Name: `audioout1` 
- Device: 选择你的扬声器设备
- Active: `On`

**UDP In DAT**
- Name: `udpin1`
- Network Port: `7000`
- Active: `On`

**UDP Out DAT**
- Name: `udpout1`
- Network Address: `localhost`
- Network Port: `7001`
- Active: `On`

#### 2. 脚本配置
创建一个**Script DAT**，命名为`udp_client_script`，内容如下：

```python
import struct
import numpy as np

# 全局变量
audio_buffer = []
CHUNK_SIZE = 1600  # 100ms at 16kHz

def onCook(dat):
    """每帧调用"""
    # 处理音频输入
    handle_audio_input()
    
    # 处理接收到的音频
    handle_received_audio()

def handle_audio_input():
    """处理麦克风输入"""
    audio_in = op('audioin1')
    if audio_in and audio_in.numChans > 0:
        # 获取音频数据
        audio_data = audio_in[0].vals
        
        # 转换为16位PCM并发送
        if len(audio_data) >= CHUNK_SIZE:
            # 取最新的CHUNK_SIZE个样本
            samples = audio_data[-CHUNK_SIZE:]
            
            # 转换为16位整数
            pcm_data = np.array(samples, dtype=np.float32)
            pcm_data = np.clip(pcm_data * 32767, -32768, 32767).astype(np.int16)
            
            # 发送UDP数据
            udp_out = op('udpout1')
            if udp_out:
                udp_out.sendBytes(pcm_data.tobytes())

def handle_received_audio():
    """处理接收到的音频数据"""
    udp_in = op('udpin1')
    if udp_in and udp_in.numRows > 0:
        # 读取最新的UDP数据
        for i in range(udp_in.numRows):
            try:
                raw_data = udp_in[i, 'data'].val
                if raw_data:
                    # 转换字节数据为音频
                    audio_samples = np.frombuffer(bytes.fromhex(raw_data), dtype=np.int16)
                    # 转换为浮点数并播放
                    float_samples = audio_samples.astype(np.float32) / 32767.0
                    play_audio(float_samples)
            except Exception as e:
                print(f"处理音频数据失败: {e}")

def play_audio(samples):
    """播放音频到扬声器"""
    try:
        audio_out = op('audioout1')
        if audio_out and len(samples) > 0:
            # 这里需要将samples写入Audio Device Out CHOP
            # TouchDesigner的具体实现可能需要调整
            pass
    except Exception as e:
        print(f"播放音频失败: {e}")
```

---

## 方案二：WebRTC适配器（简化版）

### Python端启动
```bash
python main.py --adapter touchdesigner-webrtc --signaling-port 8080
```

### TouchDesigner端配置

#### 1. 基础组件设置

**Audio Device In CHOP**
- Name: `audioin1`
- Device: 选择你的麦克风设备
- Active: `On`
- Sample Rate: `16000`

**Audio Device Out CHOP**
- Name: `audioout1`
- Device: 选择你的扬声器设备  
- Active: `On`

**WebSocket DAT**
- Name: `websocket1`
- Network Address: `localhost`
- Port: `8080`
- Active: `On`
- Auto Reconnect: `On`

#### 2. 脚本配置
创建**Script DAT**，命名为`webrtc_client_script`，复制`touchdesigner_webrtc_client.py`的内容。

#### 3. WebSocket DAT回调设置
在WebSocket DAT的参数面板中设置：
- On Connect: `op('webrtc_client_script').module.onConnect(me)`
- On Disconnect: `op('webrtc_client_script').module.onDisconnect(me)`
- On Receive Text: `op('webrtc_client_script').module.onReceiveText(me, rowIndex, data)`

#### 4. 初始化脚本
创建另一个**Script DAT**用于初始化：

```python
# 初始化WebRTC客户端
client = op('webrtc_client_script').module.initialize_client()
op('webrtc_client_script').module.setup_and_connect("localhost", 8080)
```

---

## 方案三：WebRTC适配器（真正版）

### 前置条件
首先安装aiortc依赖：
```bash
pip install aiortc
```

### Python端启动
```bash
python main.py --adapter touchdesigner-webrtc-proper --signaling-port 8080 --webrtc-port 8081
```

### TouchDesigner端配置

#### 1. 基础组件设置

**Audio Device In CHOP**
- Name: `audioin1`
- Device: 选择你的麦克风设备
- Active: `On`
- Sample Rate: `16000`

**Audio Device Out CHOP**
- Name: `audioout1`
- Device: 选择你的扬声器设备
- Active: `On`

**WebSocket DAT（信令用）**
- Name: `websocket1`
- Network Address: `localhost`
- Port: `8080`
- Active: `On`

**WebRTC DAT**
- Name: `webrtc1`
- 连接到WebSocket DAT进行信令

**AudioStreamOut CHOP**
- Name: `audiostreamout1`
- Mode: `WebRTC`
- WebRTC: 连接到`webrtc1`
- Input: 连接到`audioin1`
- Active: `On`

#### 2. 脚本配置
创建**Script DAT**，复制`touchdesigner_webrtc_proper_client.py`的内容。

#### 3. 连线设置
- `audioin1` → `audiostreamout1` (音频输入到流输出)
- `websocket1` → `webrtc1` (WebSocket信令到WebRTC)
- WebRTC接收的音频 → `audioout1` (WebRTC音频到扬声器)

---

## 测试步骤

### 1. 启动Python服务
根据选择的方案启动对应的Python服务。

### 2. 启动TouchDesigner
打开TouchDesigner项目，确保所有组件都已正确配置。

### 3. 检查连接状态
- 查看Python控制台，应该看到连接成功的消息
- 在TouchDesigner中检查网络组件的连接状态

### 4. 测试音频
- 对着麦克风说话
- 应该能听到豆包的语音回复

---

## 故障排除

### 常见问题

**1. 连接失败**
- 检查IP地址和端口是否正确
- 确认防火墙没有阻止连接
- 检查Python服务是否正常启动

**2. 没有音频输出**
- 检查Audio Device Out CHOP是否选择了正确的播放设备
- 确认音频格式设置正确
- 检查音频数据是否正确传输

**3. WebRTC连接问题**
- 确保aiortc已正确安装（真正版WebRTC）
- 检查WebRTC DAT的配置
- 查看信令消息是否正常交换

**4. 音频质量问题**
- 检查采样率设置（应为16kHz）
- 确认音频格式为16位PCM
- 调整缓冲区大小

### 调试技巧

**1. 启用详细日志**
在Python端添加日志级别：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**2. 监控网络数据**
在TouchDesigner中使用Text DAT显示网络消息：
```python
# 在Script DAT中添加
def debug_message(msg):
    debug_text = op('debug_text')  # Text DAT
    if debug_text:
        debug_text.text = str(msg)
```

**3. 音频数据可视化**
使用Scope CHOP监控音频信号：
- 连接到Audio Device In CHOP查看输入
- 连接到Audio Device Out CHOP查看输出

---

## 性能优化

### 1. 音频延迟优化
- 减小音频缓冲区大小
- 使用更高的采样率（如果网络允许）
- 优化网络连接

### 2. 网络优化
- 使用有线网络连接
- 确保网络带宽充足
- 避免网络拥塞

### 3. TouchDesigner优化
- 降低不必要的帧率
- 优化脚本执行频率
- 关闭不需要的组件

---

## 示例项目文件

建议创建三个TouchDesigner项目文件：
1. `volcengine_udp.toe` - UDP适配器版本
2. `volcengine_webrtc_simple.toe` - 简化WebRTC版本  
3. `volcengine_webrtc_proper.toe` - 真正WebRTC版本

每个项目都包含完整的配置和脚本，可以直接使用。

---

## 总结

- **新手推荐**：从UDP适配器开始，简单可靠
- **进阶用户**：使用简化WebRTC适配器，功能更丰富
- **专业用户**：使用真正WebRTC适配器，支持完整的WebRTC功能

选择适合你需求的方案，按照上述步骤进行配置即可。
# TouchDesigner WebRTC 适配器使用指南

## 概述

TouchDesigner WebRTC适配器通过WebSocket信令服务器与TouchDesigner进行实时音频通信，支持双向音频传输和文本消息交换。

## 架构特点

- **简洁高效**: 使用WebSocket进行信令，避免复杂的WebRTC实现
- **实时通信**: 支持低延迟音频传输
- **双向通信**: 支持音频和文本双向传输
- **易于集成**: 利用TouchDesigner原生WebSocket DAT

## 环境要求

### Python端
- Python 3.8+
- websockets库
- 现有的volcengine-s2s-demo依赖

### TouchDesigner端
- TouchDesigner 2022.28070+
- WebSocket DAT
- Audio Device In/Out CHOP (可选)
- Script DAT

## 快速开始

### 1. Python端设置

```python
from src.adapters import TouchDesignerWebRTCAudioAdapter, TouchDesignerWebRTCConnectionConfig

# 创建配置
config = TouchDesignerWebRTCConnectionConfig(
    signaling_port=8080,
    app_id="your_app_id",
    access_token="your_access_token"
)

# 创建适配器
adapter = TouchDesignerWebRTCAudioAdapter(config)

# 连接
await adapter.connect()
```

### 2. TouchDesigner端设置

#### 步骤1: 创建WebSocket DAT
1. 在TouchDesigner中添加WebSocket DAT
2. 设置参数:
   - Network Address: `localhost` (或Python服务器IP)
   - Network Port: `8080`
   - Active: `On`

#### 步骤2: 创建Script DAT
1. 添加Script DAT
2. 将 `touchdesigner_webrtc_client.py` 的内容复制到Script DAT中

#### 步骤3: 配置WebSocket回调
在WebSocket DAT的Callbacks参数中设置:
- Callbacks DAT: 指向你的Script DAT
- 确保以下回调函数已定义:
  - `onConnect`
  - `onDisconnect` 
  - `onReceiveText`

#### 步骤4: 初始化客户端
在另一个Script DAT或Execute DAT中运行:
```python
# 初始化客户端
client = op('your_script_dat').module.initialize_client()

# 连接到服务器
op('your_script_dat').module.connect_to_server("127.0.0.1", 8080)
```

## 消息协议

### 从TouchDesigner发送到Python

#### 音频数据
```json
{
    "type": "audio-data",
    "audio": "base64_encoded_audio_data",
    "length": 1024,
    "timestamp": 123456
}
```

#### 文本消息
```json
{
    "type": "text-message", 
    "text": "Hello from TouchDesigner",
    "timestamp": 123456
}
```

#### WebRTC Offer
```json
{
    "type": "offer",
    "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
    "timestamp": 123456
}
```

### 从Python发送到TouchDesigner

#### 音频响应
```json
{
    "type": "audio-response",
    "audio": "base64_encoded_audio_data", 
    "length": 1024,
    "timestamp": 123456.789
}
```

#### 状态消息
```json
{
    "type": "status",
    "message": "连接成功",
    "timestamp": 123456.789
}
```

#### WebRTC Answer
```json
{
    "type": "answer",
    "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
    "session_id": "abc123..."
}
```

## 音频处理

### 音频格式
- 采样率: 16kHz
- 位深: 16-bit
- 声道: 单声道 (mono)
- 编码: PCM

### TouchDesigner中的音频路由

#### 音频输入 (发送到Python)
```
Audio Device In CHOP → Script DAT (capture_and_send_audio) → WebSocket DAT → Python
```

#### 音频输出 (从Python接收)
```
Python → WebSocket DAT → Script DAT (handle_audio_response) → Audio Device Out CHOP
```

## 高级配置

### 自定义信令端口
```python
config = TouchDesignerWebRTCConnectionConfig(
    signaling_port=9090,  # 自定义端口
    app_id="your_app_id",
    access_token="your_access_token"
)
```

### 多客户端支持
适配器支持多个TouchDesigner客户端同时连接，每个连接会获得独立的client_id。

### 错误处理
```python
try:
    await adapter.connect()
except Exception as e:
    print(f"连接失败: {e}")
```

## 故障排除

### 常见问题

1. **连接失败**
   - 检查防火墙设置
   - 确认端口未被占用
   - 验证IP地址正确

2. **音频无声音**
   - 检查TouchDesigner音频设备设置
   - 确认音频格式匹配
   - 验证音频CHOP连接

3. **消息不通**
   - 检查JSON格式
   - 确认WebSocket回调设置
   - 查看TouchDesigner控制台日志

### 调试技巧

1. **启用详细日志**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **TouchDesigner控制台**
在TouchDesigner中按F1打开控制台查看Python输出。

3. **网络监控**
使用Wireshark等工具监控WebSocket通信。

## 性能优化

### 音频缓冲
- 适当设置音频缓冲区大小
- 避免频繁的小数据包传输

### 网络优化
- 使用本地网络减少延迟
- 考虑音频压缩 (如有需要)

### TouchDesigner优化
- 设置合适的Timeline FPS
- 优化音频CHOP的Cook参数

## 示例项目

完整的示例TouchDesigner项目文件将包含:
- 配置好的WebSocket DAT
- 音频路由设置
- UI控制面板
- 状态显示

## 技术支持

如遇到问题，请检查:
1. Python端日志输出
2. TouchDesigner控制台信息
3. 网络连接状态
4. 音频设备配置
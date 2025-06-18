# TouchDesigner集成指南

本文档详细说明如何在TouchDesigner中集成豆包端到端语音对话系统。

## 系统架构

```
TouchDesigner                    Python后端                   豆包API
┌─────────────────┐             ┌─────────────────┐          ┌─────────────┐
│  音频输入组件    │   UDP      │  TouchDesigner  │ WebSocket│  豆包语音    │
│  (麦克风)       │ ──────────► │     适配器      │ ────────► │   服务      │
│                 │   7001     │                 │          │             │
│  音频输出组件    │   UDP      │                 │ WebSocket│             │
│  (扬声器)       │ ◄────────── │                 │ ◄──────── │             │
│                 │   7000     │                 │          │             │
│  控制界面       │            │                 │          │             │
└─────────────────┘             └─────────────────┘          └─────────────┘
```

## 快速开始

### 1. 环境准备

确保已安装所有依赖：

```bash
pip install asyncio websockets numpy pyaudio
```

### 2. 启动Python后端

```bash
cd td/
python start_backend.py --td-ip localhost --td-port 7000 --listen-port 7001
```

参数说明：
- `--td-ip`: TouchDesigner的IP地址 (默认: localhost)
- `--td-port`: 发送音频到TouchDesigner的端口 (默认: 7000)
- `--listen-port`: 监听TouchDesigner音频的端口 (默认: 7001)
- `--app-id`: 火山引擎应用ID
- `--access-token`: 火山引擎访问令牌

### 3. TouchDesigner项目设置

#### 步骤1: 创建基础组件

在TouchDesigner中创建以下组件：

1. **Audio Device In CHOP** (名称: `audiodevicein1`)
   - 设置采样率: 16000 Hz
   - 声道: 1 (单声道)

2. **Audio Device Out CHOP** (名称: `audiodeviceout1`)
   - 设置采样率: 16000 Hz
   - 声道: 1 (单声道)

3. **Execute DAT** (名称: `voice_chat_execute`)
   - 复制 `voice_chat_execute.py` 的内容

4. **Script CHOP** (名称: `audio_input_processor`)
   - 复制 `audio_input_script.py` 的内容
   - 连接到 `audiodevicein1`

5. **Script CHOP** (名称: `audio_output_processor`)
   - 复制 `audio_output_script.py` 的内容
   - 连接到 `audiodeviceout1`

#### 步骤2: 添加控制组件

1. **Button COMP** (启用/禁用开关)
   - 设置为Toggle模式
   - 绑定到Execute DAT的Enable参数

2. **Text DAT** (状态显示)
   - 用于显示当前连接状态

3. **Text COMP** (文本输入)
   - 用于发送文本消息

#### 步骤3: 设置参数

在Execute DAT中添加自定义参数：

```python
# 在Execute DAT的参数页面添加：
Enable (Toggle): 启用/禁用语音对话
TD_IP (String): TouchDesigner IP地址 (默认: localhost)
TD_Port (Integer): TouchDesigner端口 (默认: 7000)
Listen_Port (Integer): 监听端口 (默认: 7001)
TextInput (String): 文本输入框
SendText (Pulse): 发送文本按钮
Status (String, Read-only): 当前状态
```

#### 步骤4: 连接组件

```
audiodevicein1 → audio_input_processor → voice_chat_execute
audiodeviceout1 ← audio_output_processor ← voice_chat_execute
button_comp → voice_chat_execute (Enable参数)
text_comp → voice_chat_execute (TextInput参数)
voice_chat_execute → status_display (Status参数)
```

## 详细配置

### Python后端配置

在 `td/start_backend.py` 中可以配置：

```python
# 网络设置
TD_IP = "localhost"          # TouchDesigner IP
TD_PORT = 7000              # 发送到TD的端口
LISTEN_PORT = 7001          # 监听TD的端口

# 豆包API设置
VOLCENGINE_APP_ID = "your_app_id"
VOLCENGINE_ACCESS_TOKEN = "your_token"

# 音频设置
SAMPLE_RATE = 16000         # 采样率
CHANNELS = 1                # 声道数
SAMPLE_WIDTH = 2            # 位深度(16-bit)
```

### TouchDesigner组件配置

#### Execute DAT配置

```python
# voice_chat_execute.py 关键函数：

def onStart():
    """初始化语音对话系统"""
    
def onValueChange(channel, sampleIndex, val, prev):
    """处理参数变化"""
    if channel.name == 'Enable':
        # 启用/禁用语音对话
        
def send_audio_input(audio_chop):
    """发送音频输入到后端"""
    
def get_audio_output():
    """从后端获取音频输出"""
    
def get_status():
    """获取当前状态"""
```

#### Script CHOP配置

**音频输入处理：**
```python
def onCook(scriptOp):
    # 获取音频输入
    audio_input = op('audiodevicein1')
    
    # 发送到后端
    execute_dat.module.send_audio_input(audio_input)
```

**音频输出处理：**
```python
def onCook(scriptOp):
    # 从后端获取音频
    audio_output = execute_dat.module.get_audio_output()
    
    # 输出到CHOP
    if audio_output is not None:
        for sample in audio_output:
            scriptOp.appendSample([sample])
```

## 使用方法

### 基本操作

1. **启动系统**
   - 先启动Python后端: `python td/start_backend.py`
   - 再在TouchDesigner中点击启用按钮

2. **语音对话**
   - 对着麦克风说话，系统会自动发送到豆包
   - 豆包的回复会通过扬声器播放

3. **文本消息**
   - 在文本输入框中输入文本
   - 点击发送按钮发送给豆包

4. **状态监控**
   - 观察状态显示组件了解当前连接状态
   - 查看控制台日志了解详细信息

### 高级功能

#### 自定义音频处理

可以在Script CHOP中添加音频处理逻辑：

```python
def onCook(scriptOp):
    # 获取原始音频
    audio_input = op('audiodevicein1')
    audio_data = audio_input.numpyArray()
    
    # 音频预处理 (降噪、增益等)
    processed_audio = preprocess_audio(audio_data)
    
    # 发送处理后的音频
    execute_dat.module.send_audio_input(processed_audio)
```

#### 状态可视化

在TouchDesigner中可以创建可视化组件显示：

- 音频波形
- 连接状态
- 语音识别结果
- 实时状态信息

```python
# 在Text DAT中显示状态
status = execute_dat.module.get_status()
op('status_text').text = status

# 在Audio Spectrum中显示音频频谱
audio_output = execute_dat.module.get_audio_output()
if audio_output is not None:
    op('audio_spectrum').source = audio_output
```

## 故障排除

### 常见问题

1. **Python后端无法启动**
   - 检查环境变量是否正确设置
   - 确认端口没有被占用
   - 检查防火墙设置

2. **TouchDesigner连接失败**
   - 确认IP地址和端口设置正确
   - 检查网络连接
   - 查看Python后端日志

3. **音频质量问题**
   - 检查采样率设置 (必须是16kHz)
   - 确认声道设置为单声道
   - 调整音频设备设置

4. **延迟问题**
   - 减少音频缓冲区大小
   - 使用有线网络连接
   - 优化TouchDesigner项目性能

### 调试方法

1. **启用详细日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **监控UDP流量**
   ```bash
   # 使用Wireshark或tcpdump监控UDP包
   sudo tcpdump -i lo0 -p udp port 7000 or port 7001
   ```

3. **检查音频数据**
   ```python
   # 在Script CHOP中添加调试输出
   print(f"音频数据长度: {len(audio_data)}")
   print(f"音频数据类型: {type(audio_data)}")
   ```

## 性能优化

### 音频优化

- 使用较小的音频缓冲区 (100ms以内)
- 避免不必要的音频格式转换
- 使用高效的音频设备驱动

### 网络优化

- 使用本地回环接口减少延迟
- 适当设置UDP缓冲区大小
- 避免网络拥塞

### TouchDesigner优化

- 减少不必要的组件
- 使用高效的脚本算法
- 适当设置时间片段

## API参考

### TouchDesigner函数接口

```python
# 主要函数
enable_voice_chat()          # 启用语音对话
disable_voice_chat()         # 禁用语音对话
toggle_voice_chat()          # 切换状态
send_audio(audio_input)      # 发送音频
get_audio()                  # 获取音频输出
send_text(text)              # 发送文本
get_status()                 # 获取状态
is_enabled()                 # 检查是否启用
is_connected()               # 检查是否连接
```

### UDP协议格式

```
音频数据包格式:
[4字节长度][4字节类型][数据内容]

类型定义:
1 = 音频数据
2 = 文本消息
3 = 状态信息
```

## 示例项目

完整的TouchDesigner示例项目包含：

- 基础语音对话功能
- 音频可视化
- 状态监控界面
- 文本输入输出
- 参数控制面板

请参考 `td/examples/` 目录中的示例文件。
# TouchDesigner语音对话系统完整指南

## 概述

本指南将帮助您在TouchDesigner中创建一个完整的语音对话系统，实现与火山引擎语音服务的实时交互。

## 系统架构

```
TouchDesigner ←→ Python适配器 ←→ 火山引擎API
   (UDP/TCP)       (WebSocket)
```

### 端口配置
- **控制端口 7003** (TCP): 命令和状态通信
- **音频输入 7001** (UDP): Python接收TouchDesigner音频
- **音频输出 7002** (UDP): Python发送音频到TouchDesigner

## 第一步：启动Python适配器

### 1.1 命令行启动
```bash
# 基本启动
poetry run python main.py --adapter touchdesigner --td-ip localhost

# 指定TouchDesigner IP（如果不在同一台机器）
poetry run python main.py --adapter touchdesigner --td-ip 192.168.1.100

# 自定义端口（可选）
poetry run python main.py --adapter touchdesigner --td-ip localhost --td-port 7000
```

### 1.2 启动成功标志
您应该看到类似输出：
```
TouchDesigner适配器启动成功
控制端口: 7003
音频输入端口: 7001
音频输出端口: 7002
等待TouchDesigner连接...
```

## 第二步：TouchDesigner项目设置

### 2.1 创建新项目
1. 打开TouchDesigner
2. 创建新项目
3. 保存为 `volc_speech_demo.toe`

### 2.2 创建基础网络结构

#### 创建Text DAT组件
1. 创建一个Text DAT，命名为 `volc_interface`
2. 将 `td/volc_speech_interface.py` 的内容复制到此Text DAT中
3. 设置Text DAT的参数：
   - **Extension**: `.py`
   - **Word Wrap**: Off

#### 创建Execute DAT组件
1. 创建一个Execute DAT，命名为 `main_execute`
2. 将 `td/execute_callbacks.py` 的内容复制到此Execute DAT中
3. 设置Execute DAT的参数：
   - **Active**: On
   - **Frame Start**: On
   - **Frame End**: Off

#### 创建Button回调DAT
1. 创建一个Text DAT，命名为 `button_callbacks`
2. 将 `td/button_callbacks.py` 的内容复制到此Text DAT中

### 2.3 创建音频系统

#### 音频输入链
```
Audio Device In CHOP → Math CHOP → Null CHOP
       ↓
   (命名为audioin1)    (音量控制)   (输出缓冲)
```

**配置步骤：**
1. **Audio Device In CHOP** (`audioin1`):
   - Device: 选择您的麦克风设备
   - Sample Rate: 24000
   - Mono: On
   - Active: On

2. **Math CHOP** (`input_gain`) - 音量控制:
   - CHOP: `audioin1`
   - Multiply: 1.0 (可调节增益)

3. **Null CHOP** (`audio_buffer`):
   - CHOP: `input_gain`
   - 用于音频数据缓冲

#### 简化版音频输入链（推荐）
```
Audio Device In CHOP → Null CHOP
   (audioin1)        (audio_buffer)
```

#### 音频输出链
```
Null CHOP → Math CHOP → Audio Device Out CHOP
(接收缓冲)   (音量控制)     (输出到扬声器)
```

**配置步骤：**
1. **Null CHOP** (`audio_receive`):
   - 用于接收从Python返回的音频

2. **Math CHOP** (`output_gain`) - 音量控制:
   - CHOP: `audio_receive`
   - Multiply: 0.8 (默认音量)

3. **Audio Device Out CHOP** (`audioout1`):
   - CHOP: `output_gain`
   - Device: 选择您的扬声器设备
   - Sample Rate: 24000

#### 简化版音频输出链（推荐）
```
Null CHOP → Audio Device Out CHOP
(audio_receive)    (audioout1)
```

### 2.4 创建控制界面

#### 主控制面板
创建以下Button组件：

1. **连接按钮** (`btn_connect`):
   - Text: "连接"
   - Script: `op('button_callbacks').module.onOffToOn(me)`

2. **断开按钮** (`btn_disconnect`):
   - Text: "断开"
   - Script: `op('button_callbacks').module.onOffToOn(me)`

3. **问候按钮** (`btn_hello`):
   - Text: "你好"
   - Script: `op('button_callbacks').module.onOffToOn(me)`

4. **问题按钮** (`btn_question`):
   - Text: "天气"
   - Script: `op('button_callbacks').module.onOffToOn(me)`

#### 文本输入
1. **Text Field** (`text_input`):
   - 用于输入自定义文本

2. **发送按钮** (`btn_custom_text`):
   - Text: "发送"
   - Script: `op('button_callbacks').module.onOffToOn(me)`

#### 状态显示
1. **连接状态** (`connection_status`):
   - Text TOP显示连接状态

2. **音频电平** (`audio_level_display`):
   - Level CHOP显示音频电平

### 2.5 创建可视化效果

#### 音频波形显示
```
Trail CHOP → Trail TOP → Composite TOP
(音频轨迹)   (波形渲染)   (最终显示)
```

#### 音频频谱
```
Spectrum CHOP → Math CHOP → Line MAT → Line SOP
(频谱分析)     (数据处理)   (材质)     (3D显示)
```

#### 音频反应粒子
```
Audio Level → Math CHOP → Point SOP → Particle SOP
(音量检测)    (映射计算)   (发射点)    (粒子系统)
```

## 第三步：建立连接

### 3.1 启动系统
1. 确保Python适配器正在运行
2. 在TouchDesigner中点击"连接"按钮
3. 检查控制台输出，应该看到连接成功消息

### 3.2 测试音频
1. 点击"你好"按钮发送测试消息
2. 对着麦克风说话测试音频输入
3. 检查是否有音频输出

## 第四步：高级功能实现

### 4.1 实时音频可视化

在Execute DAT中添加：
```python
def onFrameStart(frame):
    # 获取音频电平
    interface = op('volc_interface')
    if interface and hasattr(interface.module, 'get_audio_level'):
        level = interface.module.get_audio_level()
        
        # 更新可视化
        level_chop = op('audio_level')
        if level_chop:
            level_chop.par.value0 = level
        
        # 更新粒子系统
        particles = op('particles1')
        if particles:
            particles.par.birthrate = level * 1000
```

### 4.2 音频效果处理

创建音频效果链：
```
Audio Input → Filter CHOP → Delay CHOP → Reverb CHOP → Output
(原始音频)    (滤波器)     (延迟)      (混响)       (输出)
```

### 4.3 智能触发系统

创建Timer CHOP进行定期检查：
```python
# 在Timer CHOP的回调中
def onTimerPulse(info):
    # 检查音频电平触发
    audio_in = op('audioin1')
    if audio_in and audio_in.numSamples > 0:
        level = abs(audio_in[0].vals[-1])
        if level > 0.1:  # 阈值
            # 触发语音识别
            interface = op('volc_interface')
            if interface:
                interface.module.send_audio_from_chop('audioin1')
```

### 4.4 场景控制

根据语音内容控制场景：
```python
def handle_speech_response(text):
    """根据语音回复控制场景"""
    if "红色" in text:
        # 改变灯光为红色
        light = op('light1')
        if light:
            light.par.colorr = 1
            light.par.colorg = 0
            light.par.colorb = 0
    
    elif "音乐" in text:
        # 播放音乐
        audio_file = op('audiofilein1')
        if audio_file:
            audio_file.par.play = True
```

## 第五步：调试和优化

### 5.1 常见问题解决

**连接失败**
- 检查Python适配器是否运行
- 验证端口7003没有被占用
- 检查防火墙设置

**音频无声**
- 确认Audio Device In/Out设备选择正确
- 检查音频缓冲区大小设置
- 验证采样率匹配（24kHz）

**延迟过高**
- 减小音频缓冲区大小
- 优化网络连接
- 使用有线网络而非WiFi

### 5.2 性能优化

**内存管理**
```python
# 在Execute DAT中定期清理缓冲区
def onFrameStart(frame):
    if frame % 1000 == 0:  # 每1000帧清理一次
        interface = op('volc_interface')
        if interface:
            # 清理音频缓冲区
            interface.module.volc_interface.audio_buffer.clear()
```

**CPU优化**
- 降低不必要的CHOP/TOP分辨率
- 使用GPU加速的operators
- 避免过于复杂的Python计算

### 5.3 调试工具

**日志监控**
```python
def debug_status():
    """调试状态信息"""
    interface = op('volc_interface')
    if interface and interface.module.volc_interface:
        vi = interface.module.volc_interface
        print(f"连接状态: {vi.connected}")
        print(f"音频缓冲区大小: {len(vi.audio_buffer)}")
        print(f"会话ID: {vi.session_id}")
```

**网络测试**
```python
def test_network():
    """测试网络连接"""
    import socket
    try:
        sock = socket.create_connection(('localhost', 7003), timeout=1)
        sock.close()
        print("网络连接正常")
        return True
    except:
        print("网络连接失败")
        return False
```

## 第六步：创意应用示例

### 6.1 交互式装置控制
```python
# 根据语音内容控制装置
def control_installation(speech_text):
    if "开始" in speech_text:
        op('main_sequence').par.play = True
    elif "停止" in speech_text:
        op('main_sequence').par.play = False
    elif "快一点" in speech_text:
        op('main_sequence').par.rate = 2.0
    elif "慢一点" in speech_text:
        op('main_sequence').par.rate = 0.5
```

### 6.2 音乐可视化
```python
# 音频驱动的视觉效果
def update_music_visuals():
    interface = op('volc_interface')
    if interface:
        level = interface.module.get_audio_level()
        
        # 更新材质
        material = op('material1')
        if material:
            material.par.diffuser = level
            material.par.emisr = level * 0.8
        
        # 更新几何体
        geometry = op('sphere1')
        if geometry:
            geometry.par.radx = 1 + level * 2
            geometry.par.rady = 1 + level * 2
            geometry.par.radz = 1 + level * 2
```

### 6.3 智能环境控制
```python
# 环境智能响应
def smart_environment_control(speech_text):
    """智能环境控制"""
    if "太亮了" in speech_text:
        # 调暗灯光
        for light in ["light1", "light2", "light3"]:
            op(light).par.dimmer = 0.3
    
    elif "太暗了" in speech_text:
        # 调亮灯光
        for light in ["light1", "light2", "light3"]:
            op(light).par.dimmer = 1.0
    
    elif "播放音乐" in speech_text:
        # 启动音乐播放
        op('music_player').par.play = True
```

## 第七步：部署和维护

### 7.1 项目打包
1. 保存TouchDesigner项目文件
2. 导出Python脚本到独立文件
3. 创建配置文件记录所有设置参数

### 7.2 远程监控
```python
# 添加远程监控功能
def send_status_update():
    """发送状态更新到远程监控"""
    status = {
        'connected': is_connected(),
        'audio_level': get_audio_level(),
        'timestamp': time.time()
    }
    # 发送到监控服务器
```

### 7.3 自动恢复
```python
# 自动重连机制
def auto_recovery():
    """自动恢复机制"""
    if not is_connected():
        print("检测到连接断开，尝试重连...")
        reconnect()
        
    # 每30秒检查一次
    run("args[0]()", auto_recovery, delayFrames=1800)
```

## 总结

通过本指南，您已经创建了一个完整的TouchDesigner语音对话系统。该系统具备：

- ✅ 实时语音识别和合成
- ✅ 音频可视化效果
- ✅ 智能交互控制
- ✅ 可扩展的创意功能
- ✅ 稳定的网络通信
- ✅ 完整的调试工具

您可以基于这个基础系统继续开发更复杂的创意应用和交互装置。

## 支持和帮助

如有问题，请检查：
1. Python控制台输出
2. TouchDesigner textport信息
3. 网络连接状态
4. 音频设备配置

祝您创作愉快！
# TouchDesigner集成 - 快速设置指南

本指南将指导你在TouchDesigner中快速设置豆包语音对话系统。

## 📋 前提条件

- TouchDesigner 2022.x 或更高版本
- Python 3.8+ 环境
- 已配置的豆包API凭证

## 🚀 快速设置（5分钟）

### 步骤1: 启动Python后端 (1分钟)

```bash
# 在项目根目录运行
cd td/
python start_backend.py
```

看到以下输出表示启动成功：
```
🚀 启动TouchDesigner语音对话后端...
📡 TouchDesigner目标: localhost:7000
👂 监听端口: 7001
✅ TouchDesigner适配器连接成功
```

### 步骤2: 创建TouchDesigner项目 (3分钟)

#### 2.1 创建基础组件

在TouchDesigner中按以下顺序创建组件：

1. **Audio Device In CHOP**
   - 拖拽 "Audio Device In" 到网络视图
   - 重命名为 `audiodevicein1`
   - 设置参数：
     - Sample Rate: 16000
     - Mono: On

2. **Audio Device Out CHOP**
   - 拖拽 "Audio Device Out" 到网络视图
   - 重命名为 `audiodeviceout1`
   - 设置参数：
     - Sample Rate: 16000

3. **Execute DAT**
   - 拖拽 "Execute" DAT 到网络视图
   - 重命名为 `voice_chat_execute`
   - 打开文本编辑器，复制粘贴 [voice_chat_execute.py](voice_chat_execute.py) 的内容

4. **Script CHOP** (音频输入处理)
   - 拖拽 "Script" CHOP 到网络视图
   - 重命名为 `audio_input_processor`
   - 复制粘贴 [audio_input_script.py](audio_input_script.py) 的内容

5. **Script CHOP** (音频输出处理)
   - 拖拽 "Script" CHOP 到网络视图
   - 重命名为 `audio_output_processor`
   - 复制粘贴 [audio_output_script.py](audio_output_script.py) 的内容

#### 2.2 添加控制界面

6. **Button COMP** (启用开关)
   - 拖拽 "Button" COMP 到网络视图
   - 设置为Toggle模式
   - Text: "启用语音对话"

7. **Text COMP** (文本输入)
   - 拖拽 "Text" COMP 到网络视图
   - Text: "在这里输入文本消息"

8. **Text DAT** (状态显示)
   - 拖拽 "Text" DAT 到网络视图
   - 用于显示连接状态

#### 2.3 连接组件

连接组件如下：
```
audiodevicein1 → audio_input_processor
audio_output_processor → audiodeviceout1
```

### 步骤3: 配置参数 (1分钟)

在 `voice_chat_execute` Execute DAT 中：

1. 点击参数面板右上角的 "+" 按钮
2. 添加以下自定义参数：

```
名称: Enable        类型: Toggle    标签: 启用语音对话
名称: Textinput     类型: String    标签: 文本输入
名称: Sendtext      类型: Pulse     标签: 发送文本
名称: Status        类型: String    标签: 状态 (只读)
```

3. 将Button COMP的值绑定到Enable参数
4. 将Text COMP的文本绑定到Textinput参数

## ✅ 测试连接

### 测试步骤：

1. **启动Python后端**
   ```bash
   python td/start_backend.py
   ```

2. **在TouchDesigner中启用**
   - 点击"启用语音对话"按钮
   - 观察状态显示应该显示"已连接"

3. **测试音频**
   - 对着麦克风说"你好"
   - 应该听到豆包的回复

4. **测试文本**
   - 在文本输入框输入"介绍一下你自己"
   - 点击发送按钮
   - 应该听到豆包的语音回复

## 🔧 常见问题解决

### 问题1: Python后端启动失败
```
❌ 错误: 请设置火山引擎的APP_ID和ACCESS_TOKEN
```
**解决方案:**
```bash
# 设置环境变量
export VOLCENGINE_APP_ID="your_app_id"
export VOLCENGINE_ACCESS_TOKEN="your_access_token"

# 或者通过命令行参数
python start_backend.py --app-id your_app_id --access-token your_token
```

### 问题2: TouchDesigner连接失败
```
❌ 状态显示: 连接失败
```
**解决方案:**
1. 确认Python后端正在运行
2. 检查端口是否被占用
3. 确认防火墙设置允许本地连接

### 问题3: 听不到声音
**解决方案:**
1. 检查音频设备设置
2. 确认采样率设置为16000Hz
3. 检查音量设置

### 问题4: 模块导入失败
```
❌ 导入模块失败: No module named 'td'
```
**解决方案:**
1. 确认Python路径设置正确
2. 在Execute DAT开头添加：
```python
import sys
import os
sys.path.append(r"C:\path\to\your\project\py")
```

## 📁 完整项目结构

设置完成后，你的TouchDesigner项目应该包含：

```
TouchDesigner Network:
├── audiodevicein1 (Audio Device In CHOP)
├── audiodeviceout1 (Audio Device Out CHOP)
├── voice_chat_execute (Execute DAT)
├── audio_input_processor (Script CHOP)
├── audio_output_processor (Script CHOP)
├── enable_button (Button COMP)
├── text_input (Text COMP)
└── status_display (Text DAT)
```

## 🎯 下一步

设置完成后，你可以：

1. **自定义界面**: 添加更多控制组件和可视化
2. **音频处理**: 在Script CHOP中添加音频效果
3. **集成其他系统**: 将语音对话集成到你的TouchDesigner项目中
4. **性能优化**: 根据需要调整缓冲区和参数

## 📖 更多信息

- 详细文档: [README.md](README.md)
- API参考: [README.md#API参考](README.md#api参考)
- 示例项目: `td/examples/` 目录

## 🆘 获取帮助

如果遇到问题：

1. 查看控制台日志输出
2. 检查Python后端日志
3. 参考故障排除章节
4. 联系技术支持
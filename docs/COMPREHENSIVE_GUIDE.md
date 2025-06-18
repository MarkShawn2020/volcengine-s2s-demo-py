# 豆包AI语音通话系统 - 完整使用指南

## 项目概述

本项目是基于火山引擎API的高质量实时语音对话系统，支持多种部署场景和接入方式。系统采用现代化的适配器架构模式，可以灵活支持不同的客户端和使用场景。

### 核心特性

- 🎙️ **实时语音对话**: 支持与豆包AI进行低延迟的语音对话
- 🌐 **浏览器支持**: 直接在浏览器中进行语音通话，无需安装插件
- 🎨 **TouchDesigner集成**: 专为创意工作者设计的TouchDesigner音频接入
- 🔧 **模块化架构**: 基于适配器模式，易于扩展新的接入方式
- 📱 **跨平台兼容**: 支持Windows、macOS、Linux等主流操作系统

## 快速开始

### 环境要求

- Python 3.11+
- Poetry (推荐) 或 pip
- 火山引擎豆包AI账号及API凭证

### 安装依赖

使用Poetry（推荐）：
```bash
poetry install
```

或使用pip：
```bash
pip install -r requirements.txt
```

### 配置API凭证

1. 在火山引擎控制台获取API凭证
2. 设置环境变量：
```bash
export VOLC_APP_ID="你的App ID"
export VOLC_ACCESS_KEY="你的Access Key"
export VOLC_APP_KEY="你的App Key"
```

或创建`.env`文件：
```
VOLC_APP_ID=你的App ID
VOLC_ACCESS_KEY=你的Access Key
VOLC_APP_KEY=你的App Key
```

## 使用方式

### 1. 本地模式（推荐用于开发测试）

直接使用本地麦克风和扬声器进行语音对话：

```bash
python main.py --adapter local
```

特点：
- ✅ 最简单的使用方式
- ✅ 低延迟，高质量
- ✅ 支持语音活动检测
- ❌ 仅限本地使用

### 2. 浏览器模式（推荐用于Web应用）

#### 步骤1：启动代理服务器

浏览器WebSocket不支持自定义headers，需要通过代理服务器转发：

```bash
python -m src.adapters.proxy_server
```

默认监听端口：8765

#### 步骤2：打开浏览器页面

有两个可选的浏览器界面：

**基础版（兼容性好）**：
```
static/unified_browser_demo.html
```

**增强版（功能丰富）**：
```
static/enhanced_browser_demo.html
```

#### 步骤3：配置连接

在浏览器页面中配置：
- 代理服务器：`ws://localhost:8765`
- App ID：你的火山引擎App ID
- Access Token：你的火山引擎Access Token

特点：
- ✅ 无需安装客户端
- ✅ 现代化的Web界面
- ✅ 支持移动设备
- ✅ 便于集成到Web应用
- ❌ 需要代理服务器中转

### 3. TouchDesigner模式（推荐用于创意项目）

专为TouchDesigner用户设计的音频接入方式：

#### 步骤1：启动TouchDesigner适配器

```bash
python main.py --adapter touchdesigner --td-ip localhost --td-port 7000
```

参数说明：
- `--td-ip`: TouchDesigner所在机器的IP地址
- `--td-port`: TouchDesigner基础端口（将自动分配音频和控制端口）

#### 步骤2：在TouchDesigner中配置

将生成的示例代码复制到TouchDesigner的Text DAT中：

```python
# 查看完整示例代码
cat docs/touchdesigner_example.py
```

#### 端口分配

- **控制端口**: 7003 (TCP) - 用于发送控制命令和状态信息
- **音频输入**: 7001 (UDP) - TouchDesigner接收音频数据
- **音频输出**: 7002 (UDP) - TouchDesigner发送音频数据

特点：
- ✅ 专为创意工作设计
- ✅ 低延迟UDP音频传输
- ✅ 丰富的控制接口
- ✅ 支持实时音频处理
- ❌ 需要TouchDesigner软件

## 浏览器端详细说明

### 增强版浏览器界面特性

我们提供了全新设计的增强版浏览器界面（`enhanced_browser_demo.html`），具有以下特性：

#### 🎨 现代化设计
- 响应式设计，支持移动端和桌面端
- 毛玻璃效果和渐变背景
- 直观的状态指示和动画效果

#### 🎤 智能语音控制
- 一键开始/停止录音
- 实时音量显示和可视化
- 自动音频格式优化（16kHz, 单声道）

#### 💬 完整对话体验
- 实时对话记录显示
- 支持文本和语音混合输入
- 消息时间戳和发送状态

#### 📊 系统监控
- 详细的连接状态显示
- 实时日志查看
- 浮动状态提示

#### 🔧 高级功能
- 自动重连机制
- 心跳保活
- 音频缓冲优化

### 使用技巧

1. **音频权限**：首次使用需要授权麦克风权限
2. **网络环境**：确保与代理服务器网络连通
3. **音频质量**：建议使用有线网络以获得最佳音频质量
4. **浏览器兼容性**：推荐使用Chrome、Firefox、Safari等现代浏览器

## TouchDesigner集成详解

### 架构设计

TouchDesigner适配器采用三层通信架构：

```
TouchDesigner    ←→    Python适配器    ←→    火山引擎API
     (UDP/TCP)              (WebSocket)
```

### 通信协议

#### 控制通道 (TCP)
- **端口**: 7003
- **格式**: JSON over TCP
- **用途**: 发送文本消息、状态查询、配置更新

示例消息：
```json
{
    "type": "text",
    "content": "你好",
    "timestamp": 1645123456.789
}
```

#### 音频通道 (UDP)
- **输入端口**: 7001 (TouchDesigner → Python)
- **输出端口**: 7002 (Python → TouchDesigner)
- **格式**: 时间戳(8字节) + 长度(4字节) + PCM音频数据

音频包结构：
```
[时间戳:8字节][数据长度:4字节][音频数据:N字节]
```

### TouchDesigner端实现

#### 基础连接类
```python
class VolcEngineInterface:
    def __init__(self):
        self.control_socket = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        
    def connect(self):
        # 建立TCP控制连接
        # 建立UDP音频连接
        
    def send_audio(self, audio_data):
        # 发送音频到Python适配器
        
    def send_text(self, message):
        # 发送文本消息
```

#### 音频处理流程

1. **音频采集**: 从Audio Device In或其他音频源获取音频数据
2. **格式转换**: 转换为16kHz单声道PCM格式
3. **数据打包**: 添加时间戳和长度头部
4. **UDP发送**: 发送到Python适配器

5. **音频接收**: 从UDP socket接收音频数据
6. **数据解包**: 解析时间戳和音频数据
7. **格式转换**: 转换为TouchDesigner音频格式
8. **音频播放**: 发送到Audio Device Out

### 高级功能

#### 实时音频可视化
- 音频波形显示
- 频谱分析
- 音量计量

#### 智能触发
- 声音检测触发
- 静音检测
- 关键词识别

#### 创意效果
- 音频反应式视觉效果
- 3D空间音频定位
- 实时音频滤镜

## 性能优化建议

### 网络优化
1. **使用有线网络**：WiFi可能导致音频延迟和丢包
2. **QoS配置**：为音频流量设置高优先级
3. **防火墙配置**：确保相关端口未被阻塞

### 音频优化
1. **缓冲大小**：根据网络条件调整音频缓冲区大小
2. **采样率**：使用16kHz以平衡质量和带宽
3. **压缩格式**：在带宽受限时考虑使用音频压缩

### 系统优化
1. **CPU优先级**：为音频处理线程设置高优先级
2. **内存管理**：定期清理音频缓冲区
3. **日志级别**：生产环境使用INFO级别日志

## 故障排除

### 常见问题

#### 连接问题
**问题**: 无法连接到代理服务器
**解决方案**:
1. 检查代理服务器是否正在运行
2. 确认端口8765未被占用
3. 检查防火墙设置

**问题**: TouchDesigner连接失败
**解决方案**:
1. 确认IP地址和端口配置正确
2. 检查网络连通性（ping测试）
3. 验证TouchDesigner脚本是否正确加载

#### 音频问题
**问题**: 无法听到AI回复
**解决方案**:
1. 检查系统音频设备设置
2. 确认浏览器音频权限
3. 测试音频输出设备

**问题**: 录音无声音
**解决方案**:
1. 检查麦克风权限
2. 测试麦克风硬件
3. 调整音频输入增益

#### API问题
**问题**: 认证失败
**解决方案**:
1. 验证API凭证是否正确
2. 检查凭证是否过期
3. 确认API配额是否用尽

### 调试模式

启用详细日志：
```bash
export PYTHONPATH=.
python main.py --adapter local --verbose
```

或在Python代码中：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 监控和统计

#### 连接状态监控
- WebSocket连接状态
- 音频流状态
- 错误率统计

#### 性能指标
- 音频延迟测量
- 包丢失率
- CPU/内存使用率

## 扩展开发

### 创建新适配器

1. **继承基类**：

```python
from src.adapters.base import AudioAdapter
from src.adapters.type import AdapterType


class CustomAdapter(AudioAdapter):
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.CUSTOM
```

2. **实现抽象方法**：
```python
async def connect(self) -> bool:
    # 实现连接逻辑
    
async def send_audio(self, audio_data: bytes) -> bool:
    # 实现音频发送
    
async def receive_audio(self) -> AsyncGenerator[bytes, None]:
    # 实现音频接收
```

3. **注册适配器**：
在`AdapterFactory`中添加新适配器类型。

### 自定义音频处理

```python
class CustomAudioProcessor:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
    
    def process_input(self, audio_data: bytes) -> bytes:
        # 音频预处理（降噪、增益等）
        return processed_audio
    
    def process_output(self, audio_data: bytes) -> bytes:
        # 音频后处理（均衡器、效果等）
        return processed_audio
```

## API参考

### 适配器接口

#### AudioAdapter基类
```python
class AudioAdapter(ABC):
    async def connect(self) -> bool
    async def disconnect(self) -> None
    async def send_audio(self, audio_data: bytes) -> bool
    async def receive_audio(self) -> AsyncGenerator[bytes, None]
    async def send_text(self, text: str) -> bool
```

#### AdapterFactory
```python
class AdapterFactory:
    @staticmethod
    def create_adapter(adapter_type: AdapterType, config: Dict[str, Any]) -> AudioAdapter
    
    @staticmethod
    def get_available_adapters() -> list[AdapterType]
    
    @staticmethod
    def get_adapter_requirements(adapter_type: AdapterType) -> Dict[str, Any]
```

### 配置选项

#### 本地适配器配置
```python
config = {
    "app_id": "your_app_id",
    "access_token": "your_access_token",
    "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
}
```

#### 浏览器适配器配置
```python
config = {
    "proxy_url": "ws://localhost:8765",
    "app_id": "your_app_id",
    "access_token": "your_access_token"
}
```

#### TouchDesigner适配器配置
```python
config = {
    "app_id": "your_app_id",
    "access_token": "your_access_token",
    "td_ip": "localhost",
    "td_port": 7000,
    "audio_input_port": 7001,
    "audio_output_port": 7002,
    "control_port": 7003
}
```

## 最佳实践

### 开发环境
1. 使用虚拟环境隔离依赖
2. 配置IDE的Python解释器
3. 启用类型检查和代码格式化

### 生产部署
1. 使用HTTPS/WSS协议
2. 配置负载均衡
3. 监控系统性能指标
4. 设置日志轮转

### 安全考虑
1. 保护API凭证安全
2. 验证输入数据格式
3. 限制并发连接数
4. 实施访问控制

## 社区和支持

### 问题反馈
- GitHub Issues: [项目地址]
- 邮件支持: [邮箱地址]

### 贡献指南
1. Fork项目仓库
2. 创建功能分支
3. 提交Pull Request
4. 通过代码审查

### 更新日志
- v1.0.0: 初始版本，支持本地和浏览器模式
- v1.1.0: 新增TouchDesigner适配器
- v1.2.0: 增强版浏览器界面

---

## 结语

本系统为豆包AI语音通话提供了完整、灵活、高质量的解决方案。无论您是开发者、创意工作者还是企业用户，都能找到适合的接入方式。

我们致力于持续改进和优化，欢迎您的反馈和建议！
# 统一音频架构设计文档

## 概述

本项目实现了基于适配器模式的统一音频架构，支持多种部署场景：
- **本地模式**：直接连接火山引擎API
- **浏览器模式**：通过代理服务器连接，解决浏览器WebSocket自定义header限制
- **TouchDesigner模式**：为TouchDesigner等外部工具预留接口（待实现）

## 架构设计

### 核心组件

1. **AudioAdapter (基类)** - 定义统一的音频处理接口
2. **LocalAudioAdapter** - 本地直连适配器
3. **BrowserAudioAdapter** - 浏览器代理适配器
4. **ProxyServer** - 代理服务器，解决浏览器限制
5. **AdapterFactory** - 适配器工厂，统一创建适配器
6. **UnifiedAudioApp** - 统一应用入口

### 目录结构

```
src/
├── adapters/
│   ├── __init__.py
│   ├── base.py              # 基类和配置类
│   ├── local_adapter.py     # 本地适配器
│   ├── browser_adapter.py   # 浏览器适配器
│   ├── factory.py           # 适配器工厂
│   └── proxy_server.py      # 代理服务器
├── unified_app.py           # 统一应用入口
static/
└── unified_browser_demo.html # 浏览器端示例
```

## 使用方法

### 1. 本地模式

直接运行，使用系统麦克风和扬声器：

```bash
python -m src.unified_app --adapter local
```

### 2. 浏览器模式

#### 步骤1：启动代理服务器

```bash
python -m src.adapters.proxy_server
```

#### 步骤2：启动统一应用（可选，用于本地音频处理）

```bash
python -m src.unified_app --adapter browser --proxy-url ws://localhost:8765
```

#### 步骤3：打开浏览器页面

访问 `static/unified_browser_demo.html`，配置：
- 代理服务器：`ws://localhost:8765`
- App ID：你的火山引擎App ID
- Access Token：你的火山引擎Access Token

## 核心特性

### 1. 解决浏览器限制

浏览器WebSocket不支持自定义headers，我们通过代理服务器解决：

```
浏览器 <---> 代理服务器 <---> 火山引擎API
       ^无自定义header  ^有自定义header
```

### 2. 统一接口

所有适配器都实现相同的接口：

```python
class AudioAdapter(ABC):
    async def connect(self) -> bool
    async def disconnect(self) -> None
    async def send_audio(self, audio_data: bytes) -> bool
    async def receive_audio(self) -> AsyncGenerator[bytes, None]
    async def send_text(self, text: str) -> bool
```

### 3. 灵活配置

支持不同场景的配置：

```python
# 本地配置
config = {
    "app_id": "your_app_id",
    "access_token": "your_token"
}

# 浏览器配置
config = {
    "proxy_url": "ws://localhost:8765",
    "app_id": "your_app_id", 
    "access_token": "your_token"
}
```

## 扩展新场景

### 1. 创建新适配器

继承 `AudioAdapter` 基类：

```python
class TouchDesignerAdapter(AudioAdapter):
    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.TOUCHDESIGNER
    
    async def connect(self) -> bool:
        # 实现TouchDesigner连接逻辑
        pass
    
    # 实现其他抽象方法...
```

### 2. 注册到工厂

在 `AdapterFactory` 中添加：

```python
elif adapter_type == AdapterType.TOUCHDESIGNER:
    return TouchDesignerAdapter(config)
```

### 3. 更新配置类

创建对应的配置类：

```python
class TouchDesignerConnectionConfig(ConnectionConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

## 消息协议

### 代理服务器协议

#### 客户端 -> 服务器

```json
// 认证
{"type": "auth", "app_id": "xxx", "access_token": "xxx"}

// 发送音频（十六进制编码）
{"type": "audio", "data": "deadbeef..."}

// 发送文本
{"type": "text", "content": "你好"}

// 心跳
{"type": "ping"}
```

#### 服务器 -> 客户端

```json
// 认证成功
{"type": "auth_success", "session_id": "xxx"}

// 音频响应（十六进制编码）
{"type": "audio", "data": "deadbeef..."}

// 事件响应
{"type": "event", "event": 350, "data": {...}}

// 错误
{"type": "error", "message": "错误信息"}

// 心跳回复
{"type": "pong"}
```

## 性能优化

1. **音频缓冲**：使用队列缓冲音频数据，避免阻塞
2. **异步处理**：所有I/O操作都是异步的
3. **资源清理**：自动清理WebSocket连接和音频资源
4. **错误恢复**：支持连接断开重连

## 安全考虑

1. **凭证保护**：火山引擎凭证仅在代理服务器端使用
2. **连接验证**：代理服务器验证客户端认证信息
3. **资源限制**：限制并发连接数和消息大小

## 故障排除

### 常见问题

1. **代理服务器连接失败**
   - 检查端口是否被占用
   - 确认防火墙设置

2. **音频无法播放**
   - 检查浏览器音频权限
   - 确认音频格式兼容性

3. **认证失败**
   - 验证App ID和Access Token
   - 检查火山引擎配额

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 未来扩展

1. **TouchDesigner适配器**：支持TouchDesigner实时音频处理
2. **移动端适配器**：支持React Native等移动端框架
3. **云端部署**：支持云端代理服务器部署
4. **音频增强**：集成降噪、回声消除等算法
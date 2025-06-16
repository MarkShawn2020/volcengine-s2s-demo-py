# 豆包AI语音通话系统

🤖 基于火山引擎API的高质量实时语音对话系统，支持浏览器、TouchDesigner等多种接入方式。

## ✨ 核心特性

- 🎙️ **实时语音对话**: 与豆包AI进行低延迟语音交互
- 🌐 **浏览器支持**: 现代化Web界面，无需安装客户端
- 🎨 **TouchDesigner集成**: 专业音频处理和创意项目支持
- 🔧 **模块化架构**: 基于适配器模式，易于扩展
- 📱 **跨平台兼容**: 支持Windows、macOS、Linux

## 🚀 快速开始

### 环境要求
- Python 3.11+
- 火山引擎豆包AI账号

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置API凭证
```bash
export VOLC_APP_ID="你的App ID"
export VOLC_ACCESS_KEY="你的Access Key"
export VOLC_APP_KEY="你的App Key"
```

### 开始使用

#### 🎤 本地语音对话（最简单）
```bash
python main.py --adapter local
```

#### 🌐 浏览器语音通话
```bash
# 1. 启动代理服务器
python -m src.adapters.proxy_server

# 2. 打开浏览器访问
open static/enhanced_browser_demo.html
```

#### 🎨 TouchDesigner集成
```bash
# 启动TouchDesigner适配器
python main.py --adapter touchdesigner

# 在TouchDesigner中加载示例代码
# 查看: docs/touchdesigner_example.py
```

## 📖 详细文档

- 📚 [完整使用指南](docs/COMPREHENSIVE_GUIDE.md) - 全面的功能介绍和使用说明
- 🚀 [快速开始](docs/QUICK_START.md) - 5分钟上手指南
- 🎨 [TouchDesigner集成](docs/TOUCHDESIGNER_INTEGRATION.md) - 创意项目集成详解
- 🏗️ [统一架构文档](docs/UNIFIED_ARCHITECTURE.md) - 技术架构说明

## 🎯 使用场景

| 场景 | 推荐方案 | 特点 |
|------|----------|------|
| 个人试用 | 本地模式 | 最简单，直接使用 |
| Web应用开发 | 浏览器模式 | 现代界面，跨平台 |
| 创意项目 | TouchDesigner | 专业音频处理 |
| 企业集成 | 自定义适配器 | 灵活扩展 |

## 🔧 支持的适配器

### 本地适配器 (Local)
- ✅ 直接连接火山引擎API
- ✅ 使用本地音频设备
- ✅ 最低延迟

### 浏览器适配器 (Browser)
- ✅ 通过代理服务器连接
- ✅ 现代Web界面
- ✅ 移动设备支持

### TouchDesigner适配器 (TouchDesigner)
- ✅ UDP/TCP协议通信
- ✅ 实时音频处理
- ✅ 创意项目集成

## 📁 项目结构

```
src/
├── adapters/           # 适配器模块
│   ├── local_adapter.py      # 本地适配器
│   ├── browser_adapter.py    # 浏览器适配器
│   ├── touchdesigner_adapter.py  # TouchDesigner适配器
│   └── factory.py            # 适配器工厂
├── volcengine/         # 火山引擎API客户端
├── audio/              # 音频处理工具
└── unified_app.py      # 统一应用入口

static/
├── enhanced_browser_demo.html  # 增强版浏览器界面
└── unified_browser_demo.html   # 基础浏览器界面

docs/
├── COMPREHENSIVE_GUIDE.md      # 完整指南
├── TOUCHDESIGNER_INTEGRATION.md  # TouchDesigner集成
└── touchdesigner_example.py    # TouchDesigner示例代码
```

## 🌟 界面预览

### 增强版浏览器界面
- 🎨 现代化设计风格
- 🎤 实时音量显示
- 💬 对话记录功能
- 📊 系统状态监控

### TouchDesigner集成
- 🔊 实时音频可视化
- 🎛️ 专业音频控制
- 🎪 创意效果支持

## ⚡ 性能优化

- **音频缓冲**: 智能缓冲管理，减少延迟
- **网络优化**: 异步处理，高并发支持
- **资源管理**: 自动资源清理和错误恢复

## 🛠️ 高级配置

### 自定义音频参数
```bash
python main.py --adapter local --use-pcm
```

### TouchDesigner网络配置
```bash
python main.py --adapter touchdesigner --td-ip 192.168.1.100 --td-port 7000
```

### 代理服务器端口
```bash
python -m src.adapters.proxy_server --port 9000
```

## 🤝 开发指南

### 创建自定义适配器
1. 继承 `AudioAdapter` 基类
2. 实现必要的抽象方法
3. 在 `AdapterFactory` 中注册

### 扩展音频处理
- 支持自定义音频滤镜
- 集成第三方音频库
- 实现音频效果插件

## 📞 技术支持

- 🐛 [问题反馈](https://github.com/your-repo/issues)
- 💬 [讨论区](https://github.com/your-repo/discussions)
- 📧 技术支持邮箱

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

感谢火山引擎提供的优质AI服务，感谢TouchDesigner社区的创意灵感。

---

**让语音交互更简单，让创意无限可能！** 🚀
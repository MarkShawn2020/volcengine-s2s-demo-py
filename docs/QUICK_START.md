# 快速开始指南

## 🚀 5分钟上手豆包AI语音通话

### 第一步：环境准备

确保您已安装Python 3.11+：
```bash
python --version
```

### 第二步：安装依赖

```bash
# 克隆项目（如果还没有）
cd volcengine-s2s-demo/py

# 安装依赖
pip install -r requirements.txt
```

### 第三步：配置API凭证

在火山引擎控制台获取凭证后，设置环境变量：
```bash
export VOLC_APP_ID="你的App ID"
export VOLC_ACCESS_KEY="你的Access Key" 
export VOLC_APP_KEY="你的App Key"
```

### 第四步：开始使用

#### 🎤 本地语音对话（最简单）
```bash
python main.py --adapter local
```

#### 🌐 浏览器语音通话

1. 启动代理服务器：
```bash
python -m src.adapters.proxy_server
```

2. 打开浏览器，访问：`static/enhanced_browser_demo.html`

3. 填入配置信息并点击连接

#### 🎨 TouchDesigner集成

1. 启动TouchDesigner适配器：
```bash
python main.py --adapter touchdesigner
```

2. 在TouchDesigner中加载：`docs/touchdesigner_example.py`

## 🎯 使用场景选择

| 场景 | 推荐方案 | 特点 |
|------|----------|------|
| 个人试用 | 本地模式 | 最简单，直接使用 |
| Web应用 | 浏览器模式 | 现代界面，跨平台 |
| 创意项目 | TouchDesigner | 专业音频处理 |

## 🔧 常用命令

```bash
# 查看所有参数
python main.py --help

# 指定TouchDesigner IP
python main.py --adapter touchdesigner --td-ip 192.168.1.100

# 自定义代理端口
python -m src.adapters.proxy_server --port 9000
```

## ❗ 常见问题

**Q: 无法连接？**
A: 检查API凭证和网络连接

**Q: 没有声音？**
A: 确认音频设备权限和硬件连接

**Q: TouchDesigner连接失败？**
A: 检查IP地址和端口配置

更多详细信息请查看 [完整使用指南](COMPREHENSIVE_GUIDE.md)。
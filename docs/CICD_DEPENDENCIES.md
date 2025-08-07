# CI/CD 依赖问题解决指南

## 🔴 问题：PyAudio 编译失败

### 错误信息
```
fatal error: portaudio.h: No such file or directory
```

### 原因
PyAudio 是一个 Python 音频库，它依赖于 C 库 PortAudio。在安装 PyAudio 时，需要编译 C 扩展，这需要：
1. PortAudio 开发头文件
2. C 编译器
3. 正确的编译环境

## ✅ 解决方案

### GitHub Actions 工作流（已实施）

#### Linux (Ubuntu)
```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev python3-pyaudio
```

#### macOS
```yaml
- name: Install system dependencies
  run: |
    brew install portaudio
```

#### Windows
```yaml
- name: Install system dependencies
  run: |
    # Windows 通常有预编译的 wheels
    pip install pyaudio
```

## 🛠️ 本地开发环境配置

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

### macOS
```bash
brew install portaudio

# 如果还有问题，设置环境变量
export CFLAGS="-I$(brew --prefix)/include"
export LDFLAGS="-L$(brew --prefix)/lib"
```

### Windows
1. **方法一：使用预编译 wheel**
   - 访问 https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
   - 下载对应 Python 版本的 wheel
   - 安装：`pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl`

2. **方法二：安装 Visual C++ Build Tools**
   - 下载 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
   - 安装 "Desktop development with C++"

### 使用 Docker
```dockerfile
FROM python:3.11

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install
```

## 🧪 测试安装

### 快速测试脚本
```bash
./scripts/test_pyaudio_install.sh
```

### 手动测试
```python
# 测试 PyAudio 是否正确安装
import pyaudio

p = pyaudio.PyAudio()
print(f"PyAudio 版本: {pyaudio.__version__}")
print(f"设备数量: {p.get_device_count()}")
p.terminate()
```

## 📋 CI/CD 检查清单

### ✅ 已完成
- [x] release.yml - 添加 Linux 系统依赖
- [x] build-macos.yml - 添加 macOS 系统依赖  
- [x] build-windows.yml - 添加 Windows 兼容处理
- [x] 创建本地测试脚本
- [x] 文档化解决方案

### 🔍 验证步骤
1. 提交代码
2. 观察 GitHub Actions 运行
3. 检查 "Install system dependencies" 步骤
4. 确认 "Install dependencies" 步骤成功

## 🚀 其他优化建议

### 1. 使用 Docker 容器
为了避免系统依赖问题，可以考虑使用预配置的 Docker 容器：
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: python:3.11
      options: --user root
```

### 2. 缓存系统依赖
```yaml
- name: Cache system dependencies
  uses: actions/cache@v4
  with:
    path: /usr/local
    key: ${{ runner.os }}-system-deps-${{ hashFiles('**/requirements.txt') }}
```

### 3. 使用 Matrix 策略
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ['3.11', '3.12']
```

## 📚 相关资源

- [PyAudio 官方文档](https://people.csail.mit.edu/hubert/pyaudio/)
- [PortAudio 官网](http://www.portaudio.com/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Poetry 依赖管理](https://python-poetry.org/docs/dependency-specification/)

## ⚠️ 常见错误

### 1. `ERROR: Could not build wheels for pyaudio`
**解决**: 安装系统依赖

### 2. `ModuleNotFoundError: No module named 'pyaudio'`
**解决**: 确保在正确的虚拟环境中

### 3. `OSError: [Errno -9996] Invalid input device`
**解决**: 检查音频设备权限

## 💡 提示

- 始终在 CI/CD 中明确安装系统依赖
- 使用缓存加速构建
- 在本地测试 CI/CD 配置
- 保持依赖版本一致性
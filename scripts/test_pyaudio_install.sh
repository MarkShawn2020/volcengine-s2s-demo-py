#!/bin/bash

echo "🔍 测试 PyAudio 安装"
echo "======================"
echo ""

# 检测操作系统
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "📍 检测到: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "📍 检测到: macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="windows"
    echo "📍 检测到: Windows"
fi

echo ""
echo "步骤 1: 检查系统依赖"
echo "----------------------"

case $OS in
    linux)
        echo "检查 portaudio 是否已安装..."
        if dpkg -l | grep -q portaudio19-dev; then
            echo "✅ portaudio19-dev 已安装"
        else
            echo "❌ portaudio19-dev 未安装"
            echo ""
            echo "请运行以下命令安装："
            echo "  sudo apt-get update"
            echo "  sudo apt-get install -y portaudio19-dev python3-pyaudio"
            echo ""
            read -p "是否现在安装？(y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sudo apt-get update
                sudo apt-get install -y portaudio19-dev python3-pyaudio
            fi
        fi
        ;;
    macos)
        echo "检查 portaudio 是否已安装..."
        if brew list | grep -q portaudio; then
            echo "✅ portaudio 已安装"
        else
            echo "❌ portaudio 未安装"
            echo ""
            echo "请运行以下命令安装："
            echo "  brew install portaudio"
            echo ""
            read -p "是否现在安装？(y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                brew install portaudio
            fi
        fi
        ;;
    windows)
        echo "Windows 通常使用预编译的 wheel 包"
        echo "如果安装失败，可以尝试："
        echo "  1. pip install pyaudio"
        echo "  2. 从 https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio 下载对应版本的 wheel"
        ;;
    *)
        echo "⚠️  未知操作系统"
        ;;
esac

echo ""
echo "步骤 2: 测试 Poetry 安装"
echo "------------------------"

# 创建临时虚拟环境
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
echo "在临时目录测试: $TEMP_DIR"

# 复制 pyproject.toml
cp "$OLDPWD/pyproject.toml" .
cp "$OLDPWD/poetry.lock" . 2>/dev/null || true

echo ""
echo "尝试安装 pyaudio..."
if poetry install --no-interaction --no-ansi 2>&1 | tee install.log; then
    echo ""
    echo "✅ PyAudio 安装成功！"
    
    # 测试导入
    echo ""
    echo "测试导入 pyaudio..."
    if poetry run python -c "import pyaudio; print('✅ PyAudio 导入成功！版本:', pyaudio.__version__)"; then
        echo ""
        echo "🎉 所有测试通过！"
    else
        echo ""
        echo "❌ PyAudio 导入失败"
    fi
else
    echo ""
    echo "❌ PyAudio 安装失败"
    echo ""
    echo "错误日志："
    grep -A 5 "error:" install.log
    echo ""
    echo "可能的解决方案："
    case $OS in
        linux)
            echo "1. 确保安装了所有系统依赖："
            echo "   sudo apt-get install -y portaudio19-dev python3-pyaudio"
            echo "2. 尝试使用 pip 直接安装："
            echo "   pip install pyaudio"
            ;;
        macos)
            echo "1. 确保安装了 portaudio："
            echo "   brew install portaudio"
            echo "2. 设置环境变量："
            echo "   export CFLAGS=\"-I$(brew --prefix)/include\""
            echo "   export LDFLAGS=\"-L$(brew --prefix)/lib\""
            ;;
        windows)
            echo "1. 下载预编译的 wheel："
            echo "   https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio"
            echo "2. 安装 Visual C++ Build Tools"
            ;;
    esac
fi

# 清理
cd "$OLDPWD"
rm -rf "$TEMP_DIR"

echo ""
echo "测试完成！"
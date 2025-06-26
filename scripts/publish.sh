#!/bin/bash
set -e

echo "🚀 开始发布 volcengine-s2s-framework 到 PyPI"

# 检查是否安装了 poetry
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry 未安装，请先安装 Poetry"
    exit 1
fi

# 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    echo "⚠️  检测到未提交的更改，建议先提交代码"
    read -p "是否继续发布？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 构建包
echo "📦 构建包..."
poetry build

# 安装 twine（如果未安装）
if ! poetry run python -c "import twine" 2>/dev/null; then
    echo "📦 安装 twine..."
    poetry add --group dev twine
fi

# 检查包内容
echo "🔍 检查包内容..."
poetry run twine check dist/*

# 发布到 TestPyPI（可选，用于测试）
read -p "是否先发布到 TestPyPI 进行测试？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📤 发布到 TestPyPI..."
    poetry publish -r testpypi
    echo "✅ 已发布到 TestPyPI"
    echo "🔗 可以通过以下命令安装测试版本："
    echo "pip install --index-url https://test.pypi.org/simple/ volcengine-s2s-framework"
    
    read -p "测试完成后，是否继续发布到正式 PyPI？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# 发布到正式 PyPI
echo "📤 发布到正式 PyPI..."
poetry publish

echo "✅ 发布完成！"
echo "🔗 可以通过以下命令安装："
echo "pip install volcengine-s2s-framework"
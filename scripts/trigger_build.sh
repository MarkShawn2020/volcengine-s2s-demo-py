#!/bin/bash

echo "🚀 手动触发构建工作流"
echo "====================="
echo ""

# 获取最新的 tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

if [ -z "$LATEST_TAG" ]; then
    echo "❌ 没有找到任何 tag"
    echo ""
    echo "请先创建一个 tag："
    echo "  git tag v1.0.0"
    echo "  git push origin v1.0.0"
    exit 1
fi

echo "📍 最新的 tag: $LATEST_TAG"
echo ""

echo "选择操作："
echo "1. 为现有 tag ($LATEST_TAG) 触发构建"
echo "2. 创建新的 tag 并触发构建"
echo "3. 手动触发构建（不创建 tag）"
echo ""

read -p "请选择 (1/2/3): " choice

case $choice in
    1)
        echo ""
        echo "🔄 重新推送 tag 以触发构建..."
        git push origin :refs/tags/$LATEST_TAG 2>/dev/null
        git push origin $LATEST_TAG
        echo "✅ 已触发构建工作流"
        echo ""
        echo "📊 查看构建进度："
        echo "https://github.com/MarkShawn2020/volcengine-s2s-demo-py/actions"
        ;;
    2)
        echo ""
        read -p "输入新版本号 (如 1.0.1): " VERSION
        if [ -z "$VERSION" ]; then
            echo "❌ 版本号不能为空"
            exit 1
        fi
        
        TAG="v$VERSION"
        echo ""
        echo "创建 tag: $TAG"
        git tag -a $TAG -m "Release $TAG"
        git push origin $TAG
        echo "✅ 已创建并推送 tag，构建工作流已触发"
        echo ""
        echo "📊 查看构建进度："
        echo "https://github.com/MarkShawn2020/volcengine-s2s-demo-py/actions"
        ;;
    3)
        echo ""
        echo "📝 手动触发需要通过 GitHub Actions 页面："
        echo ""
        echo "1. 访问: https://github.com/MarkShawn2020/volcengine-s2s-demo-py/actions"
        echo "2. 选择 'Build and Release' 工作流"
        echo "3. 点击 'Run workflow'"
        echo "4. 输入版本号（可选）"
        echo "5. 点击 'Run workflow' 按钮"
        ;;
    *)
        echo "❌ 无效的选择"
        exit 1
        ;;
esac

echo ""
echo "💡 提示："
echo "  • 构建通常需要 5-10 分钟"
echo "  • Windows 和 macOS 会并行构建"
echo "  • 构建完成后会自动创建 Release"
echo "  • 在 Releases 页面下载构建产物"
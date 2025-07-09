#!/bin/bash
# macOS 打包脚本

set -e

echo "开始构建 macOS 应用..."

# 清理之前的构建
rm -rf build dist

# 安装依赖
echo "安装依赖..."
poetry install --with dev

# 使用 PyInstaller 打包
echo "运行 PyInstaller..."
poetry run pyinstaller build.spec --clean --noconfirm

# 检查构建结果
if [ -d "dist/VolcengineVoiceChat.app" ]; then
    echo "✅ macOS 应用构建成功！"
    echo "应用位置: dist/VolcengineVoiceChat.app"
    
    # 显示应用信息
    echo "应用大小: $(du -sh dist/VolcengineVoiceChat.app | cut -f1)"
    
    # 可选：创建 DMG 镜像
    if command -v create-dmg &> /dev/null; then
        echo "创建 DMG 镜像..."
        create-dmg \
            --volname "Volcengine Voice Chat" \
            --volicon "dist/VolcengineVoiceChat.app/Contents/Resources/icon.icns" \
            --window-pos 200 120 \
            --window-size 600 300 \
            --icon-size 100 \
            --icon "VolcengineVoiceChat.app" 175 120 \
            --hide-extension "VolcengineVoiceChat.app" \
            --app-drop-link 425 120 \
            "dist/VolcengineVoiceChat.dmg" \
            "dist/"
        echo "✅ DMG 镜像创建成功: dist/VolcengineVoiceChat.dmg"
    fi
else
    echo "❌ 构建失败！"
    exit 1
fi

echo "构建完成！"
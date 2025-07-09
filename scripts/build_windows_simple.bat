@echo off
REM Windows 简单打包脚本

echo 开始构建Windows应用...

REM 清理之前的构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 安装依赖
echo 安装依赖...
poetry install --with dev

REM 使用PyInstaller打包
echo 运行PyInstaller...
poetry run pyinstaller ^
    --clean ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name VolcengineVoiceChat ^
    --add-data "src;src" ^
    --add-data "static;static" ^
    --add-data ".env;." ^
    --hidden-import "src.adapters.local_adapter" ^
    --hidden-import "src.volcengine.client" ^
    --hidden-import "pyaudio" ^
    --hidden-import "numpy" ^
    --hidden-import "websockets" ^
    --hidden-import "dotenv" ^
    gui_main.py

REM 检查构建结果
if exist "dist\VolcengineVoiceChat\VolcengineVoiceChat.exe" (
    echo ✅ Windows应用构建成功！
    echo 应用位置: dist\VolcengineVoiceChat\
    
    REM 创建ZIP包
    echo 创建ZIP包...
    powershell -Command "Compress-Archive -Path 'dist\VolcengineVoiceChat\*' -DestinationPath 'dist\VolcengineVoiceChat-Windows.zip' -Force"
    echo ✅ ZIP包创建成功: dist\VolcengineVoiceChat-Windows.zip
    
) else (
    echo ❌ 构建失败！
    exit /b 1
)

echo 构建完成！
pause
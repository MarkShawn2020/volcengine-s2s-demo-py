#!/usr/bin/env python3
"""
Windows 打包脚本
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_windows_exe():
    """构建Windows可执行文件"""
    print("开始构建Windows应用...")
    
    # 清理之前的构建
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # 检查是否安装了pyinstaller
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("安装pyinstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 使用PyInstaller打包
    print("运行PyInstaller...")
    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--onedir",  # 创建目录模式，更适合复杂依赖
        "--windowed",  # 不显示控制台窗口
        "--name", "VolcengineVoiceChat",
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", ".",
        # 添加数据文件
        "--add-data", "src;src",
        "--add-data", "static;static",
        "--add-data", ".env;.",
        # 隐藏导入
        "--hidden-import", "src.adapters.local_adapter",
        "--hidden-import", "src.adapters.browser_adapter",
        "--hidden-import", "src.adapters.touchdesigner_adapter",
        "--hidden-import", "src.adapters.text_input_adapter",
        "--hidden-import", "src.volcengine.client",
        "--hidden-import", "src.volcengine.protocol",
        "--hidden-import", "src.audio.threads",
        "--hidden-import", "pyaudio",
        "--hidden-import", "numpy",
        "--hidden-import", "scipy",
        "--hidden-import", "soundfile",
        "--hidden-import", "pydub",
        "--hidden-import", "websockets",
        "--hidden-import", "pydantic",
        "--hidden-import", "dotenv",
        # 排除不需要的模块
        "--exclude-module", "matplotlib",
        "--exclude-module", "PIL",
        "--exclude-module", "tkinter.test",
        "--exclude-module", "test",
        "--exclude-module", "unittest",
        "gui_main.py"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("PyInstaller执行成功")
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller执行失败: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    
    # 检查构建结果
    exe_path = Path("dist/VolcengineVoiceChat/VolcengineVoiceChat.exe")
    if exe_path.exists():
        print(f"✅ Windows应用构建成功！")
        print(f"应用位置: {exe_path}")
        
        # 显示应用信息
        app_size = sum(f.stat().st_size for f in Path("dist/VolcengineVoiceChat").rglob('*') if f.is_file())
        print(f"应用大小: {app_size / 1024 / 1024:.1f} MB")
        
        # 创建ZIP包
        print("创建ZIP包...")
        shutil.make_archive("dist/VolcengineVoiceChat-Windows", 'zip', "dist/VolcengineVoiceChat")
        print("✅ ZIP包创建成功: dist/VolcengineVoiceChat-Windows.zip")
        
        return True
    else:
        print("❌ 构建失败！")
        return False

def create_onefile_exe():
    """创建单文件exe"""
    print("创建单文件exe...")
    
    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--onefile",  # 单文件模式
        "--windowed",  # 不显示控制台窗口
        "--name", "VolcengineVoiceChat-Portable",
        "--distpath", "dist",
        "--workpath", "build",
        # 添加数据文件
        "--add-data", "src;src",
        "--add-data", "static;static",
        "--add-data", ".env;.",
        # 隐藏导入
        "--hidden-import", "src.adapters.local_adapter",
        "--hidden-import", "src.volcengine.client",
        "--hidden-import", "pyaudio",
        "--hidden-import", "numpy",
        "--hidden-import", "websockets",
        "--hidden-import", "dotenv",
        "gui_main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 单文件exe创建成功: dist/VolcengineVoiceChat-Portable.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 单文件exe创建失败: {e}")
        return False

def main():
    """主函数"""
    print("Windows打包工具")
    print("=" * 40)
    
    # 构建目录版本
    success = build_windows_exe()
    
    if success:
        # 询问是否创建单文件版本
        try:
            response = input("\n是否创建单文件版本？(启动较慢但方便分发) [y/N]: ")
            if response.lower() in ['y', 'yes']:
                create_onefile_exe()
        except KeyboardInterrupt:
            print("\n取消操作")
    
    print("\n构建完成！")

if __name__ == "__main__":
    main()
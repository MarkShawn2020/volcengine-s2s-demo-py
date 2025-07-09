#!/usr/bin/env python3
"""
Windows 打包测试脚本
"""
import os
import sys
import subprocess
from pathlib import Path

def test_dependencies():
    """测试依赖是否完整"""
    print("测试依赖导入...")
    
    required_modules = [
        'tkinter',
        'pyaudio', 
        'numpy',
        'websockets',
        'pydantic',
        'dotenv',
        'queue',
        'threading',
        'asyncio',
        'json',
        'logging'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module}")
            missing_modules.append(module)
    
    if missing_modules:
        print(f"\n缺少模块: {', '.join(missing_modules)}")
        return False
    else:
        print("\n所有依赖模块都可用")
        return True

def test_project_structure():
    """测试项目结构"""
    print("测试项目结构...")
    
    required_files = [
        'gui_main.py',
        'src/adapters/local_adapter.py',
        'src/volcengine/client.py',
        'src/audio/threads.py',
        '.env',
        'pyproject.toml'
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n缺少文件: {', '.join(missing_files)}")
        return False
    else:
        print("\n所有必需文件都存在")
        return True

def test_pyinstaller():
    """测试PyInstaller是否可用"""
    print("测试PyInstaller...")
    
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"✅ PyInstaller版本: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller不可用")
        return False

def test_gui_import():
    """测试GUI模块导入"""
    print("测试GUI模块导入...")
    
    try:
        # 测试基本GUI导入
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        import dotenv
        dotenv.load_dotenv()
        print("✅ dotenv")
        
        from src.adapters.type import AdapterType
        print("✅ AdapterType")
        
        from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
        print("✅ 配置")
        
        from src.unified_app import UnifiedAudioApp
        print("✅ UnifiedAudioApp")
        
        print("✅ 所有GUI模块导入成功")
        return True
        
    except Exception as e:
        print(f"❌ GUI模块导入失败: {e}")
        return False

def generate_build_command():
    """生成打包命令"""
    print("\n生成推荐的打包命令:")
    
    command = [
        "pyinstaller",
        "--clean",
        "--noconfirm", 
        "--onedir",
        "--windowed",
        "--name", "VolcengineVoiceChat",
        "--add-data", "src;src",
        "--add-data", "static;static", 
        "--add-data", ".env;.",
        "--hidden-import", "src.adapters.local_adapter",
        "--hidden-import", "src.volcengine.client",
        "--hidden-import", "pyaudio",
        "--hidden-import", "numpy",
        "--hidden-import", "websockets",
        "--hidden-import", "dotenv",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PIL",
        "gui_main.py"
    ]
    
    print(" ".join(command))
    return command

def main():
    """主函数"""
    print("Windows 打包测试")
    print("=" * 50)
    
    tests = [
        test_dependencies,
        test_project_structure,
        test_pyinstaller,
        test_gui_import
    ]
    
    results = []
    for test in tests:
        print("\n" + "-" * 30)
        result = test()
        results.append(result)
        print()
    
    print("=" * 50)
    print("测试结果汇总:")
    
    test_names = [
        "依赖模块",
        "项目结构", 
        "PyInstaller",
        "GUI模块"
    ]
    
    all_passed = True
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过！可以开始打包了")
        generate_build_command()
    else:
        print("\n⚠️  请先解决失败的测试项")

if __name__ == "__main__":
    main()
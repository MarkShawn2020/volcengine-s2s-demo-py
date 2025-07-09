# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

# 获取项目根目录
project_root = Path(__file__).parent

# 数据文件列表
datas = [
    ('src', 'src'),
    ('static', 'static'),
    ('.env', '.'),
]

# 隐藏导入
hiddenimports = [
    'src.adapters.local_adapter',
    'src.adapters.browser_adapter',
    'src.adapters.touchdesigner_adapter',
    'src.adapters.touchdesigner_webrtc_adapter',
    'src.adapters.touchdesigner_webrtc_proper_adapter',
    'src.adapters.text_input_adapter',
    'src.volcengine.client',
    'src.volcengine.protocol',
    'src.audio.threads',
    'src.audio.utils.calculate_volume',
    'src.audio.utils.has_speech_activity',
    'src.audio.utils.select_audio_device',
    'src.audio.utils.voice_activity_detector',
    'pyaudio',
    'av',
    'aiortc',
    'pygame',
    'keyboard',
    'numpy',
    'scipy',
    'soundfile',
    'pydub',
    'ffmpeg',
    'dotenv',
    'websockets',
    'pydantic',
    'typing_extensions',
    'socks',
]

# 排除的模块
excludes = [
    'matplotlib',
    'PIL',
    'tkinter.test',
    'test',
    'unittest',
    'pydoc',
    'doctest',
]

# 二进制文件
binaries = []

# 如果是 macOS，添加一些特定的二进制文件
if sys.platform == 'darwin':
    binaries.extend([
        # 可能需要的 macOS 特定库
    ])

# 如果是 Windows，添加一些特定的二进制文件
if sys.platform == 'win32':
    binaries.extend([
        # 可能需要的 Windows 特定库
    ])

a = Analysis(
    ['gui_main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VolcengineVoiceChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

# 创建分发包
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VolcengineVoiceChat',
)

# macOS 应用包
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='VolcengineVoiceChat.app',
        icon=None,  # 可以添加 .icns 图标文件
        bundle_identifier='com.markshawn2020.volcengine-voice-chat',
        info_plist={
            'CFBundleDisplayName': 'Volcengine Voice Chat',
            'CFBundleVersion': '0.1.0',
            'CFBundleShortVersionString': '0.1.0',
            'NSMicrophoneUsageDescription': 'This app needs microphone access for voice input.',
            'NSCameraUsageDescription': 'This app may need camera access for video features.',
        },
    )
# -*- mode: python ; coding: utf-8 -*-
# Windows 专用打包配置

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

# 隐藏导入 - Windows专用优化
hiddenimports = [
    'src.adapters.local_adapter',
    'src.adapters.browser_adapter',
    'src.adapters.text_input_adapter',
    'src.volcengine.client',
    'src.volcengine.protocol',
    'src.audio.threads',
    'src.audio.utils.calculate_volume',
    'src.audio.utils.has_speech_activity',
    'src.audio.utils.select_audio_device',
    'src.audio.utils.voice_activity_detector',
    'pyaudio',
    'numpy',
    'scipy',
    'soundfile',
    'pydub',
    'websockets',
    'pydantic',
    'typing_extensions',
    'dotenv',
    'tkinter',
    'tkinter.ttk',
    'queue',
    'threading',
    'asyncio',
    'json',
    'logging',
    'uuid',
    'io',
    'wave',
    'struct',
    'time',
    'datetime',
    'base64',
    'hashlib',
    'hmac',
    'urllib.parse',
    'urllib.request',
    'ssl',
    'socket',
    'select',
    'errno',
    'os',
    'sys',
    'pathlib',
    'configparser',
    'platform',
]

# 排除的模块 - Windows优化
excludes = [
    'matplotlib',
    'PIL',
    'tkinter.test',
    'test',
    'unittest',
    'pydoc',
    'doctest',
    'turtle',
    'curses',
    'readline',
    'rlcompleter',
    'pdb',
    'profile',
    'pstats',
    'cProfile',
    'trace',
    'timeit',
    'dis',
    'pickletools',
    'py_compile',
    'compileall',
    'keyword',
    'token',
    'tokenize',
    'ast',
    'parser',
    'symbol',
    'tabnanny',
    'lib2to3',
    'distutils',
    'setuptools',
    'pkg_resources',
    'pip',
    'wheel',
    'easy_install',
]

# Windows特定的二进制文件
binaries = []
if sys.platform == 'win32':
    # 可能需要的Windows特定库
    binaries.extend([
        # 例如: ('path/to/dll', '.'),
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

# 创建Windows可执行文件
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加 .ico 图标文件
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

# Windows特定优化
if sys.platform == 'win32':
    # 可以添加Windows特定的配置
    pass
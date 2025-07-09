# GUI 打包说明

## 概述

本项目支持将命令行应用打包为 GUI 应用，支持 macOS 和 Windows 平台。

## 依赖安装

首先安装打包依赖：

```bash
poetry install --with dev
```

## GUI 运行

在开发模式下运行 GUI：

```bash
poetry run python gui_main.py
```

## 打包

### macOS 打包

```bash
./scripts/build_mac.sh
```

生成的应用位于 `dist/VolcengineVoiceChat.app`

### Windows 打包

#### 方法1：使用Python脚本（推荐）

```bash
python build_windows.py
```

#### 方法2：使用批处理脚本

```cmd
scripts\build_windows_simple.bat
```

#### 方法3：使用PyInstaller命令行

```bash
poetry run pyinstaller build_windows.spec
```

#### 方法4：使用PowerShell脚本

```powershell
.\scripts\build_windows.ps1
```

**Windows打包结果：**
- 目录版本：`dist\VolcengineVoiceChat\` 
- 单文件版本：`dist\VolcengineVoiceChat-Portable.exe`
- ZIP包：`dist\VolcengineVoiceChat-Windows.zip`

## 文件结构

```
gui_main.py                 # GUI 主程序入口
gui/
├── __init__.py
└── main_window.py          # 主窗口实现
build.spec                  # PyInstaller 配置文件
scripts/
├── build_mac.sh           # macOS 打包脚本
└── build_windows.ps1      # Windows 打包脚本
```

## GUI 功能

- 适配器选择（下拉菜单）
- 动态配置界面（根据适配器类型显示不同选项）
- 启动/停止按钮
- 实时日志显示
- 状态指示器

## 注意事项

1. 确保在 `.env` 文件中配置了正确的 API 密钥
2. 首次运行可能需要授予麦克风权限
3. 打包后的应用包含所有必需的依赖，可以独立运行
4. Windows 版本可能需要安装 Visual C++ 运行时库

## Windows 打包优化

### 减少文件大小
- 使用 `--exclude-module` 排除不必要的模块
- 使用 `--upx` 压缩可执行文件（需要安装UPX）
- 选择单文件模式可以减少文件数量但会增加启动时间

### 解决常见问题
1. **音频设备权限**：Windows可能需要手动授予麦克风权限
2. **防火墙警告**：首次运行可能触发Windows防火墙警告
3. **杀毒软件**：某些杀毒软件可能误报，需要添加白名单
4. **缺少运行时库**：安装 Microsoft Visual C++ Redistributable

### 分发建议
- 目录版本：适合本地使用，启动快
- 单文件版本：适合分发，便携但启动慢
- ZIP包：适合下载分发

## 故障排除

如果遇到打包问题：

1. 检查 `build.spec` 文件中的隐藏导入列表
2. 确保所有必需的数据文件都在 `datas` 列表中
3. 查看打包日志中的错误信息
4. 可以尝试使用 `--debug` 参数进行调试打包
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

在 Windows 系统上运行：

```powershell
.\scripts\build_windows.ps1
```

生成的应用位于 `dist\VolcengineVoiceChat\`

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

## 故障排除

如果遇到打包问题：

1. 检查 `build.spec` 文件中的隐藏导入列表
2. 确保所有必需的数据文件都在 `datas` 列表中
3. 查看打包日志中的错误信息
4. 可以尝试使用 `--debug` 参数进行调试打包
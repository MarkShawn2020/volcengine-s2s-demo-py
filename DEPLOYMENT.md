# 部署指南

## 跨平台打包说明

### 重要提醒
**不能在Mac上直接打包Windows exe文件！** 需要在对应平台上进行打包。

## 打包方式

### 方式1：本地打包

#### Windows打包
1. 在Windows机器上克隆项目
2. 安装Python 3.11+和Poetry
3. 运行打包：
   ```cmd
   python build_windows.py
   ```

#### macOS打包
1. 在Mac上运行：
   ```bash
   ./scripts/build_mac.sh
   ```

### 方式2：虚拟机打包

#### 在Mac上使用Windows虚拟机
1. 安装VMware Fusion或Parallels Desktop
2. 创建Windows虚拟机
3. 在虚拟机中进行Windows打包
4. 将生成的exe文件复制到Mac

#### 在Windows上使用Mac虚拟机
1. 安装VMware Workstation
2. 创建macOS虚拟机（需要合规使用）
3. 在虚拟机中进行macOS打包

### 方式3：CI/CD自动打包（推荐）

#### GitHub Actions
1. 推送代码到GitHub
2. Actions会自动在Windows和macOS环境中打包
3. 从Artifacts下载打包结果

#### 使用步骤：
1. 将项目推送到GitHub
2. GitHub Actions会自动触发构建
3. 在Actions页面下载构建产物：
   - `windows-build`：包含Windows exe和zip
   - `macos-build`：包含macOS app和dmg

## 分发建议

### Windows分发
- **ZIP包**：`VolcengineVoiceChat-Windows.zip`
  - 解压即用，适合大多数用户
  - 包含所有依赖文件
  
- **单文件exe**：`VolcengineVoiceChat-Portable.exe`
  - 便携版本，适合U盘分发
  - 首次启动较慢

### macOS分发
- **App包**：`VolcengineVoiceChat.app`
  - 拖拽到Applications文件夹
  - 需要处理签名和公证

- **DMG镜像**：`VolcengineVoiceChat.dmg`
  - 标准macOS分发格式
  - 用户体验更好

## 环境要求

### Windows
- Windows 10/11
- Microsoft Visual C++ Redistributable
- 麦克风权限

### macOS
- macOS 10.15+
- 麦克风权限（系统偏好设置）

## 常见问题

### Windows
1. **杀毒软件误报**
   - 添加到杀毒软件白名单
   - 使用代码签名证书

2. **缺少运行时库**
   - 安装Microsoft Visual C++ Redistributable
   - 包含在安装包中

3. **防火墙警告**
   - 允许网络访问
   - 仅在需要联网时出现

### macOS
1. **"无法打开，因为无法验证开发者"**
   - 系统偏好设置 → 安全性与隐私 → 仍要打开
   - 或使用开发者签名

2. **麦克风权限**
   - 系统偏好设置 → 安全性与隐私 → 隐私 → 麦克风

## 自动化部署

### 设置GitHub Actions
1. 创建`.github/workflows/build.yml`
2. 配置构建流程
3. 每次推送代码自动打包

### 版本发布
1. 创建Git Tag：`git tag v1.0.0`
2. 推送Tag：`git push origin v1.0.0`
3. 在GitHub创建Release
4. 自动附加构建产物

## 测试建议

### 打包前测试
```bash
# Windows
python test_windows_build.py

# macOS
python test_mac_build.py  # 需要创建
```

### 打包后测试
1. 在干净的系统上测试
2. 检查所有功能是否正常
3. 验证音频设备检测
4. 测试网络连接功能

## 签名和公证

### Windows代码签名
- 获取代码签名证书
- 使用signtool签名exe文件
- 提高用户信任度

### macOS公证
- 使用Apple开发者账号
- 通过notarytool公证
- 自动更新机制

## 总结

- **Windows打包**：必须在Windows环境中进行
- **macOS打包**：必须在macOS环境中进行
- **推荐方案**：使用GitHub Actions自动化打包
- **分发方式**：ZIP包（Windows）+ DMG镜像（macOS）
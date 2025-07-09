# Windows 打包脚本

Write-Host "开始构建 Windows 应用..." -ForegroundColor Green

# 清理之前的构建
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# 安装依赖
Write-Host "安装依赖..." -ForegroundColor Yellow
poetry install --with dev

# 使用 PyInstaller 打包
Write-Host "运行 PyInstaller..." -ForegroundColor Yellow
poetry run pyinstaller build.spec --clean --noconfirm

# 检查构建结果
if (Test-Path "dist\VolcengineVoiceChat\VolcengineVoiceChat.exe") {
    Write-Host "✅ Windows 应用构建成功！" -ForegroundColor Green
    Write-Host "应用位置: dist\VolcengineVoiceChat\" -ForegroundColor Green
    
    # 显示应用信息
    $size = (Get-ChildItem "dist\VolcengineVoiceChat" -Recurse | Measure-Object -Property Length -Sum).Sum
    $sizeInMB = [math]::Round($size / 1MB, 2)
    Write-Host "应用大小: $sizeInMB MB" -ForegroundColor Green
    
    # 可选：创建安装程序
    if (Get-Command "iscc.exe" -ErrorAction SilentlyContinue) {
        Write-Host "创建安装程序..." -ForegroundColor Yellow
        # 这里可以添加 Inno Setup 脚本来创建安装程序
        Write-Host "提示: 可以使用 Inno Setup 创建安装程序" -ForegroundColor Yellow
    }
    
    # 创建 ZIP 包
    Write-Host "创建 ZIP 包..." -ForegroundColor Yellow
    Compress-Archive -Path "dist\VolcengineVoiceChat\*" -DestinationPath "dist\VolcengineVoiceChat-Windows.zip" -Force
    Write-Host "✅ ZIP 包创建成功: dist\VolcengineVoiceChat-Windows.zip" -ForegroundColor Green
    
} else {
    Write-Host "❌ 构建失败！" -ForegroundColor Red
    exit 1
}

Write-Host "构建完成！" -ForegroundColor Green
#!/bin/bash

echo "🔧 修复 Semantic Release 配置和权限问题"
echo ""

# 1. 检查 Git 配置
echo "1️⃣ 检查 Git 配置..."
git_user=$(git config user.name)
git_email=$(git config user.email)

if [ -z "$git_user" ] || [ -z "$git_email" ]; then
    echo "❌ Git 用户信息未配置"
    echo "请运行以下命令配置："
    echo "  git config --global user.name \"你的用户名\""
    echo "  git config --global user.email \"你的邮箱\""
    exit 1
else
    echo "✅ Git 用户: $git_user <$git_email>"
fi

# 2. 检查远程仓库
echo ""
echo "2️⃣ 检查远程仓库配置..."
remote_url=$(git remote get-url origin 2>/dev/null)
if [ -z "$remote_url" ]; then
    echo "❌ 未找到远程仓库"
    exit 1
else
    echo "当前远程仓库: $remote_url"
fi

# 3. 提供解决方案
echo ""
echo "3️⃣ 解决 Git 推送权限问题的方案："
echo ""
echo "方案 A: 使用 SSH (推荐)"
echo "----------------------------------------"
echo "1. 生成 SSH 密钥（如果还没有）："
echo "   ssh-keygen -t ed25519 -C \"$git_email\""
echo ""
echo "2. 添加 SSH 密钥到 GitHub："
echo "   - 复制公钥: cat ~/.ssh/id_ed25519.pub"
echo "   - 访问: https://github.com/settings/keys"
echo "   - 点击 'New SSH key' 并粘贴"
echo ""
echo "3. 切换到 SSH URL:"
echo "   git remote set-url origin git@github.com:MarkShawn2020/volcengine-s2s-demo-py.git"
echo ""

echo "方案 B: 使用 GitHub Personal Access Token"
echo "----------------------------------------"
echo "1. 创建 Personal Access Token:"
echo "   - 访问: https://github.com/settings/tokens"
echo "   - 点击 'Generate new token'"
echo "   - 选择权限: repo (全部)"
echo ""
echo "2. 设置环境变量:"
echo "   export GH_TOKEN=你的token"
echo ""
echo "3. 或者更新远程 URL:"
echo "   git remote set-url origin https://你的token@github.com/MarkShawn2020/volcengine-s2s-demo-py.git"
echo ""

echo "方案 C: 本地测试（不推送）"
echo "----------------------------------------"
echo "使用 --no-push 选项进行本地测试："
echo "   poetry run semantic-release version --no-push"
echo ""

# 4. 检查当前分支
echo "4️⃣ 检查当前分支..."
current_branch=$(git branch --show-current)
echo "当前分支: $current_branch"
if [ "$current_branch" != "main" ]; then
    echo "⚠️  警告: semantic-release 配置为在 'main' 分支运行"
    echo "   请切换到 main 分支: git checkout main"
fi

# 5. 检查未提交的更改
echo ""
echo "5️⃣ 检查工作区状态..."
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  存在未提交的更改："
    git status --short
    echo ""
    echo "建议先提交或暂存这些更改："
    echo "  git add ."
    echo "  git commit -m \"chore: update semantic-release config\""
fi

echo ""
echo "📝 快速测试命令："
echo "----------------------------------------"
echo "# 本地测试（不推送）"
echo "poetry run semantic-release version --no-push"
echo ""
echo "# 查看将要发布的版本"
echo "poetry run semantic-release version --print"
echo ""
echo "# 强制发布（跳过 commit 分析）"
echo "poetry run semantic-release version --patch --no-push"
echo ""
echo "✅ 配置已更新，请选择上述方案之一解决推送权限问题"
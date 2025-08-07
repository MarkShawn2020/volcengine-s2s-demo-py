#!/bin/bash

echo "🔍 诊断 Semantic Release 自动化流程"
echo "===================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查 Git 配置
echo "1️⃣ 检查 Git 配置"
echo "-------------------"

git_user=$(git config user.name)
git_email=$(git config user.email)

if [ -z "$git_user" ] || [ -z "$git_email" ]; then
    echo -e "${RED}❌ Git 用户信息未配置${NC}"
    echo "   请运行："
    echo "   git config --global user.name \"你的用户名\""
    echo "   git config --global user.email \"你的邮箱\""
else
    echo -e "${GREEN}✅ Git 用户: $git_user <$git_email>${NC}"
fi

# 2. 检查远程仓库配置
echo ""
echo "2️⃣ 检查远程仓库配置"
echo "----------------------"

remote_url=$(git remote get-url origin 2>/dev/null)
if [ -z "$remote_url" ]; then
    echo -e "${RED}❌ 未找到远程仓库${NC}"
else
    echo "远程仓库: $remote_url"
    
    if [[ "$remote_url" == *"https://"* ]]; then
        echo -e "${YELLOW}⚠️  使用 HTTPS URL${NC}"
        echo "   建议切换到 SSH："
        echo "   git remote set-url origin git@github.com:MarkShawn2020/volcengine-s2s-demo-py.git"
    else
        echo -e "${GREEN}✅ 使用 SSH URL${NC}"
    fi
fi

# 3. 检查最近的 commits
echo ""
echo "3️⃣ 检查最近的 Semantic Commits"
echo "---------------------------------"

echo "最近 5 个 commits："
git log --oneline -5

echo ""
echo "符合 Semantic 规范的 commits："
git log --oneline -10 | grep -E '^[a-f0-9]+ (feat|fix|perf)(\(.*\))?!?:' || echo "没有找到符合规范的 commits"

# 4. 检查当前版本和 tags
echo ""
echo "4️⃣ 检查版本信息"
echo "-----------------"

echo "当前版本 (src/__init__.py):"
grep "__version__" src/__init__.py 2>/dev/null || echo "未找到版本信息"

echo ""
echo "最近的 tags:"
git tag -l "v*" | tail -5

# 5. 测试 semantic-release
echo ""
echo "5️⃣ 测试 Semantic Release"
echo "--------------------------"

echo "检查下一个版本（dry-run）："
poetry run semantic-release version --print-last-released 2>/dev/null || echo "无法获取上一个版本"
poetry run semantic-release version --dry-run 2>&1 | grep -E "(next version|No release|version)" || echo "Semantic Release 测试失败"

# 6. 检查工作流文件
echo ""
echo "6️⃣ 检查 GitHub Actions 工作流"
echo "--------------------------------"

if [ -f ".github/workflows/release.yml" ]; then
    echo -e "${GREEN}✅ release.yml 存在${NC}"
    
    # 检查关键配置
    if grep -q "poetry run semantic-release publish" .github/workflows/release.yml; then
        echo -e "${GREEN}✅ 包含 publish 命令${NC}"
    else
        echo -e "${RED}❌ 缺少 publish 命令${NC}"
    fi
    
    if grep -q "GH_TOKEN" .github/workflows/release.yml; then
        echo -e "${GREEN}✅ 配置了 GH_TOKEN${NC}"
    else
        echo -e "${RED}❌ 缺少 GH_TOKEN 配置${NC}"
    fi
else
    echo -e "${RED}❌ release.yml 不存在${NC}"
fi

if [ -f ".github/workflows/build-release.yml" ]; then
    echo -e "${GREEN}✅ build-release.yml 存在${NC}"
else
    echo -e "${YELLOW}⚠️  build-release.yml 不存在${NC}"
fi

# 7. 诊断结果
echo ""
echo "7️⃣ 诊断结果和建议"
echo "-------------------"

problems=0

# 检查问题
if [ -z "$git_user" ] || [ -z "$git_email" ]; then
    echo -e "${RED}问题 $((++problems)): Git 用户信息未配置${NC}"
fi

if [[ "$remote_url" == *"https://"* ]]; then
    echo -e "${YELLOW}建议: 使用 SSH URL 以避免认证问题${NC}"
fi

if ! git log --oneline -10 | grep -qE '^[a-f0-9]+ (feat|fix|perf)(\(.*\))?!?:'; then
    echo -e "${YELLOW}问题 $((++problems)): 最近没有符合规范的 commits${NC}"
    echo "   确保使用: git commit -m \"feat: 描述\" 或 \"fix: 描述\""
fi

if [ $problems -eq 0 ]; then
    echo -e "${GREEN}✅ 所有检查通过！自动化流程应该正常工作。${NC}"
else
    echo -e "${YELLOW}⚠️  发现 $problems 个问题需要解决${NC}"
fi

echo ""
echo "📝 测试自动化流程："
echo "-------------------"
echo "1. 创建一个符合规范的 commit："
echo "   git commit -m \"feat: test automatic release\""
echo ""
echo "2. 推送到 main 分支："
echo "   git push origin main"
echo ""
echo "3. 观察 GitHub Actions："
echo "   https://github.com/MarkShawn2020/volcengine-s2s-demo-py/actions"
echo ""
echo "4. 检查 Releases 页面："
echo "   https://github.com/MarkShawn2020/volcengine-s2s-demo-py/releases"
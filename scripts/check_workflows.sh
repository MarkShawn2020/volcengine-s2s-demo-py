#!/bin/bash

echo "🔍 GitHub Actions 工作流状态检查"
echo "=================================="
echo ""

# 检查工作流文件
echo "📁 当前激活的工作流："
for workflow in .github/workflows/*.yml; do
    if [ -f "$workflow" ]; then
        name=$(basename "$workflow")
        echo -n "  • $name - "
        
        # 提取触发条件
        if grep -q "push:" "$workflow"; then
            if grep -q "tags:" "$workflow"; then
                echo "仅在 tag 推送时触发 ✅"
            elif grep -q "branches:" "$workflow"; then
                echo "在分支推送时触发 ⚠️"
            fi
        else
            echo "手动或特殊触发 ℹ️"
        fi
    fi
done

echo ""
echo "🗑️  已禁用的工作流："
for workflow in .github/workflows/*.backup; do
    if [ -f "$workflow" ]; then
        name=$(basename "$workflow" .backup)
        echo "  • $name (已备份)"
    fi
done

echo ""
echo "📊 优化效果："
echo "  • 减少了重复构建 ✅"
echo "  • 文档更改不触发构建 ✅"
echo "  • 只在版本发布时构建应用 ✅"

echo ""
echo "💡 使用提示："
echo "  1. 新功能: git commit -m \"feat: 描述\" → 触发 Minor 版本发布"
echo "  2. Bug修复: git commit -m \"fix: 描述\" → 触发 Patch 版本发布"
echo "  3. 其他提交: 不触发版本发布和构建"
echo ""
echo "📚 详细说明请查看: .github/workflows/README_STRATEGY.md"
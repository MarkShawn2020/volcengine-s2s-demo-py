#!/usr/bin/env python3
"""
验证 GitHub Actions 工作流的 YAML 语法
"""
import yaml
import sys
import os
from pathlib import Path

def validate_yaml_file(filepath):
    """验证单个 YAML 文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return True, "OK"
    except yaml.YAMLError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"

def main():
    """主函数"""
    print("🔍 验证 GitHub Actions 工作流 YAML 语法")
    print("=" * 50)
    
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.exists():
        print("❌ 找不到 .github/workflows 目录")
        return 1
    
    yaml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if not yaml_files:
        print("⚠️  没有找到 YAML 文件")
        return 0
    
    errors = []
    for filepath in yaml_files:
        filename = filepath.name
        is_valid, message = validate_yaml_file(filepath)
        
        if is_valid:
            print(f"✅ {filename:30} - 语法正确")
        else:
            print(f"❌ {filename:30} - 语法错误")
            print(f"   错误信息: {message}")
            errors.append((filename, message))
    
    print("\n" + "=" * 50)
    
    if errors:
        print(f"\n❌ 发现 {len(errors)} 个文件有语法错误:")
        for filename, error in errors:
            print(f"\n文件: {filename}")
            print(f"错误: {error[:200]}...")  # 限制错误信息长度
        return 1
    else:
        print("\n✅ 所有工作流文件语法正确!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份Python代码到GitHub
- 自动将 D:\Python 同步到 GitHub
"""

import sys
import os
import subprocess
from datetime import datetime

# 设置标准输出和标准错误为UTF-8编码，解决Windows环境下emoji输出问题
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

REPO_PATH = r'D:\Python'


def run_git_command(repo_path: str, args: list) -> tuple:
    """执行git命令，返回(成功状态, 输出内容)"""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("🐍 备份Python代码到GitHub")
    print("=" * 60)
    print(f"📂 路径：{REPO_PATH}")
    print(f"🌐 远程：https://github.com/leokou/PythonCode")
    print("-" * 60)

    # 检查目录是否存在
    if not os.path.isdir(REPO_PATH):
        print(f"❌ 错误：目录不存在 {REPO_PATH}")
        return

    # 检查是否是git仓库
    if not os.path.isdir(os.path.join(REPO_PATH, '.git')):
        print(f"❌ 错误：不是Git仓库 {REPO_PATH}")
        return

    # 1. 检查状态
    print("\n🔍 检查文件状态...")
    success, output = run_git_command(REPO_PATH, ['status', '--porcelain'])
    if not success:
        print(f"❌ git status 失败：{output}")
        return

    if not output.strip():
        print(f"✅ 没有变更，无需同步")
        return

    changed_count = len([line for line in output.strip().split('\n') if line.strip()])
    print(f"📊 检测到 {changed_count} 个文件有变更")

    # 2. 添加所有变更
    print("\n📥 暂存变更文件...")
    success, output = run_git_command(REPO_PATH, ['add', '-A'])
    if not success:
        print(f"❌ git add 失败：{output}")
        return
    print(f"✅ 已暂存所有变更")

    # 3. 提交
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_msg = f"备份Python代码 @ {timestamp}"
    print(f"\n💾 提交变更：{commit_msg}")
    success, output = run_git_command(REPO_PATH, ['commit', '-m', commit_msg])
    if not success:
        if 'nothing to commit' in output or 'no changes' in output:
            print(f"✅ 没有需要提交的变更")
            return
        print(f"❌ git commit 失败：{output}")
        return
    print(f"✅ 提交成功")

    # 4. 推送
    print(f"\n🚀 推送到GitHub...")
    success, output = run_git_command(REPO_PATH, ['push'])
    if not success:
        print(f"❌ git push 失败：{output}")
        return
    print(f"✅ 推送成功")

    # 5. 显示最新提交
    success, output = run_git_command(REPO_PATH, ['log', '--oneline', '-1'])
    if success:
        print(f"\n📌 最新提交：{output.strip()}")

    print(f"\n{'='*60}")
    print(f"🎉 Python代码备份完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

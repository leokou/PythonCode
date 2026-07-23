#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian GitHub 同步工具
- 自动将本地仓库同步到GitHub
- 支持 PythonCode 和 ObsidianLeoDiary 两个仓库
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

# 仓库配置
REPOS = [
    {
        'name': 'PythonCode',
        'path': r'D:\Python',
        'remote': 'git@github.com:leokou/PythonCode.git'
    },
    {
        'name': 'ObsidianLeoDiary',
        'path': r'D:\Obsidian\LeoDiary',
        'remote': 'git@github.com:leokou/ObsidianLeoDiary.git'
    }
]


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


def sync_repo(repo: dict) -> bool:
    """同步单个仓库，返回是否成功"""
    repo_path = repo['path']
    repo_name = repo['name']

    print(f"\n{'='*60}")
    print(f"📁 仓库：{repo_name}")
    print(f"📂 路径：{repo_path}")
    print(f"{'='*60}")

    # 检查目录是否存在
    if not os.path.isdir(repo_path):
        print(f"❌ 错误：目录不存在 {repo_path}")
        return False

    # 检查是否是git仓库
    git_dir = os.path.join(repo_path, '.git')
    if not os.path.isdir(git_dir):
        print(f"❌ 错误：不是Git仓库 {repo_path}")
        return False

    # 1. 检查状态
    print("\n🔍 检查文件状态...")
    success, output = run_git_command(repo_path, ['status', '--porcelain'])
    if not success:
        print(f"❌ git status 失败：{output}")
        return False

    if not output.strip():
        print(f"✅ 没有变更，无需同步")
        return True

    changed_count = len([line for line in output.strip().split('\n') if line.strip()])
    print(f"📊 检测到 {changed_count} 个文件有变更")

    # 2. 添加所有变更
    print("\n📥 暂存变更文件...")
    success, output = run_git_command(repo_path, ['add', '-A'])
    if not success:
        print(f"❌ git add 失败：{output}")
        return False
    print(f"✅ 已暂存所有变更")

    # 3. 提交
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_msg = f"自动同步 @ {timestamp}"
    print(f"\n💾 提交变更：{commit_msg}")
    success, output = run_git_command(repo_path, ['commit', '-m', commit_msg])
    if not success:
        if 'nothing to commit' in output or 'no changes' in output:
            print(f"✅ 没有需要提交的变更")
            return True
        print(f"❌ git commit 失败：{output}")
        return False
    print(f"✅ 提交成功")

    # 4. 推送
    print(f"\n🚀 推送到GitHub...")
    success, output = run_git_command(repo_path, ['push'])
    if not success:
        print(f"❌ git push 失败：{output}")
        return False
    print(f"✅ 推送成功")

    # 5. 显示最新提交
    success, output = run_git_command(repo_path, ['log', '--oneline', '-1'])
    if success:
        print(f"\n📌 最新提交：{output.strip()}")

    return True


def main():
    print("=" * 60)
    print("🚀 Obsidian GitHub 同步工具")
    print("=" * 60)

    print("\n请选择要同步的仓库：")
    print(f"  1. 全部同步（{len(REPOS)}个仓库）")
    for i, repo in enumerate(REPOS, 2):
        print(f"  {i}. {repo['name']}（{repo['path']}）")
    print(f"  0. 退出")

    try:
        choice = input("\n请输入选项编号：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return

    if choice == '0':
        print("已退出")
        return

    if choice == '1':
        # 同步所有仓库
        success_count = 0
        fail_count = 0
        for repo in REPOS:
            if sync_repo(repo):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*60}")
        print(f"🎉 同步完成！成功 {success_count} 个，失败 {fail_count} 个")
        print(f"{'='*60}")

    elif choice.isdigit():
        idx = int(choice) - 2
        if 0 <= idx < len(REPOS):
            repo = REPOS[idx]
            if sync_repo(repo):
                print(f"\n🎉 {repo['name']} 同步成功！")
            else:
                print(f"\n❌ {repo['name']} 同步失败")
        else:
            print("❌ 无效的选项")
    else:
        print("❌ 无效的输入")


if __name__ == "__main__":
    main()

import sys
import os
import subprocess
import argparse
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

REPO_PATH = r'D:\Python'

TASK_NAME = "Python代码同步GitHub"

def run_git_command(repo_path, args):
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            shell=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Python 代码备份到 GitHub")
    parser.add_argument("--message", "-m", default="", help="版本说明")
    parser.add_argument("--remark", "-r", default="", help="版本说明（兼容）")
    args = parser.parse_args()
    message = (args.message or args.remark or "").strip()

    print(f"🔁 {TASK_NAME} 启动")
    print("=" * 60)
    print("🐍 备份Python代码到GitHub")
    print("=" * 60)
    print(f"📂 路径：{REPO_PATH}")
    print(f"🌐 远程：https://github.com/leokou/PythonCode")
    print("-" * 60)

    if not os.path.isdir(REPO_PATH):
        print(f"❌ 错误：目录不存在 {REPO_PATH}")
        print(f"❌ {TASK_NAME} 失败")
        return

    if not os.path.isdir(os.path.join(REPO_PATH, '.git')):
        print(f"❌ 错误：不是Git仓库 {REPO_PATH}")
        print(f"❌ {TASK_NAME} 失败")
        return

    if not message:
        message = f"备份Python代码 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    print("\n🔍 检查文件状态...")
    success, output = run_git_command(REPO_PATH, ['status', '--porcelain'])
    if not success:
        print(f"❌ git status 失败：{output}")
        print(f"❌ {TASK_NAME} 失败")
        return

    if not output.strip():
        print(f"✅ 没有变更，无需同步")
        print(f"✅ {TASK_NAME} 成功")
        return

    changed_count = len([line for line in output.strip().split('\n') if line.strip()])
    print(f"📊 检测到 {changed_count} 个文件有变更")

    print("\n📥 暂存变更文件...")
    success, output = run_git_command(REPO_PATH, ['add', '-A'])
    if not success:
        print(f"❌ git add 失败：{output}")
        print(f"❌ {TASK_NAME} 失败")
        return
    print(f"✅ 已暂存所有变更")

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_msg = f"{message}\n\n---\n备份Python代码 @ {timestamp}"
    print(f"\n💾 提交变更：{message}")
    success, output = run_git_command(REPO_PATH, ['commit', '-m', commit_msg])
    if not success:
        if 'nothing to commit' in output or 'no changes' in output:
            print(f"✅ 没有需要提交的变更")
            print(f"✅ {TASK_NAME} 成功")
            return
        print(f"❌ git commit 失败：{output}")
        print(f"❌ {TASK_NAME} 失败")
        return
    print(f"✅ 提交成功")

    print(f"\n🚀 推送到GitHub...")
    success, output = run_git_command(REPO_PATH, ['push'])
    if not success:
        print(f"❌ git push 失败：{output}")
        print(f"❌ {TASK_NAME} 失败")
        return
    print(f"✅ 推送成功")

    success, output = run_git_command(REPO_PATH, ['log', '--oneline', '-1'])
    if success:
        print(f"\n📌 最新提交：{output.strip()}")

    print(f"\n{'='*60}")
    print(f"🎉 Python代码备份完成！")
    print(f"✅ {TASK_NAME} 成功")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
import sys
import os
import subprocess
import argparse
import shutil
import stat
import tempfile
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

REPO_PATH = r'C:\Users\leokou\.claude\skills\Obsidian'
GITHUB_REPO = 'https://github.com/leokou/leodiary-skills'
CLONE_DIR = r"D:\project\leodiary-skills-tmp"

SKIP_DIRS = {'.system', '.obsidian', '__pycache__'}
SKIP_FILES = {'desktop.ini', '.DS_Store'}

def on_rmtree_error(func, path, exc_info):
    """处理 Windows 上 .git 只读文件导致的删除失败"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def run_git(repo_path, args, check=True):
    cwd = repo_path if (repo_path and os.path.isdir(repo_path)) else None
    result = subprocess.run(
        ['git'] + args,
        cwd=cwd,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        shell=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stdout + result.stderr}")
    return result

def main():
    parser = argparse.ArgumentParser(description="Skill 同步到 GitHub")
    parser.add_argument("--message", "-m", default="", help="版本说明")
    parser.add_argument("--remark", "-r", default="", help="版本说明（兼容）")
    args = parser.parse_args()
    message = (args.message or args.remark or "").strip()

    print("=" * 60)
    print("☁️  Claude Skill → GitHub 同步")
    print(f"源: {REPO_PATH}")
    print(f"目标: {GITHUB_REPO}")
    print("=" * 60)

    if not os.path.isdir(REPO_PATH):
        print(f"❌ 源目录不存在: {REPO_PATH}")
        return

    if not message:
        message = f"Skill 同步 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Step 1: Clone or pull the GitHub repo
    print("\n🔍 准备 GitHub 仓库...")
    if os.path.isdir(CLONE_DIR):
        shutil.rmtree(CLONE_DIR, onerror=on_rmtree_error)

    try:
        run_git(None, ['clone', GITHUB_REPO, CLONE_DIR])
        print(f"✅ 克隆成功: {CLONE_DIR}")
    except RuntimeError as e:
        print(f"⚠️  克隆失败: {e}")
        print("   如果是第一次使用，请先手动配置 Git 凭据。")
        return

    # Step 2: Clean clone dir (keep .git only) then copy skills
    print("\n🧹 清理 clone 目录（保留 .git）...")
    for item in os.listdir(CLONE_DIR):
        if item == '.git':
            continue
        item_path = os.path.join(CLONE_DIR, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path, onerror=on_rmtree_error)
        else:
            try:
                os.remove(item_path)
            except Exception:
                pass

    print("\n📥 复制 skills 到仓库...")
    skills_count = 0
    for item in sorted(os.listdir(REPO_PATH)):
        src = os.path.join(REPO_PATH, item)
        if item in SKIP_DIRS or item in SKIP_FILES:
            continue
        if not os.path.isdir(src):
            continue
        if not os.path.exists(os.path.join(src, "SKILL.md")):
            continue

        dst = os.path.join(CLONE_DIR, item)
        if os.path.exists(dst):
            shutil.rmtree(dst, onerror=on_rmtree_error)
        shutil.copytree(src, dst)
        print(f"  ✅ {item}")
        skills_count += 1

    print(f"📊 共复制 {skills_count} 个 skill")

    # Step 2.5: Copy top-level files (README.md, CLAUDE.md)
    print("\n📄 复制顶层文件...")
    top_files = ['README.md', 'CLAUDE.md']
    for fname in top_files:
        src_file = os.path.join(REPO_PATH, fname)
        if os.path.exists(src_file):
            shutil.copy2(src_file, os.path.join(CLONE_DIR, fname))
            print(f"  ✅ {fname}")

    # Step 3: Commit and push
    if skills_count == 0:
        print("⚠️  没有找到可同步的 skill")
        return

    print("\n📤 提交并推送到 GitHub...")
    try:
        run_git(CLONE_DIR, ['add', '-A'])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = f"{message}\n\n---\nAuto-sync {timestamp} | {skills_count} skills"
        run_git(CLONE_DIR, ['commit', '-m', commit_msg])
        print("✅ 提交成功")
    except RuntimeError as e:
        if 'nothing to commit' in str(e) or 'no changes' in str(e):
            print("✅ 没有变更，无需同步")
        else:
            print(f"❌ 提交失败: {e}")
            return

    try:
        run_git(CLONE_DIR, ['push', 'origin', 'main'])
        print("🚀 推送成功！")
    except RuntimeError as e:
        print(f"❌ 推送失败: {e}")
        print("   可能是认证问题，请检查 Git 凭据配置")
        return

    # Cleanup
    try:
        shutil.rmtree(CLONE_DIR, onerror=on_rmtree_error)
        print(f"\n🧹 清理临时目录")
    except Exception:
        pass

    print(f"\n{'='*60}")
    print(f"🎉 Skill 同步完成！")
    print(f"   版本说明: {message}")
    print(f"   Skill 数: {skills_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
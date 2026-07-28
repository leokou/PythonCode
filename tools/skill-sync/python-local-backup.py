import sys
import os
import shutil
import argparse
import stat
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SOURCE = r"D:\Python"
BACKUP_ROOT = r"D:\project\python备份"
MAX_BACKUPS = 10

def on_rmtree_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def main():
    parser = argparse.ArgumentParser(description="Python 代码本地备份")
    parser.add_argument("--remark", "-r", default="", help="备份备注")
    args = parser.parse_args()
    remark = args.remark.strip()

    print("=" * 50)
    print("📁 Python 代码本地备份")
    print(f"源: {SOURCE}")

    if not os.path.isdir(SOURCE):
        print(f"❌ 源目录不存在: {SOURCE}")
        return

    os.makedirs(BACKUP_ROOT, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if remark:
        backup_name = f"python-{timestamp}（{remark}）"
    else:
        backup_name = f"python-{timestamp}"
    backup_dir = os.path.join(BACKUP_ROOT, backup_name)

    existing = sorted([
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith("python-") and os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])
    if len(existing) >= MAX_BACKUPS:
        for old in existing[:len(existing) - MAX_BACKUPS + 1]:
            try:
                shutil.rmtree(os.path.join(BACKUP_ROOT, old), onerror=on_rmtree_error)
                print(f"🗑️  清理旧备份: {old}")
            except Exception:
                pass

    # Copy D:\Python but exclude large/generated dirs
    print(f"📦 备份目标: {backup_dir}")
    print("🔄 开始复制（可能需要几分钟）...")

    shutil.copytree(
        SOURCE, backup_dir,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', 'node_modules', 'dist', 'build'),
        symlinks=True
    )

    size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, dn, fn in os.walk(backup_dir)
        for f in fn
    )
    print(f"✅ 备份完成: {backup_dir}")
    print(f"   大小: {size / 1024 / 1024:.1f} MB")

    all_backups = sorted([
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith("python-") and os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])
    print(f"📋 现有备份 ({len(all_backups)} 个):")
    for b in all_backups:
        print(f"   {b}")

    print("=" * 50 + "\n")

if __name__ == "__main__":
    main()
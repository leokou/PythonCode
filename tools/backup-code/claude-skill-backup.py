import os
import shutil
import sys
import stat
import argparse
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SOURCE = r"C:\Users\leokou\.claude\skills"
BACKUP_ROOT = r"D:\project\skill备份"
MAX_BACKUPS = 10

TASK_NAME = "Claude Skill备份"

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "skill-backup.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def on_rmtree_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def main():
    parser = argparse.ArgumentParser(description="Claude Skill 备份")
    parser.add_argument("--remark", "-r", default="", help="备份备注")
    args = parser.parse_args()
    remark = args.remark.strip()

    log(f"🔁 {TASK_NAME} 启动")
    log("=" * 50)
    log("Claude Skill 备份 启动")
    log(f"源: {SOURCE}")

    if not os.path.isdir(SOURCE):
        log(f"❌ 源目录不存在: {SOURCE}")
        log(f"❌ {TASK_NAME} 失败")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if remark:
        backup_name = f"skills-{timestamp}（{remark}）"
    else:
        backup_name = f"skills-{timestamp}"
    backup_dir = os.path.join(BACKUP_ROOT, backup_name)

    os.makedirs(BACKUP_ROOT, exist_ok=True)

    existing = sorted([
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith("skills-") and os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])
    if len(existing) >= MAX_BACKUPS:
        remove_count = len(existing) - MAX_BACKUPS + 1
        for old in existing[:remove_count]:
            old_path = os.path.join(BACKUP_ROOT, old)
            try:
                shutil.rmtree(old_path, onerror=on_rmtree_error)
                log(f"🗑️  清理旧备份: {old}")
            except Exception as e:
                log(f"⚠️  清理失败 [{old}]: {e}")

    log(f"📦 备份目标: {backup_dir}")
    try:
        shutil.copytree(SOURCE, backup_dir)
        size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, dn, fn in os.walk(backup_dir)
            for f in fn
        )
        log(f"✅ 备份完成: {backup_dir}")
        log(f"   大小: {size / 1024 / 1024:.1f} MB")
    except Exception as e:
        log(f"❌ 备份失败: {e}")
        log(f"❌ {TASK_NAME} 失败")
        return

    all_backups = sorted([
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith("skills-") and os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])
    log(f"📋 现有备份 ({len(all_backups)} 个):")
    for b in all_backups:
        log(f"   {b}")

    log("Claude Skill 备份 完成")
    log(f"✅ {TASK_NAME} 成功")
    log("=" * 50 + "\n")

if __name__ == "__main__":
    main()
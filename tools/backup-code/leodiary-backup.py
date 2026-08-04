#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SOURCE_DIR = Path(r"D:\Obsidian\LeoDiary")
BACKUP_ROOT = Path(r"D:\Obsidian\Backup")

SKIP_DIRS = {
    '.obsidian', '.trash', '.smart-env', '.claude', '.claudian',
    '.mimocode', '.workbuddy', '.git',
    'assets', 'Excalidraw', 'Clippings',
}
SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg',
                   '.mp4', '.mp3', '.wav', '.avi', '.mov',
                   '.zip', '.rar', '.7z', '.tar', '.gz',
                   '.pdf', '.epub', '.mobi'}

MAX_BACKUPS = 50

TASK_NAME = "Obsidian笔记备份"

def get_backup_dir(remark="") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if remark:
        return BACKUP_ROOT / f"LeoDiary_{timestamp}（{remark}）"
    return BACKUP_ROOT / f"LeoDiary_{timestamp}"

def should_skip_dir(dir_name: str) -> bool:
    if dir_name in SKIP_DIRS:
        return True
    if dir_name.startswith('.'):
        return True
    return False

def should_skip_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in SKIP_EXTENSIONS

def backup_files(src_dir: Path, dst_dir: Path) -> tuple:
    copied = 0
    skipped = 0
    for entry in src_dir.iterdir():
        if entry.is_dir():
            if should_skip_dir(entry.name):
                continue
            rel = entry.relative_to(src_dir)
            sub_dst = dst_dir / rel
            c, s = backup_files(entry, sub_dst)
            copied += c
            skipped += s
        elif entry.is_file():
            if should_skip_file(entry.name):
                skipped += 1
                continue
            rel = entry.relative_to(src_dir)
            dst = dst_dir / rel
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, dst)
                copied += 1
            except Exception as e:
                print(f"  ⚠️ 复制失败：{entry} - {e}")
                skipped += 1
    return copied, skipped

def main():
    parser = argparse.ArgumentParser(description="Obsidian 笔记备份")
    parser.add_argument("--remark", "-r", default="", help="备份备注")
    args = parser.parse_args()
    remark = args.remark.strip()

    print(f"🔁 {TASK_NAME} 启动")

    if not SOURCE_DIR.exists():
        print(f"❌ 源目录不存在：{SOURCE_DIR}")
        print(f"❌ {TASK_NAME} 失败")
        sys.exit(1)

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    # Rotate old backups
    existing = sorted([
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith("LeoDiary_") and os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])
    if len(existing) >= MAX_BACKUPS:
        for old in existing[:len(existing) - MAX_BACKUPS + 1]:
            try:
                shutil.rmtree(os.path.join(BACKUP_ROOT, old))
                print(f"🗑️  清理旧备份: {old}")
            except Exception:
                pass

    backup_dir = get_backup_dir(remark)
    print(f"📦 Obsidian 笔记备份工具")
    print(f"📂 源目录：{SOURCE_DIR}")
    print(f"📁 备份到：{backup_dir}")
    if remark:
        print(f"🏷️  备注：{remark}")
    print("-" * 60)

    backup_dir.mkdir(parents=True, exist_ok=True)

    print("🔄 开始备份...")
    copied, skipped = backup_files(SOURCE_DIR, backup_dir)

    print("-" * 60)
    print(f"✅ 备份完成！")
    print(f"📄 复制文件：{copied} 个")
    print(f"⏭️  跳过文件：{skipped} 个")
    print(f"📁 备份位置：{backup_dir}")
    print(f"✅ {TASK_NAME} 成功")

if __name__ == "__main__":
    main()
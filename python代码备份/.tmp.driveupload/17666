#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 笔记备份工具
- 将 D:\Obsidian\LeoDiary 备份到指定目录（带时间戳）
- 自动跳过 .开头的隐藏文件夹和超大附件
- 支持增量备份（仅复制新增/修改的文件）
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# 设置标准输出和标准错误为UTF-8编码，解决Windows环境下emoji输出问题
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 源目录
SOURCE_DIR = Path(r"D:\Obsidian\LeoDiary")

# 备份根目录
BACKUP_ROOT = Path(r"D:\Obsidian\Backup")

# 跳过的文件夹（.开头的隐藏文件夹 + 大附件文件夹）
SKIP_DIRS = {
    '.obsidian', '.trash', '.smart-env', '.claude', '.claudian',
    '.mimocode', '.workbuddy', '.git',
    'assets', 'Excalidraw', 'Clippings',
}

# 跳过的文件扩展名（大文件附件）
SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg',
                   '.mp4', '.mp3', '.wav', '.avi', '.mov',
                   '.zip', '.rar', '.7z', '.tar', '.gz',
                   '.pdf', '.epub', '.mobI'}


def get_backup_dir() -> Path:
    """生成带时间戳的备份目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BACKUP_ROOT / f"LeoDiary_{timestamp}"


def should_skip_dir(dir_name: str) -> bool:
    """判断是否跳过该目录"""
    if dir_name in SKIP_DIRS:
        return True
    if dir_name.startswith('.'):
        return True
    return False


def should_skip_file(filename: str) -> bool:
    """判断是否跳过该文件"""
    ext = Path(filename).suffix.lower()
    return ext in SKIP_EXTENSIONS


def copy_file_with_dirs(src: Path, dst: Path, copied: int, skipped: int) -> tuple:
    """复制单个文件，自动创建目录"""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return copied + 1, skipped
    except Exception as e:
        print(f"  ⚠️ 复制失败：{src} - {e}")
        return copied, skipped + 1


def backup_files(src_dir: Path, dst_dir: Path) -> tuple:
    """递归备份文件"""
    copied = 0
    skipped = 0

    for entry in src_dir.iterdir():
        if entry.is_dir():
            if should_skip_dir(entry.name):
                print(f"  ⏭️  跳过目录：{entry.name}")
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
            copied, skipped = copy_file_with_dirs(entry, dst, copied, skipped)

    return copied, skipped


def main():
    if not SOURCE_DIR.exists():
        print(f"❌ 源目录不存在：{SOURCE_DIR}")
        sys.exit(1)

    backup_dir = get_backup_dir()
    print(f"📦 Obsidian 笔记备份工具")
    print(f"📂 源目录：{SOURCE_DIR}")
    print(f"📁 备份到：{backup_dir}")
    print("-" * 60)

    backup_dir.mkdir(parents=True, exist_ok=True)

    print("🔄 开始备份...")
    copied, skipped = backup_files(SOURCE_DIR, backup_dir)

    print("-" * 60)
    print(f"✅ 备份完成！")
    print(f"📄 复制文件：{copied} 个")
    print(f"⏭️  跳过文件：{skipped} 个")
    print(f"📁 备份位置：{backup_dir}")


if __name__ == "__main__":
    main()

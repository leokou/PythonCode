#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 文件名标题检查工具
===========================
检查所有 .md 文件，确保第一行是 "# 文件名"。
- 空文件 → 写入 "# 文件名\n"
- 第一行已经是 "# 文件名" → 跳过
- 第一行以 "# " 开头但文字不符 → 替换第一行
- 第一行不是 "# " 开头 → 在开头插入 "# 文件名\n\n"
"""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VAULT_ROOT = Path(r"D:\Obsidian\LeoDiary")

SKIP_DIRS = {
    ".obsidian", ".git", ".trash", ".claude", ".claudian",
    ".smart-env", ".workbuddy", "__pycache__", "node_modules",
    ".qoderworkcn", "templates", "Journals",
    "assets", "Canvas", "Clippings", "Excalidraw", "obsidian-index",
}

# 跳过的文件（索引类文件）
SKIP_FILES_PREFIX = ("🧩 目录-", "🏠 home-")
SKIP_FILES_EXACT = {"🤖 AI指令.md"}


def ensure_title(file_path: Path) -> bool:
    """确保单个 .md 文件第一行是 "# 文件名"。返回是否做了修改。"""
    expected = f"# {file_path.stem}"
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"   ⚠️  读取失败: {file_path.name}: {e}")
        return False

    if not content.strip():
        new_content = expected + "\n"
    else:
        lines = content.splitlines(keepends=True)
        first_line = lines[0].rstrip("\r\n") if lines else ""
        if first_line.strip() == expected:
            return False

        if first_line.startswith("# "):
            nl = "\n" if ("\n" in lines[0] or "\r" in lines[0]) else ""
            lines[0] = expected + nl
            new_content = "".join(lines)
        else:
            new_content = expected + "\n\n" + content

    try:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"   🏷️  修正: {file_path.relative_to(VAULT_ROOT)} → '{expected}'")
    except Exception as e:
        print(f"   ⚠️  写入失败: {file_path.name}: {e}")
        return False
    return True


def main():
    print("=" * 60)
    print("🏷️  Obsidian 文件名标题检查")
    print(f"Vault: {VAULT_ROOT}")
    print("=" * 60)
    print()

    total = 0
    fixed = 0

    for root, dirs, files in os.walk(VAULT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for f in files:
            if not f.endswith(".md"):
                continue
            if f.startswith(SKIP_FILES_PREFIX) or f in SKIP_FILES_EXACT:
                continue
            total += 1
            if ensure_title(root_path / f):
                fixed += 1

    print()
    print("=" * 60)
    print(f"📊 检查了 {total} 个文件，修正了 {fixed} 个")
    print("🎉 完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

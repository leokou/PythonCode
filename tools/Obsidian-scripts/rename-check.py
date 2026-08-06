#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---
# type: 工具
# tags: ['阿里官方推理平台', '开发', '魔搭ModelScope', 'API接入', 'AI']
# created: 2026-07-25
# modified: 2026-07-25
# ---
"""
Obsidian 文件名标题检查工具
===========================
规则：frontmatter 在文件开头，标题紧跟其后（无多余空行）
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from obsidian_common import (
    VAULT_ROOT, SKIP_DIRS, SKIP_FILES_PREFIX, SKIP_FILES_EXACT,
    should_skip_dir,
)


def ensure_title(file_path: Path) -> bool:
    expected = f"# {file_path.stem}"
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"   ⚠️  读取失败: {file_path.name}: {e}")
        return False

    if not content.strip():
        new_content = expected + "\n"
        file_path.write_text(new_content, encoding="utf-8")
        print(f"   🏷️  创建: {file_path.relative_to(VAULT_ROOT)} → '{expected}'")
        return True

    # 提取 frontmatter (文件开头)
    fm_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    match = fm_pattern.search(content)

    if match:
        fm_full = match.group(0)
        remaining = content[match.end():]
    else:
        fm_full = None
        remaining = content

    # 先删掉所有旧标题行（以 # 开头的行）
    lines = remaining.splitlines(keepends=True)
    other_lines = []
    removed_titles = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("# "):
            removed_titles.append(stripped[:60])
        else:
            other_lines.append(line)

    # 移除标题后的空行，确保标题后面紧跟内容
    while other_lines and other_lines[0].strip() == "":
        other_lines.pop(0)

    # 构建新内容：frontmatter 后面直接跟标题，不要有空行
    parts = []
    if fm_full is not None:
        fm_full = fm_full.rstrip("\n\r") + "\n"
        parts.append(fm_full)
    parts.append(expected + "\n")
    if other_lines:
        parts.extend(other_lines)

    new_content = "".join(parts)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    if removed_titles:
        print(f"   🏷️  修正: {file_path.relative_to(VAULT_ROOT)} → '{expected}' (删除了 {len(removed_titles)} 个旧标题)")
    else:
        print(f"   🏷️  修正: {file_path.relative_to(VAULT_ROOT)} → '{expected}'")
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
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
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
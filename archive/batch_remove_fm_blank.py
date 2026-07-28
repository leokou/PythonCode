#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量去掉所有 md 文件 frontmatter 结束后紧跟的空行
规则：
  - frontmatter 的第二个 --- 后面如果是空行，直接删掉那行空行
  - 让 --- 后面直接接 # 标题
  - 不动其他地方的空行
"""

import sys
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from obsidian_common import VAULT_ROOT, should_skip_dir


def remove_fm_blank_line(content: str) -> str:
    """去掉 frontmatter 结束 --- 后的第一个空行"""
    lines = content.splitlines(keepends=True)
    if not lines:
        return content

    # 找第一个 ---
    if not lines[0].strip() == '---':
        return content

    # 找第二个 ---
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break

    if end_idx == -1 or end_idx + 1 >= len(lines):
        return content

    # 检查下一行是不是空行
    next_line = lines[end_idx + 1]
    if next_line.strip() == '':
        # 删除这个空行
        new_lines = lines[:end_idx+1] + lines[end_idx+2:]
        return ''.join(new_lines)

    return content


def main():
    stats = {'total': 0, 'modified': 0, 'skipped': 0, 'failed': 0}

    for path in sorted(VAULT_ROOT.rglob('*.md')):
        rel = path.relative_to(VAULT_ROOT)
        skip = False
        for part in rel.parts[:-1]:
            if should_skip_dir(part):
                skip = True
                break
        if skip:
            stats['skipped'] += 1
            continue
        if str(rel).startswith('logs/') or 'processed-' in str(rel):
            stats['skipped'] += 1
            continue

        stats['total'] += 1
        try:
            content = path.read_text(encoding='utf-8-sig')
        except Exception as e:
            stats['failed'] += 1
            continue

        new_content = remove_fm_blank_line(content)
        if new_content != content:
            try:
                path.write_text(new_content, encoding='utf-8')
                stats['modified'] += 1
            except Exception as e:
                stats['failed'] += 1

    print(f"\n{'='*60}")
    print(f"批量去掉 frontmatter 后空行 完成")
    print(f"{'='*60}")
    print(f"总文件数: {stats['total']}")
    print(f"已修改:   {stats['modified']}")
    print(f"已跳过:   {stats['skipped']}")
    print(f"失败:     {stats['failed']}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

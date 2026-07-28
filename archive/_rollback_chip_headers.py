#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回滚 🧩 目录文件中的分类标题：
- ## 📁 xxx → ##### xxx（去掉 📁 前缀，改回五级标题）
- ## 📌 一句话总结 不改
"""
import re
from pathlib import Path
import sys, os

sys.path.insert(0, str(Path(__file__).parent))
from obsidian_common import should_skip_dir, read_text_safe

vault = Path(r"D:\Obsidian\LeoDiary")

fixed_count = 0
scanned_count = 0

for root, dirs, files in os.walk(vault):
    dirs[:] = [d for d in dirs if not should_skip_dir(d)]
    for fname in files:
        if not fname.startswith("🧩 目录-") or not fname.endswith(".md"):
            continue
        
        fpath = Path(root) / fname
        scanned_count += 1
        content = read_text_safe(fpath)
        if not content:
            continue
        
        lines = content.splitlines(keepends=True)
        changed = False
        
        for i, line in enumerate(lines):
            stripped = line.rstrip('\r\n')
            # 只改 ## 📁 开头的分类标题（不改 ## 📌 一句话总结）
            if stripped.startswith('## 📁 '):
                # 提取 📁 后面的内容
                title_text = stripped[len('## 📁 '):].strip()
                new_line = f"##### {title_text}"
                nl = '\n' if '\n' in line else ''
                lines[i] = new_line + nl
                changed = True
        
        if changed:
            try:
                fpath.write_text(''.join(lines), encoding='utf-8')
                fixed_count += 1
                print(f"  ✅ 回滚：{fpath.relative_to(vault)}")
            except Exception as e:
                print(f"  ❌ 写入失败：{fpath} - {e}")

print(f"\n扫描 {scanned_count} 个 🧩 目录文件，回滚 {fixed_count} 个")

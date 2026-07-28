#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复 🧩 目录文件中的分类标题级别：
- ##### xxx → ## 📁 xxx
- ### xxx（非📌非📁）→ ## 📁 xxx
- 保持 # 标题、## 📌、## 📁 等已正确格式不变
"""
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from obsidian_common import should_skip_dir, read_text_safe

vault = Path(r"D:\Obsidian\LeoDiary")

# 匹配分类标题行
# ##### emoji 名称 或 ##### 名称
re_h5 = re.compile(r'^(#{5})\s+(.+)$')
# ### 名称（但不是 ### 📌 或 ### 📁，这些可能已有正确格式）
re_h3 = re.compile(r'^(#{3})\s+(.+)$')

fixed_count = 0
scanned_count = 0

for root, dirs, files in __import__('os').walk(vault):
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
            
            # 跳过 # 一级标题
            if stripped.startswith('# '):
                continue
            
            # 跳过 ## 开头的（已正确）
            if stripped.startswith('## '):
                continue
            
            # ##### xxx → ## 📁 xxx
            m5 = re_h5.match(stripped)
            if m5:
                title_text = m5.group(2).strip()
                # 如果已经有 📁 前缀，不重复加
                if title_text.startswith('📁'):
                    new_line = f"## {title_text}"
                else:
                    new_line = f"## 📁 {title_text}"
                # 保留行尾换行
                nl = '\n' if '\n' in line else ''
                lines[i] = new_line + nl
                changed = True
                continue
            
            # ### xxx（非📌非📁）→ ## 📁 xxx
            m3 = re_h3.match(stripped)
            if m3:
                title_text = m3.group(2).strip()
                # 跳过已有正确前缀的
                if title_text.startswith('📌') or title_text.startswith('📁'):
                    continue
                new_line = f"## 📁 {title_text}"
                nl = '\n' if '\n' in line else ''
                lines[i] = new_line + nl
                changed = True
                continue
        
        if changed:
            try:
                fpath.write_text(''.join(lines), encoding='utf-8')
                fixed_count += 1
                print(f"  ✅ 修复：{fpath.relative_to(vault)}")
            except Exception as e:
                print(f"  ❌ 写入失败：{fpath} - {e}")

print(f"\n扫描 {scanned_count} 个 🧩 目录文件，修复 {fixed_count} 个")

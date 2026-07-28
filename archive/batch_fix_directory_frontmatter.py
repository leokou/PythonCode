#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量规范化所有 🧩 目录-xxx.md 文件的 frontmatter
规则：
  - 只保留 created / modified 两个字段
  - 删除 type / tags / title / source 等其他字段
  - 保留原文件已有的 created/modified 值（没有就填今天）
  - frontmatter 必须在文件开头
  - 不动分类区域和其他正文内容
"""

import re
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in __import__('sys').path:
    __import__('sys').path.insert(0, str(SCRIPT_DIR))

from obsidian_common import VAULT_ROOT, should_skip_dir

TODAY = date.today().isoformat()

def parse_frontmatter(content: str):
    """解析 frontmatter，返回 (fm_dict, body, fm_raw_lines) 或 (None, content, None)"""
    stripped = content.lstrip()
    if not stripped.startswith('---'):
        return None, content, None

    # 找第二个 ---
    lines = content.splitlines(keepends=True)
    # 找第一个 ---（可能在第一行，也可能前面有空行）
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == '---':
            start = i
            break
    if start == -1:
        return None, content, None

    # 找第二个 ---
    end = -1
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break
    if end == -1:
        return None, content, None

    fm_text = ''.join(lines[start+1:end])
    body = ''.join(lines[end+1:])
    return fm_text, body, (start, end)


def extract_created_modified(fm_text: str):
    """从 frontmatter 文本中提取 created 和 modified"""
    created = None
    modified = None
    for line in fm_text.splitlines():
        m = re.match(r'^created\s*:\s*(\S+)', line.strip())
        if m:
            created = m.group(1)
        m = re.match(r'^modified\s*:\s*(\S+)', line.strip())
        if m:
            modified = m.group(1)
    return created, modified


def build_new_frontmatter(created: str, modified: str) -> str:
    """构造新的 frontmatter"""
    return f"---\ncreated: {created}\nmodified: {modified}\n---\n"


def remove_stale_frontmatter_blocks(body: str) -> str:
    """清理正文中残留的 frontmatter 块（--- 包裹的孤立块）。

    规则：从 body 的第二行开始，如果遇到 --- 开头的行，
    且下方紧跟的是 frontmatter 字段（key: value 格式），
    且之后又有 --- 闭合，则视为残留 frontmatter，删除整个块。
    """
    lines = body.splitlines(keepends=True)
    if not lines:
        return body

    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 检查是否是潜在的残留 frontmatter 开始（不是文件第一行）
        if (i > 0 and line.strip() == '---'
                and i + 1 < len(lines)):
            # 检查接下来几行是否像 frontmatter 字段
            j = i + 1
            looks_like_fm = False
            field_count = 0
            while j < len(lines):
                inner = lines[j].strip()
                if inner == '---':
                    # 闭合了
                    if field_count >= 1:
                        looks_like_fm = True
                    break
                # 检查是否是 key: value 格式
                if re.match(r'^[\w\-]+\s*:\s*', inner):
                    field_count += 1
                    j += 1
                elif inner == '':
                    # 空行允许（但不超过1个连续）
                    j += 1
                else:
                    # 不是 frontmatter 字段，是普通内容
                    break

            if looks_like_fm and j < len(lines) and lines[j].strip() == '---':
                # 这是残留 frontmatter，跳过整个块（i 到 j 含）
                # 同时跳过块后的一个空行（如果有）
                i = j + 1
                if i < len(lines) and lines[i].strip() == '':
                    i += 1
                continue

        result.append(line)
        i += 1

    return ''.join(result)


def process_file(path: Path) -> str:
    """处理单个文件，返回状态字符串"""
    try:
        content = path.read_text(encoding='utf-8-sig')
    except Exception as e:
        return f"读取失败: {e}"

    fm_text, body, fm_range = parse_frontmatter(content)

    if fm_text is None:
        # 没有 frontmatter，添加一个
        new_fm = build_new_frontmatter(TODAY, TODAY)
        body_clean = remove_stale_frontmatter_blocks(body.lstrip('\n'))
        new_content = new_fm + "\n" + body_clean
        try:
            path.write_text(new_content, encoding='utf-8')
            return "新增 frontmatter"
        except Exception as e:
            return f"写入失败: {e}"

    # 有 frontmatter，提取 created/modified
    created, modified = extract_created_modified(fm_text)
    if not created:
        created = TODAY
    if not modified:
        modified = TODAY

    new_fm = build_new_frontmatter(created, modified)
    body_clean = remove_stale_frontmatter_blocks(body.lstrip('\n'))
    if body_clean.startswith('# '):
        new_content = new_fm + "\n" + body_clean
    else:
        new_content = new_fm + "\n" + body_clean

    try:
        path.write_text(new_content, encoding='utf-8')
        return "规范化 frontmatter"
    except Exception as e:
        return f"写入失败: {e}"


def main():
    stats = {'processed': 0, 'skipped': 0, 'failed': 0}
    results = []

    for path in sorted(VAULT_ROOT.rglob("🧩 目录-*.md")):
        # 跳过应该跳过的目录
        rel = path.relative_to(VAULT_ROOT)
        skip = False
        for part in rel.parts[:-1]:
            if should_skip_dir(part):
                skip = True
                break
        if skip:
            stats['skipped'] += 1
            continue

        status = process_file(path)
        results.append((str(rel), status))
        if '失败' in status:
            stats['failed'] += 1
        else:
            stats['processed'] += 1

    print(f"\n{'='*60}")
    print(f"批量规范化 🧩 目录-xxx.md frontmatter 完成")
    print(f"{'='*60}")
    print(f"总文件数: {stats['processed'] + stats['skipped'] + stats['failed']}")
    print(f"已处理:   {stats['processed']}")
    print(f"已跳过:   {stats['skipped']}（隐藏/排除目录）")
    print(f"失败:     {stats['failed']}")
    print(f"{'='*60}\n")

    # 输出前 20 个处理结果
    print("处理详情（前 30 条）:")
    for path_str, status in results[:30]:
        print(f"  [{status}] {path_str}")
    if len(results) > 30:
        print(f"  ... 还有 {len(results) - 30} 条")


if __name__ == '__main__':
    main()

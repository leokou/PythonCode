#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LD-DVA Final Frontmatter 批量补全脚本
======================================
为所有知识文件补充缺失的 AI_INDEX 扩展字段：
- id: leo-YYYYMMDD-NNN
- keywords: 从标题+正文提取 3-10 个关键词
- summary: 三段式摘要（定位+关键词+适用场景）
- updated: 最后更新日期

不覆盖已有字段，只补全缺失的。

用法：
  python frontmatter_enrich.py              试运行（dry-run），只报告不修改
  python frontmatter_enrich.py --apply      实际执行修改
  python frontmatter_enrich.py --apply --verbose  详细输出
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Windows 控制台编码
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))
from obsidian_common import (
    VAULT_ROOT, should_skip_dir, should_skip_file,
    read_text_safe, strip_frontmatter,
)

KNOWLEDGE_DIR_PREFIXES = ("0-", "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-")

# type → 描述映射（用于三段式摘要的"定位"部分）
TYPE_DESC = {
    '知识': '知识文档', '工具': '工具/软件', '项目文档': '项目文档',
    '踩坑': '踩坑记录', 'FAQ': '常见问题', '教程': '操作教程',
    '清单': '检查清单', '账号': '账号信息', '会议': '会议记录',
    '决策': '决策记录', '规范': '规范文档', '记录': '记录文档',
}

# type → 适用场景映射
TYPE_SCENARIO = {
    '知识': '知识积累与检索',
    '工具': '工具选择、配置与使用',
    '项目文档': '项目管理和执行参考',
    '踩坑': '问题排查和避坑',
    'FAQ': '快速查找常见问答',
    '教程': '按步骤操作学习',
    '清单': '流程执行前检查确认',
    '账号': '账号安全和配置参考',
    '会议': '会议回顾和决策追溯',
    '决策': '决策参考和经验复盘',
    '规范': '标准遵循和质量保障',
    '记录': '信息存档和追溯',
}

STOP_WORDS = {
    '的', '了', '是', '在', '有', '和', '与', '或', '为', '对', '用', '向', '从', '到',
    '这是', '可以', '通过', '使用', '进行', '其中', '以及', '如果', '但是', '因为',
    'the', 'a', 'an', 'is', 'to', 'of', 'in', 'for', 'on', 'and', 'or', 'with',
    'pro', 'md', 'app', 'info',
    'config', 'data', 'code', 'file', 'page', 'tool', 'new', 'old', 'test', 'demo',
    'todo', 'src', 'prod', 'log', 'set', 'get', 'id', 'key', 'url', 'uri',
    'path', 'dir', 'name', 'type', 'time', 'date', 'note', 'notes', 'learn',
    'read', 'write', 'open', 'close', 'start', 'end', 'run', 'stop', 'load', 'save',
    'check', 'update', 'create', 'delete', 'list', 'item', 'user', 'pass', 'word',
    'text', 'line', 'step', 'part', 'case', 'example', '说明', '方法', '使用',
    'http', 'https', 'www', 'com', 'org', 'net', 'io', 'cn',
    'npm', 'pip',
}


def collect_files(vault_root: Path) -> list:
    """Collect all knowledge .md files."""
    result = []
    for entry in vault_root.iterdir():
        if not entry.is_dir() or should_skip_dir(entry.name):
            continue
        if not entry.name.startswith(KNOWLEDGE_DIR_PREFIXES):
            continue
        for root, dirs, files in os.walk(entry):
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            for f in files:
                if not f.endswith('.md'):
                    continue
                fp = Path(root) / f
                if should_skip_file(f):
                    continue
                result.append(fp)
    return result


def parse_frontmatter(content: str) -> tuple:
    """Parse frontmatter. Returns (fm_dict, fm_start_line, fm_end_line, raw_lines)."""
    lines = content.splitlines(keepends=True)
    fm_dict = {}
    fm_start = -1
    fm_end = -1

    for i, line in enumerate(lines):
        if line.strip() == '---':
            if fm_start == -1:
                fm_start = i
            else:
                fm_end = i
                break

    if fm_start == -1 or fm_end == -1:
        return fm_dict, -1, -1, lines

    current_key = None
    for i in range(fm_start + 1, fm_end):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ':' in stripped:
            key, _, value = stripped.partition(':')
            key = key.strip()
            value = value.strip()
            if value.startswith('|') or value.startswith('>'):
                current_key = key
                fm_dict[key] = ""
                continue
            current_key = None
            fm_dict[key] = _parse_value(value)
        elif current_key and line.startswith(' '):
            val = stripped.strip('-').strip()
            if val:
                existing = fm_dict.get(current_key, "")
                fm_dict[current_key] = (existing + "\n" + val).strip() if existing else val

    return fm_dict, fm_start, fm_end, lines


def _parse_value(value: str):
    """Parse a YAML value."""
    if not value:
        return ""
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip('"').strip("'") for v in inner.split(',')]
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def generate_id(file_path: Path, counter_map: dict) -> str:
    """Generate unique ID: leo-YYYYMMDD-NNN."""
    try:
        mtime = os.path.getmtime(file_path)
        dt = datetime.fromtimestamp(mtime)
    except Exception:
        dt = datetime.now()
    date_str = dt.strftime('%Y%m%d')
    counter_map[date_str] = counter_map.get(date_str, 0) + 1
    seq = counter_map[date_str]
    return f"leo-{date_str}-{seq:03d}"


def extract_keywords(title: str, body: str, max_count: int = 8) -> list:
    """Extract meaningful keywords from title and first section of body."""
    def _is_good_keyword(token: str) -> bool:
        """Filter: skip stop words, pure digits, overly long Chinese fragments."""
        if token.lower() in STOP_WORDS:
            return False
        if re.match(r'^[\d]+$', token):
            return False
        # 中文 token：2-6 字是好的关键词，超过 6 字通常是句子片段
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', token))
        if chinese_chars > 6:
            return False
        # 英文 token：至少 3 字符
        if not chinese_chars and len(token) < 3:
            return False
        # 总长度不超过 12
        if len(token) > 12:
            return False
        return True

    # 从标题提取（标题里的词更可能是关键词）
    title_words = []
    for token in re.findall(r'[a-zA-Z\u4e00-\u9fff]+', title):
        if _is_good_keyword(token) and token not in title_words:
            title_words.append(token)

    # 从标题中的分隔符提取短语关键词（- @ / 分隔）
    title_phrases = re.split(r'[\s\-@/·]+', title)
    for phrase in title_phrases:
        phrase = phrase.strip()
        if 2 <= len(phrase) <= 8 and _is_good_keyword(phrase) and phrase not in title_words:
            title_words.insert(0, phrase)  # 短语关键词优先级最高

    # 从正文第一段提取（只取短 token）
    body = strip_frontmatter(body) if '---' in body[:100] else body
    first_section = body[:2000]
    body_words = []
    for token in re.findall(r'[a-zA-Z\u4e00-\u9fff]+', first_section):
        if _is_good_keyword(token) and token not in title_words and token not in body_words:
            body_words.append(token)

    # 标题词优先 + 正文补充
    keywords = title_words[:max_count]
    for w in body_words:
        if len(keywords) >= max_count:
            break
        keywords.append(w)

    return keywords


def generate_summary(title: str, doc_type: str, keywords: list, body: str) -> str:
    """Generate three-part summary: 定位 + 关键词 + 适用场景."""
    # 第一段：定位
    type_desc = TYPE_DESC.get(doc_type, doc_type or '知识文档')
    # 从正文提取用途（找第一个有意义的描述行）
    purpose = ''
    body_text = strip_frontmatter(body) if '---' in body[:100] else body
    for line in body_text.splitlines():
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # 跳过非描述性行
        if line.startswith('#') or line.startswith('>') or line.startswith('---'):
            continue
        if line.startswith('http://') or line.startswith('https://'):
            continue
        if line.startswith('```') or line.startswith('`'):
            continue
        if line.startswith('[[') or line.startswith('!['):  # wiki-link / image
            continue
        if line.startswith('- ') or line.startswith('* '):  # 列表项通常不是描述
            continue
        if re.match(r'^[\d]+[.)]\s', line):  # 编号列表
            continue
        purpose = line[:60].rstrip('。，,.')
        break
    if purpose:
        part1 = f"{title}：{type_desc}，{purpose}。"
    else:
        part1 = f"{title}：{type_desc}。"

    # 第二段：关键词
    kw_str = '、'.join(keywords[:8]) if keywords else '待补充'
    part2 = f"关键词：{kw_str}"

    # 第三段：适用场景
    scenario = TYPE_SCENARIO.get(doc_type, '知识积累与检索')
    part3 = f"适用：{scenario}。"

    return f"{part1}\n{part2}\n{part3}"


def build_frontmatter_block(fm: dict) -> str:
    """Build YAML frontmatter string from dict."""
    lines = ['---']

    # 字段顺序：id, title, type, tags, keywords, summary, entities, related, created, updated
    field_order = ['id', 'title', 'type', 'tags', 'keywords', 'summary',
                   'entities', 'related', 'created', 'updated']

    written_keys = set()
    for key in field_order:
        if key in fm:
            _write_field(lines, key, fm[key])
            written_keys.add(key)

    # 其他字段按原顺序
    for key, value in fm.items():
        if key not in written_keys:
            _write_field(lines, key, value)

    lines.append('---')
    return '\n'.join(lines) + '\n'


def _write_field(lines: list, key: str, value):
    """Write a single frontmatter field."""
    if isinstance(value, list):
        if not value:
            lines.append(f'{key}: []')
        else:
            items = ', '.join(str(v) for v in value)
            lines.append(f'{key}: [{items}]')
    elif '\n' in str(value):
        lines.append(f'{key}: |')
        for vline in str(value).split('\n'):
            lines.append(f'  {vline}')
    else:
        lines.append(f'{key}: {value}')


def process_file(file_path: Path, counter_map: dict, dry_run: bool = True, verbose: bool = False) -> dict:
    """Process a single file. Returns stats dict."""
    stats = {'path': str(file_path), 'added': [], 'skipped': [], 'modified': False}

    content = read_text_safe(file_path)
    if not content.strip():
        stats['skipped'].append('空文件')
        return stats

    fm, fm_start, fm_end, lines = parse_frontmatter(content)
    title = fm.get('title', '') or file_path.stem
    doc_type = fm.get('type', '') if isinstance(fm.get('type', ''), str) else ''
    tags = fm.get('tags', []) if isinstance(fm.get('tags', []), list) else []

    # 检查需要补充的字段
    needs_id = not fm.get('id')
    needs_keywords = not fm.get('keywords') or (isinstance(fm.get('keywords'), list) and len(fm['keywords']) == 0)
    needs_summary = not fm.get('summary') or (isinstance(fm.get('summary'), str) and fm['summary'].strip() == '')
    needs_updated = not fm.get('updated')

    if not any([needs_id, needs_keywords, needs_summary, needs_updated]):
        stats['skipped'].append('字段已完整')
        return stats

    # 生成缺失字段
    if needs_id:
        fm['id'] = generate_id(file_path, counter_map)
        stats['added'].append('id')

    if needs_keywords:
        keywords = extract_keywords(title, content)
        fm['keywords'] = keywords
        stats['added'].append(f'keywords({len(keywords)})')

    if needs_summary:
        kw = fm.get('keywords', [])
        if not isinstance(kw, list):
            kw = []
        summary = generate_summary(title, doc_type, kw, content)
        fm['summary'] = summary
        stats['added'].append('summary')

    if needs_updated:
        # 优先用 modified 字段（旧格式），否则用文件修改时间
        existing_modified = fm.get('modified', '')
        if existing_modified:
            fm['updated'] = str(existing_modified)
        else:
            try:
                mtime = os.path.getmtime(file_path)
                fm['updated'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
            except Exception:
                fm['updated'] = datetime.now().strftime('%Y-%m-%d')
        stats['added'].append('updated')

    if dry_run:
        if verbose:
            print(f"  [DRY] {file_path.name}")
            for a in stats['added']:
                print(f"    + {a}")
        return stats

    # 写入文件
    new_fm_block = build_frontmatter_block(fm)
    if fm_start >= 0 and fm_end >= 0:
        # 替换已有 frontmatter
        before = ''.join(lines[:fm_start])
        after = ''.join(lines[fm_end + 1:])
        new_content = before + new_fm_block + after
    else:
        # 新建 frontmatter
        new_content = new_fm_block + '\n' + content

    try:
        file_path.write_text(new_content, encoding='utf-8')
        stats['modified'] = True
    except Exception as e:
        stats['skipped'].append(f'写入失败: {e}')

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LD-DVA Final Frontmatter 批量补全")
    parser.add_argument('--apply', action='store_true', help='实际执行修改（默认为 dry-run）')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    ns = parser.parse_args()

    dry_run = not ns.apply
    vault = VAULT_ROOT

    print(f"{'[DRY-RUN] ' if dry_run else ''}开始 Frontmatter 批量补全...")
    print(f"  Vault: {vault}")

    files = collect_files(vault)
    print(f"  扫描到 {len(files)} 个知识文件\n")

    counter_map = {}  # 用于生成唯一 ID
    total_added = defaultdict(int)
    total_skipped = 0
    total_modified = 0
    errors = []

    for fp in sorted(files):
        stats = process_file(fp, counter_map, dry_run=dry_run, verbose=ns.verbose)
        if stats['skipped'] and '字段已完整' in stats['skipped']:
            total_skipped += 1
            continue
        if stats['skipped'] and '空文件' in stats['skipped']:
            continue
        for a in stats['added']:
            key = a.split('(')[0]
            total_added[key] += 1
        if stats.get('modified'):
            total_modified += 1
        if dry_run and ns.verbose:
            pass  # 已在 process_file 中输出
        elif not dry_run and stats.get('modified') and ns.verbose:
            print(f"  ✅ {fp.name}: +{', '.join(stats['added'])}")

        # 收集错误
        for s in stats.get('skipped', []):
            if '失败' in s:
                errors.append(f"{fp.name}: {s}")

    # 汇总
    print(f"\n{'=' * 50}")
    print(f"{'[DRY-RUN] ' if dry_run else ''}补全结果汇总")
    print(f"{'=' * 50}")
    print(f"  总文件数: {len(files)}")
    print(f"  已完整（跳过）: {total_skipped}")
    print(f"  补充字段:")
    for key, count in sorted(total_added.items()):
        print(f"    {key}: {count} 个文件")
    if not dry_run:
        print(f"  实际修改文件: {total_modified}")
    else:
        will_modify = len(files) - total_skipped if sum(total_added.values()) > 0 else 0
        print(f"  将修改文件: {will_modify}")
    if errors:
        print(f"  错误: {len(errors)}")
        for e in errors[:5]:
            print(f"    ❌ {e}")
    print(f"{'=' * 50}")

    if dry_run:
        print(f"\n这是 dry-run 模式。确认无误后加 --apply 实际执行。")


if __name__ == "__main__":
    main()

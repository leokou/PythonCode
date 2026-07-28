#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量给所有md文件加 created/modified 字段
对无frontmatter的文件，根据文件名智能判断type并添加frontmatter
"""

import subprocess
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in __import__('sys').path:
    __import__('sys').path.insert(0, str(SCRIPT_DIR))

from obsidian_common import VAULT_ROOT, SKIP_DIRS, should_skip_dir

SKIP_PREFIXES = ("🧩 目录-", "🏠 home-", "📖", "⚓", "🤖")
SKIP_EXACT = {"CLAUDE.md", "README.md"}


def get_git_times(filepath: Path, vault: Path) -> tuple:
    """用git log获取文件的创建时间和修改时间"""
    rel = str(filepath.relative_to(vault)).replace('\\', '/')
    try:
        # 创建时间：最早的commit
        result = subprocess.run(
            ['git', 'log', '--diff-filter=A', '--follow', '--format=%ai', '--', rel],
            capture_output=True, text=True, cwd=str(vault)
        )
        created = result.stdout.strip().split('\n')[-1].strip() if result.stdout.strip() else None

        # 修改时间：最新的commit
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ai', '--', rel],
            capture_output=True, text=True, cwd=str(vault)
        )
        modified = result.stdout.strip() if result.stdout.strip() else None

        # 转换为 YYYY-MM-DD 格式
        if created:
            created = created[:10]
        if modified:
            modified = modified[:10]
    except Exception:
        created = None
        modified = None

    return created, modified


def guess_type(filename: str, content: str) -> str:
    """根据文件名和内容智能判断type"""
    name_lower = filename.lower()
    content_lower = content[:500].lower()

    # 项目文档
    if any(kw in name_lower for kw in ['业委会', '投票系统', '租赁', '纠纷', '项目', '方案']):
        return 'project'
    if '## 📌 一句话总结' in content and any(kw in content_lower for kw in ['项目', '方案', '流程']):
        return 'project'

    # Q&A / 咨询
    if any(kw in name_lower for kw in ['咨询', '问答', '问题', 'qna', '面试']):
        return 'qna'
    if '### Q' in content or '## 🧠 核心问题' in content:
        return 'qna'

    # 工具/配置
    if any(kw in name_lower for kw in ['安装', '配置', '教程', '工具', '命令', 'setup', 'config', '部署']):
        return 'tool'
    if any(kw in content_lower for kw in ['安装步骤', '配置方法', '命令行', 'wrangler', 'npm ']):
        return 'tool'

    # 知识/教程
    if any(kw in name_lower for kw in ['教程', '指南', '速查', '对比', '知识', '评估']):
        return 'knowledge'

    # 账号信息
    if any(kw in name_lower for kw in ['账号', 'account', '密码', '登录']):
        return 'account'

    # 默认
    return 'knowledge'


def guess_tags(filename: str, content: str, filepath: Path) -> list:
    """根据文件路径和内容智能判断tags"""
    tags = []
    name = filepath.stem
    path_parts = filepath.parts

    # 从路径提取领域标签
    for part in path_parts:
        if part.startswith('0- '):
            tags.append('个人')
        elif part.startswith('1- '):
            tags.append('AI')
        elif part.startswith('2- '):
            tags.append('开发')
        elif part.startswith('3- '):
            tags.append('系统')
        elif part.startswith('4- '):
            tags.append('软件')
        elif part.startswith('5- '):
            tags.append('项目')

    # 从文件名提取关键词
    if '业委会' in name:
        tags.extend(['业委会', '筹备组'])
    if '投票' in name:
        tags.extend(['投票系统', 'Cloudflare'])
    if '租赁' in name or '纠纷' in name:
        tags.append('法律')
    if '翻墙' in name or 'CF' in name or 'proxy' in name.lower():
        tags.append('翻墙')
    if 'Obsidian' in name:
        tags.append('Obsidian')
    if 'Python' in name:
        tags.append('Python')
    if 'Vue' in name:
        tags.append('Vue')
    if 'AI' in name or 'Claude' in name or 'GPT' in name:
        tags.append('AI')

    # 去重
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)

    return result[:5]  # 最多5个标签


def process_file(filepath: Path, vault: Path) -> str:
    """处理单个文件，返回操作类型"""
    content = filepath.read_text(encoding='utf-8-sig')
    lines = content.split('\n')

    # 获取git时间
    created, modified = get_git_times(filepath, vault)
    if not created:
        created = datetime.now().strftime('%Y-%m-%d')
    if not modified:
        modified = created

    # 检查是否有标准frontmatter
    has_fm = lines and lines[0].strip() == '---'

    if has_fm:
        # 找FM结束位置
        fm_end = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                fm_end = i
                break
        if fm_end == -1:
            return 'skip'

        fm_body = lines[1:fm_end]
        after = lines[fm_end + 1:]

        # 检查是否已有created/modified
        has_created = any(line.strip().startswith('created:') for line in fm_body)
        has_modified = any(line.strip().startswith('modified:') for line in fm_body)

        if has_created and has_modified:
            return 'skip'  # 已有，跳过

        # 添加缺失的字段
        new_fm_body = list(fm_body)
        if not has_created:
            new_fm_body.append(f'created: {created}')
        if not has_modified:
            new_fm_body.append(f'modified: {modified}')

        new_lines = ['---'] + new_fm_body + ['---'] + after
        new_content = '\n'.join(new_lines).rstrip() + '\n'
        filepath.write_text(new_content, encoding='utf-8')
        return 'updated'

    else:
        # 无frontmatter，智能创建
        file_type = guess_type(filepath.name, content)
        tags = guess_tags(filepath.name, content, filepath)

        fm_lines = [f'type: {file_type}']
        if tags:
            fm_lines.append(f'tags: [{", ".join(tags)}]')
        fm_lines.append(f'created: {created}')
        fm_lines.append(f'modified: {modified}')

        fm_text = '\n'.join(['---'] + fm_lines + ['---'])
        body = content.strip()
        new_content = fm_text + '\n\n' + body + '\n' if body else fm_text + '\n'
        filepath.write_text(new_content, encoding='utf-8')
        return 'created'


def main():
    skip_dirs_set = set()
    stats = {'updated': 0, 'created': 0, 'skip': 0}

    files = []
    for f in VAULT_ROOT.rglob('*.md'):
        rel = f.relative_to(VAULT_ROOT)
        if any(should_skip_dir(part) for part in rel.parts[:-1]):
            continue
        if f.name in SKIP_EXACT or any(f.name.startswith(p) for p in SKIP_PREFIXES):
            continue
        files.append(f)

    total = len(files)
    for i, f in enumerate(sorted(files)):
        result = process_file(f, VAULT_ROOT)
        stats[result] += 1
        if result != 'skip':
            print(f'  [{result}] {f.relative_to(VAULT_ROOT)}')

    print(f'\n总计: {total}')
    print(f'  更新(加时间): {stats["updated"]}')
    print(f'  新建(智能FM): {stats["created"]}')
    print(f'  跳过(已有): {stats["skip"]}')


if __name__ == '__main__':
    main()

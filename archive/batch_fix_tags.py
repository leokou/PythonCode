#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能修正所有md文件的type和tags
读取文件内容（前1000字）进行智能判断，确保每个文件至少3个标签
"""

import re
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in __import__('sys').path:
    __import__('sys').path.insert(0, str(SCRIPT_DIR))

from obsidian_common import VAULT_ROOT, should_skip_dir

SKIP_PREFIXES = ("🧩 目录-", "🏠 home-", "📖", "⚓", "🤖")
SKIP_EXACT = {"CLAUDE.md", "README.md"}

# type关键词映射（按优先级）
TYPE_RULES = [
    ('project', ['业委会', '投票系统', '租赁', '纠纷', '再审', '起诉', '答辩', '传票', '证据', '庭审', '立案', '判决', '法院', '方案', '项目文档', '筹备组', '物业沟通']),
    ('qna', ['咨询', '问答', '面试', '问题清单', '### Q', '## 🧠 核心问题']),
    ('tool', ['安装', '配置', '部署', '命令', '教程', 'setup', 'wrangler', 'npm ', 'pip ', '快捷键', '脚本', '工具', '插件', 'CLI', 'API', '搭建', '使用指南', '操作']),
    ('account', ['账号', '密码', 'Apple ID', 'Shadowrocket']),
    ('knowledge', ['知识', '评估', '对比', '速查', '指南', '路线', '作品全集', '电影', '影视', '解读', '汇总', '清单', '规范']),
]

# 标签关键词库
TAG_KEYWORDS = {
    # 领域
    'AI': ['AI', 'Claude', 'GPT', 'Gemini', 'Copilot', 'Codex', 'DeepSeek', '大模型', 'AI编程', '智能体', 'MCP', 'Token'],
    'Obsidian': ['Obsidian', '笔记', '双链', 'frontmatter', '目录索引', 'Skill'],
    'Python': ['Python', 'pip', 'pyinstaller', 'django', 'flask'],
    'Vue': ['Vue', 'Vue3', 'Ant Design', 'Hono'],
    'Cloudflare': ['Cloudflare', 'Workers', 'D1', 'R2', 'Pages', 'wrangler', 'CDN'],
    '开发': ['代码', '编程', '架构', '前端', '后端', 'API', '数据库', 'SQL', 'HTML', 'JS', 'CSS', 'HTTP'],
    '系统': ['Windows', 'Win11', 'iOS', 'iPhone', 'Mac', 'Linux', 'WSL', '注册表', '系统备份'],
    '翻墙': ['翻墙', '代理', 'VPN', 'v2ray', 'Shadowrocket', '节点', '订阅', 'CF翻墙', 'TLS', 'REALITY'],
    '软件': ['AutoHotkey', 'VSCode', 'Chrome', 'PicGo', 'ShareX', 'PowerToys', 'OneNote', 'Notability'],
    '业委会': ['业委会', '筹备组', '业主', '楼栋', '物业', '街道', '住建局', '投票', '招募'],
    '法律': ['租赁', '纠纷', '法院', '起诉', '答辩', '再审', '传票', '证据', '判决', '合同'],
    '影视': ['电影', '影视', '诺兰', '导演', '影评', '作品'],
    '面试': ['面试', '简历', '工作经历', '项目经验', 'TOB'],
    'Docker': ['Docker', '容器', '镜像'],
    'Git': ['Git', 'GitHub', 'commit', 'push', '分支'],
    '图床': ['图床', 'PicGo', 'R2', 'S3', 'CDN'],
}

def guess_type(filename: str, content: str) -> str:
    """根据文件名和内容智能判断type"""
    text = filename + ' ' + content[:1500]
    for type_name, keywords in TYPE_RULES:
        for kw in keywords:
            if kw in text:
                return type_name
    return 'knowledge'

def extract_tags(filename: str, content: str, filepath: Path) -> list:
    """从文件名、内容、路径提取标签"""
    tags = set()
    full_text = filename + '\n' + content[:2000]
    
    # 1. 从关键词库匹配
    for tag, keywords in TAG_KEYWORDS.items():
        for kw in keywords:
            if kw in full_text:
                tags.add(tag)
                break
    
    # 2. 从文件名提取关键词（分割 - @ 等）
    stem = filepath.stem
    parts = re.split(r'\s*[-@]\s*', stem)
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and part not in ['教程', '工具', '指南', '速查', '配置', '安装', '说明']:
            tags.add(part)
    
    # 3. 从路径提取领域
    for part in filepath.parts:
        if part.startswith('0- '):
            tags.add('个人')
        elif part.startswith('1- '):
            tags.add('AI')
        elif part.startswith('2- '):
            tags.add('开发')
        elif part.startswith('3- '):
            tags.add('系统')
        elif part.startswith('4- '):
            tags.add('软件')
        elif part.startswith('5- '):
            # 不再粗暴加"项目"，根据内容判断
            pass
    
    # 4. 从内容标题提取
    for line in content[:1000].split('\n'):
        if line.startswith('## ') and not line.startswith('## 📌'):
            title = line[3:].strip()
            # 提取标题中的关键词
            for tag, keywords in TAG_KEYWORDS.items():
                for kw in keywords:
                    if kw in title:
                        tags.add(tag)
                        break
    
    # 5. 从✍️摘要提取
    summary_match = re.search(r'>✍️\s*(.+)', content[:500])
    if summary_match:
        summary = summary_match.group(1)
        for tag, keywords in TAG_KEYWORDS.items():
            for kw in keywords:
                if kw in summary:
                    tags.add(tag)
                    break
    
    # 过滤太短或无意义的标签
    filtered = [t for t in tags if len(t) >= 2]
    
    # 确保至少3个标签
    if len(filtered) < 3:
        # 从内容中找更多关键词
        for tag, keywords in TAG_KEYWORDS.items():
            if tag not in filtered:
                for kw in keywords:
                    if kw in content[:3000]:
                        filtered.append(tag)
                        break
            if len(filtered) >= 3:
                break
    
    return filtered[:5]

def process_file(filepath: Path) -> bool:
    """处理单个文件，更新type和tags，返回是否修改"""
    content = filepath.read_text(encoding='utf-8-sig')
    lines = content.split('\n')
    
    # 必须有标准frontmatter
    if not lines or lines[0].strip() != '---':
        return False
    
    fm_end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            fm_end = i
            break
    if fm_end == -1:
        return False
    
    fm_body = lines[1:fm_end]
    after = lines[fm_end + 1:]
    
    # 智能判断新的type和tags
    new_type = guess_type(filepath.name, content)
    new_tags = extract_tags(filepath.name, content, filepath)
    
    if not new_tags:
        new_tags = [new_type]
    
    # 重建frontmatter（保留created/modified，替换type/tags）
    new_fm_body = []
    created = None
    modified = None
    source = None
    
    for line in fm_body:
        stripped = line.strip()
        if stripped.startswith('created:'):
            created = line
        elif stripped.startswith('modified:'):
            modified = line
        elif stripped.startswith('source:'):
            source = line
        # 跳过旧的type和tags
    
    new_fm_body.append(f'type: {new_type}')
    new_fm_body.append(f'tags: [{", ".join(new_tags)}]')
    if source:
        new_fm_body.append(source)
    if created:
        new_fm_body.append(created)
    if modified:
        new_fm_body.append(modified)
    
    new_lines = ['---'] + new_fm_body + ['---'] + after
    new_content = '\n'.join(new_lines).rstrip() + '\n'
    
    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
        return True
    return False

def main():
    stats = {'updated': 0, 'skip': 0}
    files = []
    
    for f in VAULT_ROOT.rglob('*.md'):
        rel = f.relative_to(VAULT_ROOT)
        if any(should_skip_dir(part) for part in rel.parts[:-1]):
            continue
        if f.name in SKIP_EXACT or any(f.name.startswith(p) for p in SKIP_PREFIXES):
            continue
        files.append(f)
    
    for f in sorted(files):
        if process_file(f):
            stats['updated'] += 1
        else:
            stats['skip'] += 1
    
    print(f'总计: {len(files)}')
    print(f'  更新: {stats["updated"]}')
    print(f'  跳过: {stats["skip"]}')

if __name__ == '__main__':
    main()

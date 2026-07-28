#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LD-DVA Final Architecture Builder v2
====================================
生成 .ai-index/ 下的紧凑 JSON 索引，支撑轻量智能导航。

核心设计：索引不回答"内容是什么"，只回答"去哪里找"。

命令：
  python ai_index_builder_v2.py rebuild          全量重建
  python ai_index_builder_v2.py incremental      增量更新
  python ai_index_builder_v2.py search <query>   搜索（读 JSON 索引）
  python ai_index_builder_v2.py router <query>   查询路由判定（L1/L2/L3）
  python ai_index_builder_v2.py status           查看状态
  python ai_index_builder_v2.py health           健康检查
  python ai_index_builder_v2.py cache-read <q>   读取模式缓存
  python ai_index_builder_v2.py cache-write <q> <route> 写入模式缓存
"""

import sys
import os
import re
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from obsidian_common import (
    VAULT_ROOT, SKIP_DIRS, should_skip_dir,
    read_text_safe,
)

# ======================================================================
# 内联 frontmatter 解析（obsidian_common 无 parse_frontmatter）
# ======================================================================
def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content. Returns dict of fields."""
    result = {}
    if not content.startswith('---'):
        return result
    # Find the closing ---
    parts = content.split('---', 2)
    if len(parts) < 3:
        return result
    yaml_block = parts[1]
    for line in yaml_block.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            # Remove quotes
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            # Handle list values [a, b, c]
            if val.startswith('[') and val.endswith(']'):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
            if key and val:
                result[key] = val
    return result

# ======================================================================
# 路径配置（新架构：.ai-index/ 隐藏目录）
# ======================================================================
AI_INDEX_ROOT = VAULT_ROOT / ".ai-index"
RUNTIME_DIR = AI_INDEX_ROOT / "runtime"
DOMAIN_DIR = AI_INDEX_ROOT / "domain"
PROTOCOL_DIR = AI_INDEX_ROOT / "protocol"
CACHE_DIR = AI_INDEX_ROOT / "cache"
HEALTH_DIR = AI_INDEX_ROOT / "health" / "reports"

FILES_JSON = RUNTIME_DIR / "files.json"
TAGS_JSON = RUNTIME_DIR / "tags.json"
RELATIONS_JSON = RUNTIME_DIR / "relations.json"
QUERY_MEMORY_JSON = CACHE_DIR / "query-memory.json"
INDEX_STATE_JSON = RUNTIME_DIR / "index-state.json"
AI_READ_PROTOCOL = PROTOCOL_DIR / "AI_READ_PROTOCOL.md"

# ======================================================================
# 同义词映射（保留，用于搜索扩展）
# ======================================================================
SYNONYM_MAP = {
    "VPN": ["翻墙", "代理", "v2ray", "proxy", "Shadowsocks", "SSR", "V2Ray", "Clash"],
    "AI": ["人工智能", "大模型", "LLM", "AI编程", "机器学习", "深度学习", "GPT", "Claude"],
    "部署": ["上线", "发布", "deploy", "安装", "配置", "搭建", "构建"],
    "serverless": ["无服务器", "Serverless", "Serverless Function", "云函数"],
    "workers": ["Workers", "Cloudflare Workers", "cf workers", "边缘计算"],
    "数据库": ["DB", "database", "D1", "SQLite", "MySQL", "PostgreSQL", "Redis"],
    "前端": ["frontend", "UI", "界面", "页面", "视图", "组件"],
    "后端": ["backend", "API", "接口", "服务端", "服务器"],
    "框架": ["framework", "库", "library", "工具集"],
    "教程": ["tutorial", "指南", "guide", "手册", "文档", "说明书"],
    "工具": ["tool", "软件", "应用", "程序", "插件", "扩展"],
    "配置": ["config", "设置", "setup", "环境", "参数"],
    "问题": ["bug", "错误", "故障", "异常", "报错", "issue"],
    "优化": ["改进", "提升", "增强", "加速", "性能", "效率"],
    "开发": ["develop", "编程", "coding", "构建", "编写"],
    "测试": ["test", "验证", "检查", "调试", "排查"],
    "文档": ["doc", "documentation", "说明", "手册", "指南"],
    "版本": ["version", "版", "迭代", "更新", "升级"],
    "接口": ["API", "endpoint", "路由", "路径", "url"],
    "认证": ["auth", "登录", "验证", "token", "权限"],
    "Cloudflare": ["CF", "Workers", "R2", "KV", "D1", "Turnstile", "Cloudflare One"],
    "React": ["React", "React.js", "Hooks", "组件", "JSX"],
    "Python": ["Python", "Flask", "Django", "FastAPI", "脚本", "自动化"],
    "租房": ["租赁", "承租", "房屋租赁", "住房", "居住", "房客", "租户"],
    "注意": ["注意事项", "注意什么", "要点", "细节", "风险", "避免", "小心"],
    "合同": ["协议", "契约", "签署", "签订", "条款", "约定"],
    "法律": ["法规", "条款", "判例", "判决", "诉讼", "维权"],
    "生活": ["日常", "居家", "家庭", "生存", "作息"],
    "金钱": ["费用", "成本", "价格", "预算", "花费", "投资", "理财"],
}

_SYNONYM_REVERSE: Dict[str, List[str]] = {}
for _std, _syns in SYNONYM_MAP.items():
    for _s in _syns:
        _SYNONYM_REVERSE.setdefault(_s.lower(), []).append(_std)

# ======================================================================
# 数据质量过滤
# ======================================================================
_HIGH_QUALITY_TAG_MIN_LEN = 2
_DATE_PATTERN = re.compile(r'^\d{2,4}[.\-/年]\d{1,2}(-\d{1,2})?$')
_PURE_NUMBER_PATTERN = re.compile(r'^\d+$')
_SINGLE_CHAR_PATTERN = re.compile(r'^[\u4e00-\u9fff]$')
_TAG_BLACKLIST = {'年', '月', '日', '个', '期', '次', '种', '类', '项', '件', '上', '下', '中', '里', '外', '内', '前', '后', '间', '时', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'}


def _is_low_quality_tag(tag) -> bool:
    if not tag or not isinstance(tag, str):
        return True
    t = str(tag).strip()
    if not t:
        return True
    if _DATE_PATTERN.match(t) or _PURE_NUMBER_PATTERN.match(t) or _SINGLE_CHAR_PATTERN.match(t):
        return True
    if t.lower() in _TAG_BLACKLIST:
        return True
    return len(t) < _HIGH_QUALITY_TAG_MIN_LEN


def _filter_tags(tags: list) -> list:
    if not isinstance(tags, list):
        return []
    return [str(t).strip() for t in tags if not _is_low_quality_tag(t)]


def _extract_tags_from_frontmatter(fm: dict) -> list:
    """Extract tags from frontmatter, supporting both list and comma-separated string."""
    tags = fm.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    elif not isinstance(tags, list):
        tags = []
    return _filter_tags(tags)


def _infer_type_from_path(path: str) -> str:
    """Infer file type from path prefix (0-8 categories)."""
    parts = Path(path).parts
    for p in parts:
        if p.startswith('0-'): return '个人'
        if p.startswith('1-'): return 'AI'
        if p.startswith('2-'): return '开发'
        if p.startswith('3-'): return '系统'
        if p.startswith('4-'): return '软件'
        if p.startswith('5-'): return '项目'
        if p.startswith('6-'): return '影视'
        if p.startswith('7-'): return '思维框架'
        if p.startswith('8-'): return '核心规则'
    return '未分类'


def _extract_wikilinks(text: str) -> list:
    """Extract [[wikilink]] targets from text."""
    links = re.findall(r'\[\[([^\|\]]+)(?:\|[^\]]+)?\]\]', text)
    return [l.strip() for l in links if l.strip()]


def _extract_backlinks(docs: list) -> Dict[str, list]:
    """Extract backlinks: for each file, which other files link TO it."""
    backlinks: Dict[str, list] = {}
    for doc in docs:
        title = doc.get('title', '')
        path = doc.get('path', '')
        links = doc.get('_wikilinks', [])
        for link_target in links:
            backlinks.setdefault(link_target, []).append(title or path)
    return backlinks


# ======================================================================
# 扫描与索引构建
# ======================================================================
def scan_files() -> list:
    """Scan all knowledge files and return document list."""
    docs = []
    all_md_files = list(VAULT_ROOT.rglob("*.md"))
    for fpath in all_md_files:
        fstr = str(fpath)
        # Skip .ai-index, _trash, skills, logs
        if '.ai-index' in fstr or '_trash' in fstr or 'skills' in fstr or 'logs' in fstr:
            continue
        if should_skip_dir(fpath.parent.name):
            continue

        try:
            text = read_text_safe(fpath)
            fm = _parse_frontmatter(text)
            rel_path = str(fpath.relative_to(VAULT_ROOT)).replace('\\', '/')
            file_name = fpath.stem

            title = fm.get('title', file_name) or file_name
            tags = _extract_tags_from_frontmatter(fm)
            updated = fm.get('updated', '') or datetime.fromtimestamp(fpath.stat().st_mtime).strftime('%Y-%m-%d')
            status = fm.get('status', 'active')
            ftype = fm.get('type', '') or _infer_type_from_path(rel_path)
            wikilinks = _extract_wikilinks(text)

            doc = {
                'id': hashlib.md5(rel_path.encode()).hexdigest()[:8],
                'title': str(title),
                'path': rel_path,
                'type': str(ftype),
                'tags': tags[:10],  # Cap at 10 tags
                'updated': str(updated),
                'status': str(status),
                '_wikilinks': wikilinks,
                '_hash': hashlib.md5(text.encode('utf-8')).hexdigest(),
            }
            docs.append(doc)
        except Exception as e:
            print(f"  ⚠️  跳过 {fpath}: {e}")
    return docs


def build_files_json(docs: list) -> list:
    """Build runtime/files.json — search-only, ultra-compact (p→t mapping)."""
    result = []
    for d in docs:
        if d.get('status') == 'trash':
            continue
        entry = {
            'i': d['id'],
            't': d['title'],
            'p': d['path'],
            'y': d['type'][:2] if d['type'] else '',
        }
        result.append(entry)
    return sorted(result, key=lambda x: x['t'].lower())


def build_tags_json(docs: list, max_tags: int = 60, max_files_per_tag: int = 3) -> dict:
    """Build runtime/tags.json — top N tags, 3 files max per tag."""
    tag_map: Dict[str, List[str]] = {}
    for d in docs:
        if d.get('status') == 'trash':
            continue
        for tag in d['tags']:
            tag_map.setdefault(tag, []).append(d['path'])

    sorted_tags = sorted(tag_map.items(), key=lambda x: len(x[1]), reverse=True)[:max_tags]
    result = {}
    for tag, files in sorted_tags:
        result[tag] = sorted(files)[:max_files_per_tag]
    return result


def build_relations_json(docs: list, max_relations_per_file: int = 1, min_common_tags: int = 3) -> dict:
    """Build runtime/relations.json — only wikilinks + very strict tag intersections."""
    relations: Dict[str, list] = {}

    # Source 1: wikilinks only (explicit)
    for d in docs:
        title = d['title']
        for link in d.get('_wikilinks', []):
            for d2 in docs:
                if d2['title'] == link and d2['title'] != title:
                    rels = relations.get(title, [])
                    if link not in rels and len(rels) < max_relations_per_file:
                        rels.append(link)
                        relations[title] = rels
                    break

    # Source 2: tag intersections (4+ common, tiny window)
    for i, d1 in enumerate(docs):
        if d1.get('status') == 'trash':
            continue
        tags1 = set(d1['tags'])
        if len(tags1) < min_common_tags:
            continue
        t1 = d1['title']
        rels1 = relations.get(t1, [])
        if len(rels1) >= max_relations_per_file:
            continue
        for j in range(i + 1, min(i + 10, len(docs))):
            d2 = docs[j]
            if d2.get('status') == 'trash':
                continue
            tags2 = set(d2['tags'])
            if len(tags1 & tags2) >= min_common_tags:
                t2 = d2['title']
                if t2 not in rels1 and len(rels1) < max_relations_per_file:
                    rels1.append(t2)
                    relations[t1] = rels1
                rels2 = relations.get(t2, [])
                if t1 not in rels2 and len(rels2) < max_relations_per_file:
                    rels2.append(t1)
                    relations[t2] = rels2

    for k in relations:
        relations[k] = sorted(relations[k])
    return dict(sorted(relations.items()))


def build_domain_files(docs: list) -> Dict[str, str]:
    """Build domain/*.md files — lightweight domain navigation indexes."""
    domains = {
        'root-index.md': {'title': 'root-index', 'keywords': []},
        'ai.md': {'title': '🤖 AI', 'keywords': ['AI', 'ai', '人工智能', 'LLM']},
        'dev.md': {'title': '💻 开发', 'keywords': ['开发', 'develop', '编程', 'framework']},
        'system.md': {'title': '🪟 系统', 'keywords': ['系统', 'system', 'OS']},
        'project.md': {'title': '🧁 项目', 'keywords': ['项目', 'project']},
        'life.md': {'title': '🙎 个人', 'keywords': ['个人', '生活', 'life']},
        'thinking.md': {'title': '🧠 思维', 'keywords': ['思维', '思维模型', '框架', '分析', '思考', '第一性原理', 'MECE', 'SWOT', '金字塔', '决策', '系统思考']},
    }

    result = {}
    for fname, domain_info in domains.items():
        domain_title = domain_info['title']
        keywords = domain_info['keywords']
        content_lines = [f"# {domain_title} 领域导航\n"]

        if fname == 'root-index.md':
            content_lines.append("## 可用领域")
            content_lines.append("- 🤖 AI相关：工具、API、模型、Agent")
            content_lines.append("- 💻 开发：编程语言、框架、架构")
            content_lines.append("- 🪟 系统：操作系统、网络、硬件")
            content_lines.append("- 🧁 项目：个人项目、工作项目")
            content_lines.append("- 🙎 个人：生活、个人知识")
            content_lines.append("- 🧠 思维：思维框架、决策模型、分析方法\n")
            content_lines.append("## AI 读取规则")
            content_lines.append("请先阅读 `protocol/AI_READ_PROTOCOL.md`。")
            content_lines.append("除非复杂分析，否则禁止加载 runtime/ 下的所有 JSON 文件。")
        else:
            content_lines.append(f"## 核心工具/概念\n")
            # Find matching docs
            matched = []
            for d in docs:
                if d.get('status') == 'trash':
                    continue
                text = (d['title'] + ' ' + ' '.join(d.get('tags', ''))).lower()
                for kw in keywords:
                    if kw.lower() in text:
                        matched.append(d)
                        break
            # Group by type
            type_groups: Dict[str, list] = {}
            for m in matched[:30]:
                t = m.get('type', '未分类')
                type_groups.setdefault(t, []).append(m)

            for t, items in sorted(type_groups.items()):
                content_lines.append(f"### {t}\n")
                for item in items[:15]:
                    content_lines.append(f"- **{item['title']}**: `{item['path']}`")
                content_lines.append("")

        result[fname] = '\n'.join(content_lines)
    return result


# ======================================================================
# 搜索与路由
# ======================================================================
def load_index() -> dict:
    """Load all JSON index files."""
    data = {
        'files': [],
        'tags': {},
        'relations': {},
    }
    try:
        if FILES_JSON.exists():
            data['files'] = json.loads(FILES_JSON.read_text(encoding='utf-8'))
    except Exception:
        pass
    try:
        if TAGS_JSON.exists():
            data['tags'] = json.loads(TAGS_JSON.read_text(encoding='utf-8'))
    except Exception:
        pass
    try:
        if RELATIONS_JSON.exists():
            data['relations'] = json.loads(RELATIONS_JSON.read_text(encoding='utf-8'))
    except Exception:
        pass
    return data


def expand_query_terms(query: str) -> list:
    """Expand query with synonyms and smart Chinese word segmentation."""
    terms = [query.lower().strip()]
    q_lower = query.lower()

    # Smart Chinese word extraction: extract meaningful substrings
    # 2-char windows from Chinese text
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', query)
    for segment in chinese_chars:
        # Add the full segment
        if segment not in terms:
            terms.append(segment)
        # Add 2-char substrings for better matching
        for i in range(len(segment) - 1):
            sub = segment[i:i+2]
            if sub not in terms:
                terms.append(sub)

    # Split query into words (mixed Chinese/English)
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+', q_lower)
    for w in words:
        w_lower = w.lower()
        if len(w_lower) < 1:
            continue
        # Always add the word itself to terms (essential for entity matching)
        if w_lower not in terms:
            terms.append(w_lower)
        # Direct synonym lookup (reverse)
        if w_lower in _SYNONYM_REVERSE:
            for std in _SYNONYM_REVERSE[w_lower]:
                if std.lower() not in terms:
                    terms.append(std.lower())
        # Standard → expand
        if w_lower in SYNONYM_MAP:
            for syn in SYNONYM_MAP[w_lower]:
                if syn.lower() not in terms:
                    terms.append(syn.lower())

    # Also try the 2-char substrings against synonym reverse
    expanded = []
    for t in terms:
        if t in _SYNONYM_REVERSE:
            for std in _SYNONYM_REVERSE[t]:
                if std.lower() not in terms and std.lower() not in expanded:
                    expanded.append(std.lower())
        if t in SYNONYM_MAP:
            for syn in SYNONYM_MAP[t]:
                if syn.lower() not in terms and syn.lower() not in expanded:
                    expanded.append(syn.lower())
    terms.extend(expanded)

    return list(set(terms))


# Low-value generic terms that should NOT dominate scoring
_GENERIC_TERMS = {'ai', 'api', '配置', '方法', '怎么', '如何', '设置', '教程',
                  '工具', '相关', '资料', '学习', '模块', '能力', '是什么',
                  '有什么', '哪些', 'about', 'the', 'a', 'an', 'to', 'for',
                  '配置', 'config', 'setup', 'install', '使用', '用', '介绍'}

# Known product/tool entities that should get high priority
_KNOWN_ENTITIES = [
    'trae', 'claude', 'cursor', 'codex', 'copilot', 'codebuddy',
    'cherry studio', 'cherry', 'opencode', 'openwork', ' Agnes ', 'agnes',
    'deepseek', 'gemini', 'groq', 'openrouter', 'nvidia', 'cloudflare',
    'mcp', 'agent', 'skill', 'rag', '向量', '数据库',
    'shadowrocket', 'v2ray', 'clash', 'surge',
    'obsidian', 'vue3', 'hono', 'cloudflare workers', 'workers',
    'python', 'javascript', 'typescript', 'node', 'react',
    'wordpress', 'docker', 'wsl', 'windows', 'ios',
    'mece', 'swot', '金字塔', '一阶', '二阶', '5 whys', '5why',
    '业委会', '租房', ' ballot', '投票',
]

def _extract_entities(query: str) -> list:
    """Extract high-value entity terms from query."""
    q_lower = query.lower()
    entities = []
    # Check multi-word entities first
    for entity in _KNOWN_ENTITIES:
        if entity.lower() in q_lower:
            entities.append(entity.lower())
    # Also extract capitalized English words as potential entities
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9]{2,}', query)
    for w in words:
        w_lower = w.lower()
        if w_lower not in _GENERIC_TERMS and w_lower not in entities:
            entities.append(w_lower)
    # Extract quoted or emphasized terms
    for pattern in [r'「(.+?)」', r'"(.+?)"', r"'(.+?)'"]:
        matches = re.findall(pattern, query)
        for m in matches:
            if m.lower() not in _GENERIC_TERMS and m.lower() not in entities:
                entities.append(m.lower())
    return entities

def _is_generic_term(term: str) -> bool:
    """Check if a term is too generic to be used for ENTITY FILTERING.
    
    Generic terms still contribute to scoring, they just don't trigger
    the aggressive entity-based filtering.
    """
    return term.lower() in _GENERIC_TERMS or len(term.strip()) <= 1

def search(query: str, top_n: int = 5) -> list:
    """Search using JSON index with entity-aware scoring.
    
    Key design:
    1. Entity terms (product names) get 10x weight vs generic terms
    2. Files that DON'T match entity terms are filtered OUT when entities exist
    3. Path-based boost: same directory category gets +5
    4. Generic terms (AI, API, 配置) get minimal weight
    """
    index = load_index()
    if not index['files']:
        return []

    entities = _extract_entities(query)
    terms = expand_query_terms(query)
    
    # All expanded terms contribute to scoring (including generic ones)
    # Generic terms are only excluded from entity FILTERING, not scoring
    scoring_terms = terms
    
    scores: Dict[str, dict] = {}
    
    # === PHASE 1: Entity matching (highest priority) ===
    if entities:
        for entity in entities:
            entity_lower = entity.lower()
            for f in index['files']:
                title_lower = f.get('t', '').lower()
                path_lower = f.get('p', '').lower()
                
                # Exact entity in title: +50
                if entity_lower == title_lower:
                    scores.setdefault(f['i'], {'file': f, 'score': 0})
                    scores[f['i']]['score'] += 50
                # Entity as word boundary in title: +30
                elif re.search(rf'\b{re.escape(entity_lower)}\b', title_lower):
                    scores.setdefault(f['i'], {'file': f, 'score': 0})
                    scores[f['i']]['score'] += 30
                # Entity substring in title: +20
                elif entity_lower in title_lower:
                    scores.setdefault(f['i'], {'file': f, 'score': 0})
                    scores[f['i']]['score'] += 20
                # Entity in path: +10
                elif entity_lower in path_lower:
                    scores.setdefault(f['i'], {'file': f, 'score': 0})
                    scores[f['i']]['score'] += 10

    # === PHASE 2: Content term matching ===
    for term in scoring_terms:
        term_lower = term.lower()
        
        # Title exact match: +10
        for f in index['files']:
            title_lower = f.get('t', '').lower()
            if term_lower == title_lower:
                scores.setdefault(f['i'], {'file': f, 'score': 0})
                scores[f['i']]['score'] += 10
            # Title partial match: +5
            elif term_lower in title_lower:
                scores.setdefault(f['i'], {'file': f, 'score': 0})
                scores[f['i']]['score'] += 5

        # Tag match: +8
        tag_files = index['tags'].get(term, [])
        for path in tag_files:
            for f in index['files']:
                if f.get('p') == path:
                    scores.setdefault(f['i'], {'file': f, 'score': 0})
                    scores[f['i']]['score'] += 8

        # Path match: +3
        for f in index['files']:
            if term_lower in f.get('p', '').lower():
                scores.setdefault(f['i'], {'file': f, 'score': 0})
                scores[f['i']]['score'] += 3

    # === PHASE 3: Filter and boost ===
    # If specific (non-generic) entities exist, prefer files that contain them
    specific_entities = [e for e in entities if not _is_generic_term(e)]
    if specific_entities and scores:
        filtered = {}
        for fid, data in scores.items():
            f = data['file']
            title_lower = f.get('t', '').lower()
            path_lower = f.get('p', '').lower()
            has_entity = any(
                e.lower() in title_lower or e.lower() in path_lower
                for e in specific_entities
            )
            if has_entity:
                filtered[fid] = data
            # Keep files with very high scores from non-entity matches
            elif data['score'] >= 15:
                filtered[fid] = data
        scores = filtered

    # Sort by score
    results = sorted(scores.values(), key=lambda x: x['score'], reverse=True)
    # Convert back to friendly format
    friendly = []
    for r in results[:top_n]:
        f = r['file']
        friendly.append({
            'id': f.get('i', ''),
            'title': f.get('t', ''),
            'path': f.get('p', ''),
            'score': r['score'],
        })
    
    return friendly


def classify_query(query: str) -> dict:
    """Classify query into L1/L2/L3 level with honest routing paths."""
    q = query.strip()

    # Suggest relevant domain
    suggested_domain = _suggest_domain(q)

    # L3: 复杂分析（跨领域总结、对比、趋势分析、体系分析、根因分析）
    l3_patterns = ['分析', '对比', '总结', '体系', '架构', '趋势', '综合', '全面', '设计',
                   '完整性', '是否完整', '缺少', '根源', '剖析', '为什么', '原因',
                   '是否值得', '利弊', '优劣', '差异', '关系', '定位', '分工', '路线',
                   '扩展性', '扩展到', '未来', '长期', '五年', '演进',
                   '相比', '对比', '优势', '不足', '劣势']
    for p in l3_patterns:
        if p in q:
            return {'level': 'L3', 'label': '复杂分析',
                    'path': f'domain索引({suggested_domain}) → runtime(tags+relations) → 多文件 → 总结',
                    'tokens': '< 5000', 'domain': suggested_domain}

    # L2: 精确查询（配置、步骤、具体方法、行动意图、查找资料、解决问题）
    l2_patterns = ['怎么', '如何', '配置', '设置', '步骤', '方法', '教程', '安装', '搭建', '部署',
                   '注意', '技巧', '须知', '要点', '注意事项', '怎么办', '做', '流程', '攻略', '指南',
                   '资料', '学习', '模块', '能力', '分别', '哪些', '是什么', '有什么',
                   '查找', '查找一下', '搜索', '找到', '定位', '整理', '总结一下',
                   '效率', '消耗', '过大', '问题', '解决', '方案', '优化',
                   '引入', '是否需要', '要不要', 'RAG', '向量', '数据库',
                   '优先级', '安排', '规划', '选择', '方向', '落地方向',
                   '封装', '商用', '产品', '投入', '精力', '开发',
                   '知识', '设计方案', '重要', '核心', '关键']
    for p in l2_patterns:
        if p in q:
            return {'level': 'L2', 'label': '精确主题查询',
                    'path': f'domain索引({suggested_domain}) → runtime搜索 → 定位文件 → 读正文',
                    'tokens': '< 2500', 'domain': suggested_domain}

    # L1: 简单事实查询
    return {'level': 'L1', 'label': '简单事实查询',
            'path': f'domain索引({suggested_domain}) → runtime精确搜索 → 读正文',
            'tokens': '< 2000', 'domain': suggested_domain}


def _suggest_domain(query: str) -> str:
    """Suggest which domain index is most relevant for a query."""
    q_lower = query.lower()
    domain_map = [
        ('🧠 思维', ['思维', '思考', '分析', '框架', '模型', '决策', '原理', '第一性', 'MECE', 'SWOT', '金字塔', '系统思考', '二阶思维', '逻辑']),
        ('🤖 AI', ['ai', '人工智能', '大模型', 'llm', 'ai编程', 'agent', '机器学习', '深度学习', 'gpt', 'claude', '模型']),
        ('💻 开发', ['开发', '编程', '代码', 'python', 'javascript', 'vue', 'react', '框架', 'api', '数据库', 'server', 'workers']),
        ('🪟 系统', ['系统', 'windows', 'linux', 'mac', '网络', 'os', '操作系统', '硬件', '软件配置']),
        ('🧁 项目', ['项目', 'project', '案件', '法律', '合同', '庭审', '诉讼', '投票', '业委会']),
        ('🙎 个人', ['生活', '租房', '美食', '旅行', '运动', '健康', '家庭', '居家', '个人', '工作', '面试']),
    ]
    best_domain = '综合'
    best_score = 0
    for domain, keywords in domain_map:
        score = sum(1 for kw in keywords if kw.lower() in q_lower)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain


# ======================================================================
# 命令实现
# ======================================================================
def cmd_rebuild():
    """Full rebuild of all JSON indexes."""
    print("🔍 扫描知识库文件...")
    docs = scan_files()
    print(f"   发现 {len(docs)} 个知识文件")

    print("📦 生成 runtime/files.json...")
    files_data = build_files_json(docs)
    FILES_JSON.write_text(json.dumps(files_data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    files_size = FILES_JSON.stat().st_size
    print(f"   {len(files_data)} 文件, {files_size} bytes (紧凑格式)")

    print("🏷️  生成 runtime/tags.json...")
    tags_data = build_tags_json(docs)
    TAGS_JSON.write_text(json.dumps(tags_data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tags_size = TAGS_JSON.stat().st_size
    print(f"   {len(tags_data)} 标签, {tags_size} bytes (紧凑格式)")

    print("🔗 生成 runtime/relations.json...")
    rels_data = build_relations_json(docs)
    RELATIONS_JSON.write_text(json.dumps(rels_data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    rels_size = RELATIONS_JSON.stat().st_size
    print(f"   {len(rels_data)} 关系, {rels_size} bytes (紧凑格式)")

    total_size = files_size + tags_size + rels_size
    core_size = tags_size + rels_size
    print(f"\n📊 核心索引 (tags+rels): {core_size} bytes ({core_size/1024:.1f} KB) {'✅' if core_size <= 40*1024 else '⚠️'}")
    print(f"📊 搜索辅助 (files):   {files_size} bytes ({files_size/1024:.1f} KB)")
    print(f"📊 索引总计:           {total_size} bytes ({total_size/1024:.1f} KB)")

    # Build state
    state = {
        'version': '2.0',
        'last_full_rebuild': datetime.now().isoformat(),
        'file_count': len(files_data),
        'tag_count': len(tags_data),
        'relation_count': len(rels_data),
        'total_size_bytes': total_size,
        'files': {d['p']: d['i'] for d in files_data},
    }
    INDEX_STATE_JSON.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    # Generate domain files
    print("\n📂 生成领域索引...")
    domain_contents = build_domain_files(docs)
    for fname, content in domain_contents.items():
        fpath = DOMAIN_DIR / fname
        fpath.write_text(content, encoding='utf-8')
        print(f"   ✏️  {fname} ({len(content)} bytes)")

    # Initialize query memory if not exists
    if not QUERY_MEMORY_JSON.exists():
        default_memory = [
            {
                "pattern": ".*怎么配置$",
                "route_hint": ["软件配置", "教程"],
                "success_count": 0
            },
            {
                "pattern": ".*是什么$",
                "route_hint": ["AI相关", "开发"],
                "success_count": 0
            },
        ]
        QUERY_MEMORY_JSON.write_text(json.dumps(default_memory, ensure_ascii=False, indent=2), encoding='utf-8')

    print("\n✅ 全量重建完成！")


def cmd_incremental():
    """Incremental update: only re-process changed files."""
    state = {}
    if INDEX_STATE_JSON.exists():
        try:
            state = json.loads(INDEX_STATE_JSON.read_text(encoding='utf-8'))
        except Exception:
            pass

    # For simplicity, do a full rebuild (incremental logic can be added later)
    print("🔄 增量更新（委托全量重建以确保一致性）...")
    cmd_rebuild()


def cmd_search(query: str, top: int = 5):
    """Execute search with domain guidance."""
    level = classify_query(query)
    print(f"\n🔍 查询路由: {level['level']} ({level['label']})")
    print(f"   建议领域: {level.get('domain', '综合')}")
    print(f"   检索路径: {level['path']}")

    # Suggest reading domain index for context
    domain_file = _resolve_domain_file(level.get('domain', ''))
    if domain_file:
        print(f"   💡 建议先读: domain/{domain_file} (获取领域上下文)")

    results = search(query, top)
    if not results:
        print("   ❌ 未找到结果，建议:")
        print("      1. 读取领域索引: python ai_index_builder_v2.py domain-read <领域>")
        print("      2. 手动浏览 📖目录")
        return

    print(f"\n📋 Top {len(results)} 结果:")
    for i, f in enumerate(results, 1):
        score = f.get('score', 0)
        print(f"   {i}. {f['title']} (score: {score})")
        print(f"      路径: {f['path']}")
        print()


def _resolve_domain_file(domain_name: str) -> str:
    """Map domain display name to filename."""
    mapping = {
        '🤖 AI': 'ai.md',
        '💻 开发': 'dev.md',
        '🪟 系统': 'system.md',
        '🧁 项目': 'project.md',
        '🙎 个人': 'life.md',
        '🧠 思维': 'thinking.md',
        '综合': 'root-index.md',
    }
    return mapping.get(domain_name, 'root-index.md')


def cmd_domain_read(domain: str):
    """Read a domain index file for navigation context."""
    # Map aliases
    aliases = {
        'ai': 'ai.md', 'AI': 'ai.md', '人工智能': 'ai.md',
        'dev': 'dev.md', '开发': 'dev.md', '编程': 'dev.md',
        'system': 'system.md', '系统': 'system.md',
        'project': 'project.md', '项目': 'project.md', '法律': 'project.md', '案件': 'project.md',
        'life': 'life.md', '生活': 'life.md', '个人': 'life.md', '租房': 'life.md',
        'thinking': 'thinking.md', '思维': 'thinking.md', '思维框架': 'thinking.md', '模型': 'thinking.md',
        'root': 'root-index.md', '目录': 'root-index.md', 'index': 'root-index.md',
    }

    fname = aliases.get(domain.lower(), aliases.get(domain, domain))
    if not fname.endswith('.md'):
        fname = fname + '.md'

    fpath = DOMAIN_DIR / fname
    if not fpath.exists():
        print(f"   ❌ 领域索引不存在: {fname}")
        print(f"   可用领域: ai, dev, system, project, life, thinking, root")
        return

    content = fpath.read_text(encoding='utf-8')
    print(f"\n📂 领域索引: {fname}")
    print(f"   Token 消耗: ~{len(content)//4} tokens")
    print(f"   内容预览:")
    print(f"   {'='*50}")
    # Print first 20 lines or truncated content
    lines = content.split('\n')
    for line in lines[:40]:
        print(f"   {line}")
    if len(lines) > 40:
        print(f"   ... (共 {len(lines)} 行，已截断)")
    print(f"   {'='*50}")
    print(f"   💡 建议: 根据领域索引中的文件路径，读取目标文件正文")


def cmd_router(query: str):
    """Just classify and print route info."""
    level = classify_query(query)
    print(f"\n🎯 Query Router 判定:")
    print(f"   等级: {level['level']}")
    print(f"   类型: {level['label']}")
    print(f"   路径: {level['path']}")
    print(f"   Token: {level['tokens']}")


def cmd_status():
    """Print index status."""
    if INDEX_STATE_JSON.exists():
        state = json.loads(INDEX_STATE_JSON.read_text(encoding='utf-8'))
        print(f"\n📊 LD-DVA Final 状态:")
        print(f"   版本: {state.get('version', '?')}")
        print(f"   最后重建: {state.get('last_full_rebuild', '?')}")
        print(f"   文件数: {state.get('file_count', 0)}")
        print(f"   标签数: {state.get('tag_count', 0)}")
        print(f"   关系数: {state.get('relation_count', 0)}")
        print(f"   总大小: {state.get('total_size_bytes', 0)} bytes")
    else:
        print("⚠️  未找到索引，请先运行 rebuild")


def cmd_health():
    """Run health check on JSON indexes."""
    issues = []
    checks = []

    # Check directory structure
    for subdir in ['runtime', 'domain', 'protocol', 'cache']:
        d = AI_INDEX_ROOT / subdir
        ok = d.exists()
        checks.append((f'{subdir}/ 目录', ok))
        if not ok:
            issues.append(f'{subdir}/ 目录缺失')

    # Check JSON files
    for jf in [FILES_JSON, TAGS_JSON, RELATIONS_JSON]:
        ok = jf.exists()
        checks.append((f'{jf.name}', ok))
        if not ok:
            issues.append(f'{jf.name} 缺失')

    # Check protocol
    ok = AI_READ_PROTOCOL.exists()
    checks.append(('AI_READ_PROTOCOL.md', ok))
    if not ok:
        issues.append('AI_READ_PROTOCOL.md 缺失')

    # Check size — split into core (tags+relations) vs search-helper (files)
    # Use stat().st_size (bytes) for consistency with health-check-all
    tags_size = TAGS_JSON.stat().st_size if TAGS_JSON.exists() else 0
    rels_size = RELATIONS_JSON.stat().st_size if RELATIONS_JSON.exists() else 0
    core_size = tags_size + rels_size
    core_ok = core_size <= 40 * 1024  # Core AI runtime < 40KB
    checks.append((f'核心索引大小 (tags+rels) < 40KB ({core_size/1024:.1f}KB)', core_ok))
    if not core_ok:
        issues.append(f'核心索引 {core_size/1024:.1f}KB 超过 40KB')

    files_size = FILES_JSON.stat().st_size if FILES_JSON.exists() else 0
    total_size = core_size + files_size
    total_ok = total_size <= 150 * 1024  # Total including search-helper < 150KB
    checks.append((f'总索引大小 (含files.json) < 150KB ({total_size/1024:.1f}KB)', total_ok))

    # Check files.json structure
    if FILES_JSON.exists():
        try:
            data = json.loads(FILES_JSON.read_text(encoding='utf-8'))
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
                has_required = all(k in entry for k in ['i', 't', 'p'])
                checks.append(('files.json 结构完整', has_required))
                if not has_required:
                    issues.append('files.json 缺少必需字段')
            else:
                checks.append(('files.json 非空数组', False))
                issues.append('files.json 为空或格式错误')
        except Exception:
            checks.append(('files.json 可解析', False))
            issues.append('files.json JSON 解析失败')

    # Check query-memory
    ok = QUERY_MEMORY_JSON.exists()
    checks.append(('query-memory.json', ok))
    if not ok:
        issues.append('query-memory.json 缺失')

    print("\n🏥 LD-DVA Final 健康检查:")
    for name, ok in checks:
        status = "✅" if ok else "❌"
        print(f"   {status} {name}")

    if issues:
        print(f"\n   ❌ 发现 {len(issues)} 个问题:")
        for i in issues:
            print(f"      - {i}")
    else:
        print(f"\n   ✅ 全部通过！")

    return len(issues) == 0


def cmd_cache_read(query: str):
    """Read pattern cache for a query."""
    if not QUERY_MEMORY_JSON.exists():
        print("   查询记忆尚未建立")
        return
    try:
        memory = json.loads(QUERY_MEMORY_JSON.read_text(encoding='utf-8'))
        q_lower = query.lower()
        for entry in memory:
            pattern = entry.get('pattern', '')
            # Use search instead of match to find pattern anywhere
            if re.search(pattern, q_lower):
                print(f"   🎯 命中模式: {pattern}")
                print(f"      建议路径: {entry.get('route_hint', [])}")
                print(f"      成功次数: {entry.get('success_count', 0)}")
                return
        print(f"   未匹配任何模式")
    except Exception:
        print("   查询记忆解析失败")


def cmd_cache_write(query: str, route: str):
    """Write a query pattern to cache."""
    if not QUERY_MEMORY_JSON.exists():
        memory = []
    else:
        try:
            memory = json.loads(QUERY_MEMORY_JSON.read_text(encoding='utf-8'))
        except Exception:
            memory = []

    q_lower = query.lower()
    # Convert query to pattern (search-compatible, no $ anchor)
    if '怎么配置' in query:
        pattern = '怎么配置'
    elif '怎么' in query or '如何' in query:
        pattern = '(怎么|如何)'
    elif '是什么' in query:
        pattern = '是什么'
    elif '分析' in query:
        pattern = '分析'
    elif '对比' in query:
        pattern = '对比'
    else:
        pattern = re.escape(q_lower)

    # Update or add
    found = False
    for entry in memory:
        if entry.get('pattern') == pattern:
            entry['success_count'] = entry.get('success_count', 0) + 1
            found = True
            break
    if not found:
        memory.append({
            'pattern': pattern,
            'route_hint': [route] if route else [],
            'success_count': 1,
        })

    QUERY_MEMORY_JSON.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"   ✅ 已写入模式: {pattern} → {route}")


# ======================================================================
# CLI 入口
# ======================================================================
def main():
    parser = argparse.ArgumentParser(description='LD-DVA Final Architecture Builder v2')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('rebuild', help='Full rebuild')
    sub.add_parser('incremental', help='Incremental update')
    sub.add_parser('status', help='Show status')
    sub.add_parser('health', help='Health check')

    p_search = sub.add_parser('search', help='Search index')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('--top', type=int, default=5, help='Top N results')

    p_router = sub.add_parser('router', help='Classify query')
    p_router.add_argument('query', help='Query to classify')

    p_cache_read = sub.add_parser('cache-read', help='Read query memory')
    p_cache_read.add_argument('query', help='Query')

    p_cache_write = sub.add_parser('cache-write', help='Write query memory')
    p_cache_write.add_argument('query', help='Query')
    p_cache_write.add_argument('route', help='Route hint')

    p_domain = sub.add_parser('domain-read', help='Read domain index for navigation')
    p_domain.add_argument('domain', help='Domain name: ai, dev, system, project, life, thinking, root')

    args = parser.parse_args()

    cmd = args.command
    if cmd == 'rebuild':
        cmd_rebuild()
    elif cmd == 'incremental':
        cmd_incremental()
    elif cmd == 'search':
        cmd_search(args.query, args.top)
    elif cmd == 'router':
        cmd_router(args.query)
    elif cmd == 'domain-read':
        cmd_domain_read(args.domain)
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'health':
        cmd_health()
    elif cmd == 'cache-read':
        cmd_cache_read(args.query)
    elif cmd == 'cache-write':
        cmd_cache_write(args.query, args.route)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
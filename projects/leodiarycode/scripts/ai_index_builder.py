#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LD-DVA Final AI_INDEX Builder
============================
构建 LeoDiary 的 AI 检索加速层。
生成5个AI_INDEX文件：retrieval-index.md / tag-index.md / entity-index.md / query-cache.json / index-state.json

命令：
  python ai_index_builder.py rebuild         全量重建
  python ai_index_builder.py incremental     增量更新（基于 index-state.json 对比 hash，跳过未变化文件）
  python ai_index_builder.py update <path>   更新单个文件（只读该文件，其余从缓存加载）
  python ai_index_builder.py rename <old> <new>  重命名文件
  python ai_index_builder.py search <query> [--top N]  搜索文件（评分排序）
  python ai_index_builder.py cache-read <query>   读取缓存
  python ai_index_builder.py cache-write <query> <files_json>  写入缓存
  python ai_index_builder.py cache-invalidate <path>  失效缓存
  python ai_index_builder.py cache-clear     清空缓存
  python ai_index_builder.py status         查看状态
  python ai_index_builder.py health         健康检查
"""

import sys
import os
import re
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from obsidian_common import (
    VAULT_ROOT, SKIP_DIRS, should_skip_dir, should_skip_file,
    read_text_safe, strip_frontmatter,
)

AI_INDEX_DIR = VAULT_ROOT / "🤖AI_INDEX"
QUERY_CACHE_FILE = AI_INDEX_DIR / "query-cache.json"
INDEX_STATE_FILE = AI_INDEX_DIR / "index-state.json"
RETRIEVAL_INDEX_FILE = AI_INDEX_DIR / "retrieval-index.md"
TAG_INDEX_FILE = AI_INDEX_DIR / "tag-index.md"
ENTITY_INDEX_FILE = AI_INDEX_DIR / "entity-index.md"

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
    "法律": ["合同", "诉讼", "立案", "判决", "律师", "合规", "法律风险", "法规", "条款"],
    "产品经理": ["产品", "需求", "PRD", "原型", "用户故事", "产品设计", "需求分析"],
    "业委会": ["业主委员会", "业主自治", "物业管理", "业主权利", "小区治理"],
    "物业": ["物业管理", "物业服务", "物业费", "物业服务合同"],
    "金融": ["风控", "投资", "理财", "贷款", "信用", "风控模型"],
    "写作": ["排版", "润色", "校对", "文案", "内容创作"],
    "决策": ["复盘", "决策模型", "思维模型", "事后诸葛亮"],
    "Cloudflare": ["CF", "Workers", "R2", "KV", "D1", "Turnstile", "Cloudflare One"],
    "React": ["React", "React.js", "Hooks", "组件", "JSX"],
    "Python": ["Python", "Flask", "Django", "FastAPI", "脚本", "自动化"],
}

# 反向同义词映射：扩展词 → 标准词（用于检索扩展）
_SYNONYM_REVERSE: Dict[str, List[str]] = {}
for _std, _syns in SYNONYM_MAP.items():
    for _s in _syns:
        _SYNONYM_REVERSE.setdefault(_s.lower(), []).append(_std)

KNOWLEDGE_DIR_PREFIXES = ("0-", "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-")

# ======================================================================
# 数据质量过滤（R1修复：过滤垃圾 tags/keywords，R4修复：实体质量）
# ======================================================================

import string as _string
_HIGH_QUALITY_TAG_MIN_LEN = 2
_LOW_QUALITY_KEYWORD_MIN_LEN = 2

# 日期/纯数字模式：匹配 2015.03, 2026, 07, 10, 03-06 等
_DATE_PATTERN = re.compile(r'^\d{2,4}[.\-/年]\d{1,2}(-\d{1,2})?$')
_PURE_NUMBER_PATTERN = re.compile(r'^\d+$')
_SINGLE_CHAR_PATTERN = re.compile(r'^[\u4e00-\u9fff]$')

# 单字/纯数字/日期标签黑名单（进一步过滤）
_TAG_BLACKLIST = {
    '年', '月', '日', '个', '期', '次', '种', '类', '项', '件', '步',
    '上', '下', '中', '里', '外', '内', '前', '后', '间', '时',
    '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
}


def _is_low_quality_tag(tag) -> bool:
    """判断 tag 是否为低质量（日期、纯数字、单字、无意义）。"""
    if not tag or not isinstance(tag, str):
        return True
    t = str(tag).strip()
    if not t:
        return True
    if _DATE_PATTERN.match(t):
        return True
    if _PURE_NUMBER_PATTERN.match(t):
        return True
    if _SINGLE_CHAR_PATTERN.match(t):
        return True
    if t.lower() in _TAG_BLACKLIST:
        return True
    if len(t) < _HIGH_QUALITY_TAG_MIN_LEN:
        return True
    return False


def _filter_high_quality_tags(tags: list) -> list:
    """过滤 tags，移除日期/数字/单字等低质量标签。"""
    if not isinstance(tags, list):
        return []
    return [str(t).strip() for t in tags if not _is_low_quality_tag(t)]


def _is_low_quality_keyword(kw) -> bool:
    """判断 keyword 是否为低质量。"""
    if not kw or not isinstance(kw, str):
        return True
    k = str(kw).strip()
    if not k:
        return True
    if _DATE_PATTERN.match(k):
        return True
    if _PURE_NUMBER_PATTERN.match(k):
        return True
    if _SINGLE_CHAR_PATTERN.match(k):
        return True
    if k.lower() in _TAG_BLACKLIST:
        return True
    if len(k) < _LOW_QUALITY_KEYWORD_MIN_LEN:
        return True
    return False


def _filter_high_quality_keywords(keywords: list) -> list:
    """过滤 keywords，移除日期/数字/单字等低质量关键词。"""
    if not isinstance(keywords, list):
        return []
    return [str(k).strip() for k in keywords if not _is_low_quality_keyword(k)]


def _filter_low_quality_entities(entities: list) -> list:
    """过滤实体，移除日期/数字/单字等低质量实体。"""
    if not isinstance(entities, list):
        return []
    result = []
    for e in entities:
        s = str(e).strip()
        if not s:
            continue
        if _DATE_PATTERN.match(s):
            continue
        if _PURE_NUMBER_PATTERN.match(s):
            continue
        if _SINGLE_CHAR_PATTERN.match(s):
            continue
        if s.lower() in _TAG_BLACKLIST:
            continue
        if len(s) < 2:
            continue
        result.append(s)
    return result


# ======================================================================
# 解析 & 提取
# ======================================================================

def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter into dict. Handles simple YAML (no nested structures)."""
    result = {}
    stripped = content.lstrip()
    if not stripped.startswith('---'):
        return result
    lines = stripped.splitlines()
    if len(lines) < 2:
        return result
    if lines[0].strip() != '---':
        return result
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break
    if end_idx == -1:
        return result
    fm_lines = lines[1:end_idx]
    current_key = None
    for line in fm_lines:
        if not line.strip() or line.strip().startswith('#'):
            continue
        if current_key and line.startswith(' '):
            existing = result.get(current_key, "")
            val = line.strip().strip('-').strip()
            if val:
                existing = (existing + "\n" + val).strip() if existing else val
                result[current_key] = existing
            continue
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            if value.startswith('|') or value.startswith('>'):
                current_key = key
                result[key] = ""
                continue
            current_key = None
            parsed_value = _parse_yaml_value(value)
            result[key] = parsed_value
    return result


def _parse_yaml_value(value: str):
    """Parse a single YAML value."""
    if value == "" or value is None:
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


def _extract_summary_from_body(content: str) -> str:
    """Extract >✍️ summary from body after frontmatter."""
    body = strip_frontmatter(content)
    m = re.search(r'>✍️\s*(.+)', body)
    if m:
        return m.group(1).strip()
    return ""


def _extract_keywords_from_text(text: str, max_count: int = 10) -> List[str]:
    """Extract keywords from text (title + summary + tags).
    
    改进：
    1. 中文关键词：2-6字，过滤常见停用词
    2. 英文关键词：4+字符，过滤常见技术缩写
    3. 优先提取名词短语（如"Cloudflare Workers"）
    """
    text_lower = text.lower()
    kws = set()
    
    # 扩展的停用词列表
    stop_words = {
        # 中文停用词
        '的', '了', '是', '在', '有', '和', '与', '或', '为', '对', '用', '向', '从', '到',
        '这', '那', '我', '你', '他', '她', '它', '们', '个', '种', '些', '什么', '怎么',
        '可以', '需要', '应该', '能够', '已经', '正在', '将会', '如果', '因为', '所以',
        '但是', '而且', '或者', '以及', '等', '等等', '中', '上', '下', '里', '内', '外',
        # 英文停用词
        'the', 'a', 'an', 'is', 'to', 'of', 'in', 'for', 'on', 'and', 'or', 'with',
        'pro', 'md', 'api', 'cli', 'ui', 'ux', 'css', 'html', 'js', 'app', 'info',
        'config', 'data', 'code', 'file', 'page', 'tool', 'new', 'old', 'test', 'demo',
        'todo', 'src', 'dev', 'prod', 'log', 'set', 'get', 'id', 'key', 'url', 'uri',
        'path', 'dir', 'name', 'type', 'time', 'date', 'note', 'notes', 'learn', 'read',
        'write', 'open', 'close', 'start', 'end', 'run', 'stop', 'load', 'save', 'check',
        'update', 'create', 'delete', 'list', 'item', 'user', 'pass', 'word', 'text',
        'line', 'step', 'part', 'case', 'example', 'how', 'what', 'where', 'when', 'why',
        'this', 'that', 'these', 'those', 'it', 'its', 'be', 'are', 'was', 'were', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'must', 'need', 'use', 'using', 'used',
    }
    
    # 中文正则：匹配2-6字的中文词组
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]{2,6}')
    for match in chinese_pattern.finditer(text_lower):
        word = match.group()
        if word not in stop_words and not re.match(r'^[\d]+$', word):
            kws.add(word)
    
    # 英文正则：匹配4+字符的英文单词（技术术语）
    english_pattern = re.compile(r'[a-z][a-z0-9]{3,}')
    for match in english_pattern.finditer(text_lower):
        word = match.group()
        if word not in stop_words and len(word) >= 4:
            kws.add(word)
    
    # 尝试提取复合词（如 "Cloudflare Workers"）
    compound_pattern = re.compile(r'[a-z]+ [a-z]+')
    for match in compound_pattern.finditer(text_lower):
        compound = match.group()
        if len(compound) > 6:  # 只保留较长的复合词
            kws.add(compound)
    
    # 按长度排序，优先保留较长的关键词
    sorted_kws = sorted(kws, key=lambda x: (-len(x), x))
    return sorted_kws[:max_count]


def _file_hash(content: str) -> str:
    """Compute MD5 hash of file content for change detection."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def _collect_all_md_files(vault_root: Path) -> List[Path]:
    """Collect all .md files from knowledge directories (0-8 prefixes)."""
    result = []
    for entry in vault_root.iterdir():
        if not entry.is_dir():
            continue
        if should_skip_dir(entry.name):
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


def _get_relative_path(file_path: Path, vault_root: Path) -> str:
    """Get file path relative to vault root as POSIX string."""
    try:
        rel = file_path.relative_to(vault_root)
        return str(rel).replace('\\', '/')
    except ValueError:
        return file_path.name


def _extract_entities(frontmatter: dict, title: str) -> List[str]:
    """Extract entities from frontmatter (entities/keywords/tags) and title."""
    entities = set()
    _SKIP_ENTITIES = {
        '账号', '个人', '工具', '知识', '项目文档', '踩坑', 'FAQ', '教程', '清单', '会议', '决策', '规范', '记录',
        'AI', '开发', '系统', '软件', '项目', '思维', '影视', '核心规则', '笔记', '文档', '文件', '内容',
        '说明', '方法', '配置', '使用', '问题', '答案', '方案', '流程', '功能', '平台', '服务', 'md', 'ppt',
        'vue', 'wsl', 'cf', 'ui', 'ux', 'css', 'html', 'js', 'api', 'cli', 'app', 'info', 'config', 'data',
        'code', 'file', 'page', 'tool', 'new', 'old', 'test', 'demo', 'todo', 'src', 'dev', 'prod', 'log',
        'set', 'get', 'id', 'key', 'url', 'uri', 'path', 'dir', 'name', 'type', 'time', 'date', 'note', 'notes',
        'learn', 'read', 'write', 'open', 'close', 'start', 'end', 'run', 'stop', 'load', 'save', 'check', 'update',
        'create', 'delete', 'list', 'item', 'user', 'pass', 'word', 'text', 'line', 'step', 'part', 'case', 'example',
        'access', 'find', 'search', 'quick', 'owner', 'org', 'github', 'git', 'work', 'plan', 'idea', 'design',
        'build', 'make', 'help', 'need', 'want', 'use', 'try', 'ask', 'give', 'take', 'see', 'look', 'call', 'move',
        'live', 'play', 'break', 'count', 'report', 'result', 'status', 'level', 'group', 'team', 'member', 'role',
        'task', 'action', 'event', 'state', 'model', 'value', 'range', 'scale', 'mode', 'form', 'field', 'area',
        'point', 'base', 'core', 'main', 'top', 'mid', 'low', 'high', 'deep', 'wide', 'long', 'short', 'big',
        'small', 'full', 'half', 'all', 'every', 'some', 'any', 'few', 'many', 'much', 'more', 'most', 'least',
        'less', 'enough', 'npx', 'toml', 'win', 'mac', 'linux', 'ios', 'android', 'web', 'net', 'ip', 'dns', 'cdn',
        'sdk', 'ide', 'kpi', 'roi', 'b端', 'c端', 'saas', 'paas', 'iaas', 'agile', 'lean', 'scrum'
    }

    def _is_meaningful(token: str) -> bool:
        if token.lower() in _SKIP_ENTITIES:
            return False
        if re.match(r'^[\d]+$', token):
            return False
        if _DATE_PATTERN.match(token):
            return False
        if _SINGLE_CHAR_PATTERN.match(token):
            return False
        if token.lower() in _TAG_BLACKLIST:
            return False
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', token))
        if has_chinese:
            return len(token) >= 2
        return len(token) >= 4

    if 'entities' in frontmatter and isinstance(frontmatter['entities'], list):
        for e in frontmatter['entities']:
            if e and _is_meaningful(str(e)):
                entities.add(str(e))
    kw = frontmatter.get('keywords', [])
    if isinstance(kw, list):
        for k in kw:
            ks = str(k)
            if _is_meaningful(ks):
                entities.add(ks)
    tags = frontmatter.get('tags', [])
    if isinstance(tags, list):
        for t in tags:
            ts = str(t)
            if _is_meaningful(ts):
                entities.add(ts)
    title_words = _extract_keywords_from_text(title, 5)
    for w in title_words:
        if _is_meaningful(w):
            entities.add(w)
    return sorted(list(entities))[:8]


# ======================================================================
# 评分 & 同义词扩展（修复：死代码激活 + 同义词参与检索）
# ======================================================================

def _expand_query(query: str) -> List[str]:
    """Expand query using synonym map. Returns list of original + expanded terms."""
    terms = [query]
    query_lower = query.lower()
    for word in re.findall(r'[a-zA-Z\u4e00-\u9fff]+', query_lower):
        # 标准词 → 扩展
        for std, syns in SYNONYM_MAP.items():
            if word == std.lower():
                terms.extend(syns)
        # 扩展词 → 标准词
        if word in _SYNONYM_REVERSE:
            terms.extend(_SYNONYM_REVERSE[word])
    return list(set(terms))


def _compute_score(query: str, doc: dict) -> int:
    """Compute retrieval score with synonym expansion.
    累加权重：多个位置同时命中时累加分数，使排序更精细。
    Weights: filename(100) + title(90) + summary(70) + keywords(60) + tags(40) + body(20).
    
    Body matching uses body_preview (first 500 chars) if available.
    """
    expanded = _expand_query(query)
    score = 0
    
    fname_lower = doc.get('file_name', '').lower()
    for term in expanded:
        if term.lower() in fname_lower:
            score += 100
            break
    
    title_lower = doc.get('title', '').lower()
    for term in expanded:
        if term.lower() in title_lower:
            score += 90
            break
    
    summary_lower = doc.get('summary', '').lower()
    for term in expanded:
        if term.lower() in summary_lower:
            score += 70
            break
    
    kws = [str(k).lower() for k in doc.get('keywords', [])]
    for term in expanded:
        if term.lower() in kws:
            score += 60
            break
    
    tags = [str(t).lower() for t in doc.get('tags', [])]
    for term in expanded:
        if term.lower() in tags:
            score += 40
            break
    
    body_preview = doc.get('body_preview', '').lower()
    if body_preview:
        for term in expanded:
            if term.lower() in body_preview:
                score += 20
                break
    
    return score


# ======================================================================
# JSON 工具
# ======================================================================

def _load_json(path: Path, default=None):
    """Load JSON file safely."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, data):
    """Save JSON file safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ======================================================================
# 文档索引构建
# ======================================================================

def _build_document_index(vault_root: Path) -> List[dict]:
    """Scan all knowledge files and build document index."""
    docs = []
    files = _collect_all_md_files(vault_root)
    print(f"  扫描到 {len(files)} 个知识文件...")
    for fp in files:
        try:
            doc = _read_single_file(fp, vault_root)
            if doc:
                docs.append(doc)
        except Exception as e:
            print(f"  警告：解析 {fp} 失败 - {e}")
    return docs


def _read_single_file(fp: Path, vault_root: Path) -> Optional[dict]:
    """Read a single knowledge file and return doc metadata dict."""
    content = read_text_safe(fp)
    if not content.strip():
        return None
    fm = _parse_frontmatter(content)
    title = fm.get('title', '') or ''
    body = strip_frontmatter(content)
    if not title:
        m = re.search(r'^#\s+(.+)', body, re.MULTILINE)
        if m:
            title = m.group(1).strip()
    summary = fm.get('summary', '')
    if not summary:
        summary = _extract_summary_from_body(content)
    tags = _filter_high_quality_tags(fm.get('tags', []))
    keywords = _filter_high_quality_keywords(fm.get('keywords', []))
    if not keywords and summary:
        keywords = _extract_keywords_from_text(f"{title} {summary}", 10)
    entities = _extract_entities(fm, title)
    entities = _filter_low_quality_entities(entities)
    file_rel = _get_relative_path(fp, vault_root)
    file_hash = _file_hash(content)
    updated = fm.get('updated', '') or fm.get('modified', '') or datetime.now().strftime('%Y-%m-%d')
    body_preview = body[:500] if body else ''
    if not body_preview and summary:
        body_preview = summary[:500]
    return {
        'path': file_rel,
        'file_name': fp.stem,
        'title': title or fp.stem,
        'type': fm.get('type', ''),
        'tags': tags,
        'keywords': keywords,
        'summary': summary,
        'entities': entities,
        'updated': str(updated),
        'id': fm.get('id', ''),
        'hash': file_hash,
        'body_preview': body_preview,
    }


# ======================================================================
# 索引生成（修复：tag 移除 Top 15 限制、entity 移除 Top 50 限制 + 类型分类）
# ======================================================================

def _generate_retrieval_index_md(docs: List[dict], vault_root: Path) -> str:
    """Generate retrieval-index.md content."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    now_display = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_kws = set()
    for d in docs:
        for k in d.get('keywords', []):
            total_kws.add(str(k).lower())
    lines = []
    lines.append("---\n")
    lines.append("index_type: retrieval-index\n")
    lines.append("version: 2.1\n")
    lines.append(f"generated_at: {now}\n")
    lines.append(f"source_count: {len(docs)}\n")
    lines.append("---\n\n")
    lines.append("# 🤖 AI 检索索引\n\n")
    lines.append("> **第一读取入口** — 关键词倒排索引\n")
    lines.append("> ⚠️ 本文件由 ai_index_builder.py 自动生成，禁止手动编辑\n\n---\n\n")
    lines.append("## 索引统计\n")
    lines.append(f"- 关键词总数：{len(total_kws)}\n")
    lines.append(f"- 覆盖文件：{len(docs)} / {len(docs)}\n")
    lines.append(f"- 最后更新：{now_display}\n\n---\n\n")
    lines.append("## 同义词映射\n\n")
    lines.append("| 输入 | 扩展 |\n|------|------|\n")
    for k, v in SYNONYM_MAP.items():
        lines.append(f"| {k} | → {', '.join(v)} |\n")
    lines.append("\n---\n\n")
    lines.append("## 文件索引（按首字母 A-Z 排列，按检索价值加权）\n\n")
    sorted_docs = sorted(docs, key=lambda d: d.get('title', '').lower())
    for d in sorted_docs:
        title = d.get('title', d['file_name'])
        lines.append(f"### {title}\n\n")
        lines.append(f"- **Path**: `{d['path']}`\n")
        summary = d.get('summary', '') or '(无摘要)'
        lines.append(f"- **Summary**: {summary}\n")
        kws = ', '.join(str(k) for k in d.get('keywords', [])[:10]) or '(无关键词)'
        lines.append(f"- **Keywords**: {kws}\n")
        tags = ', '.join(str(t) for t in d.get('tags', [])[:5]) or '(无标签)'
        lines.append(f"- **Tags**: {tags}\n")
        lines.append(f"- **Type**: {d.get('type', '') or '未分类'}\n")
        lines.append(f"- **Updated**: {d.get('updated', '')}\n\n")
    lines.append("---\n\n")
    lines.append("## AI Agent 使用规则\n\n")
    lines.append("1. **先读本文件**，按 [Ctrl+F] 搜索关键词\n")
    lines.append("2. 获取 Top N 候选文件（默认 3 个）\n")
    lines.append("3. 按 L0-L2 协议读取候选文件\n")
    lines.append("4. 关键词未命中 → 读 `tag-index.md`\n")
    return ''.join(lines)


def _generate_tag_index_md(docs: List[dict]) -> str:
    """Generate tag-index.md content. Includes ALL tags (no Top 15 limit)."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    tag_map: Dict[str, List[dict]] = {}
    for d in docs:
        for t in d.get('tags', []):
            t_str = str(t).strip()
            if t_str:
                tag_map.setdefault(t_str, []).append(d)
    sorted_tags = sorted(tag_map.items(), key=lambda x: len(x[1]), reverse=True)
    lines = []
    lines.append("---\n")
    lines.append("index_type: tag-index\n")
    lines.append("version: 2.1\n")
    lines.append(f"generated_at: {now}\n")
    lines.append(f"source_count: {len(docs)}\n")
    lines.append("---\n\n")
    lines.append("# 🏷️ AI 标签索引\n\n")
    lines.append("> **跨域关联入口** — 标签 → 文件映射\n\n---\n\n")
    # 摘要表：Top 15（概览用）
    lines.append("## 热门标签 TOP 15\n\n")
    lines.append("| 标签 | 文件数 | 关联标签 |\n|------|--------|---------|\n")
    for tag, tag_docs in sorted_tags[:15]:
        related_tags = set()
        for td in tag_docs:
            for t in td.get('tags', []):
                if str(t) != tag:
                    related_tags.add(str(t))
        rel = ', '.join(f'#{t}' for t in sorted(related_tags)[:5])
        lines.append(f"| `#{tag}` | {len(tag_docs)} | {rel} |\n")
    lines.append("\n---\n\n")
    # 详情：全部标签（修复：不再限制 Top 15）
    lines.append(f"## 标签详情（共 {len(sorted_tags)} 个标签）\n\n")
    for tag, tag_docs in sorted_tags:
        lines.append(f"### `#{tag}` ({len(tag_docs)} 个文件)\n\n")
        sorted_d = sorted(tag_docs, key=lambda d: d.get('title', ''))
        lines.append("**核心文件**：\n")
        for i, d in enumerate(sorted_d[:5], 1):
            score = 95 - (i - 1) * 3
            lines.append(f"{i}. [[{d['file_name']}]] (score: {score})\n")
        if len(sorted_d) > 5:
            remaining = ', '.join(f'[[{d["file_name"]}]]' for d in sorted_d[5:10])
            lines.append(f"\n更多文件：{remaining}\n")
        related_tags = set()
        for td in tag_docs:
            for t in td.get('tags', []):
                if str(t) != tag:
                    related_tags.add(str(t))
        rel = ', '.join(f'#{t}' for t in sorted(related_tags)[:3])
        lines.append(f"\n**关联标签**：`{rel}`\n\n")
    lines.append("---\n\n")
    lines.append("## AI Agent 使用指南\n")
    lines.append("1. 从用户问题提取可能的标签\n")
    lines.append("2. 读取对应标签的核心文件\n")
    lines.append("3. 根据关联标签扩展检索范围\n")
    return ''.join(lines)


def _classify_entity_type(entity_name: str, files: List[dict]) -> str:
    """Classify entity type based on name heuristics and file metadata.
    Returns one of: 工具, 概念, 协议, 组织.
    """
    name_lower = entity_name.lower()
    # 组织特征
    org_keywords = ['公司', '组织', '团队', '大学', '学院', '基金', '协会', '联盟',
                    'inc', 'corp', 'ltd', 'foundation', 'university', 'institute',
                    'anthropic', 'openai', 'google', 'microsoft', 'cloudflare',
                    'github', 'mozilla', 'apple', 'amazon', 'meta']
    for kw in org_keywords:
        if kw in name_lower:
            return '组织'
    # 协议特征
    protocol_keywords = ['协议', '标准', '规范', 'protocol', 'standard', 'spec',
                         'rfc', 'http', 'https', 'tcp', 'grpc', 'websocket']
    for kw in protocol_keywords:
        if kw in name_lower:
            return '协议'
    # 概念特征：较长中文名或抽象名词
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', entity_name))
    if chinese_chars >= 3:
        return '概念'
    # 基于关联文件的 type 字段推断
    type_counts: Dict[str, int] = {}
    for d in files:
        t = d.get('type', '')
        if t:
            type_counts[t] = type_counts.get(t, 0) + 1
    dominant_type = max(type_counts, key=type_counts.get) if type_counts else ''
    if dominant_type in ('工具', '软件'):
        return '工具'
    if dominant_type in ('规范', '决策'):
        return '概念'
    # 默认按文件数量启发式
    if len(files) >= 5:
        return '工具'
    return '概念'


def _generate_entity_index_md(docs: List[dict]) -> str:
    """Generate entity-index.md content. Includes ALL entities (no Top 50 limit).
    
    改进：
    1. 关联实体数量限制：最多10个
    2. 过滤低质量实体（标题片段、无意义词）
    3. 只保留真正的实体关系
    """
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    entity_map: Dict[str, dict] = {}
    
    # 低质量实体过滤列表（标题片段、无意义词）
    _LOW_QUALITY_ENTITIES = {
        '介绍', '教程', '指南', '配置', '安装', '使用', '设置', '管理', '工具', '方法',
        '技巧', '总结', '分享', '记录', '文档', '说明', '规范', '标准', '流程', '方案',
        '问题', '解决', '优化', '改进', '提升', '增强', '完善', '更新', '升级', '迁移',
    }
    
    for d in docs:
        for e in d.get('entities', []):
            e_str = str(e).strip()
            if not e_str:
                continue
            if e_str.lower() in _LOW_QUALITY_ENTITIES:
                continue
            if _DATE_PATTERN.match(e_str):
                continue
            if _PURE_NUMBER_PATTERN.match(e_str):
                continue
            if _SINGLE_CHAR_PATTERN.match(e_str):
                continue
            if len(e_str) < 2:
                continue
            if e_str not in entity_map:
                entity_map[e_str] = {
                    'name': e_str,
                    'files': [],
                    'related_entities': set(),
                }
            entity_map[e_str]['files'].append(d)
            for r in d.get('entities', []):
                r_str = str(r).strip()
                if r_str == e_str:
                    continue
                if r_str.lower() in _LOW_QUALITY_ENTITIES:
                    continue
                if _DATE_PATTERN.match(r_str):
                    continue
                if _PURE_NUMBER_PATTERN.match(r_str):
                    continue
                if len(r_str) < 2:
                    continue
                entity_map[e_str]['related_entities'].add(r_str)
    
    # 按类型分组统计（修复：使用实际分类而非硬编码）
    entity_type_counts: Dict[str, int] = {'工具': 0, '概念': 0, '协议': 0, '组织': 0}
    entity_type_map: Dict[str, str] = {}
    for e, info in entity_map.items():
        etype = _classify_entity_type(e, info['files'])
        entity_type_map[e] = etype
        entity_type_counts[etype] = entity_type_counts.get(etype, 0) + 1
    lines = []
    lines.append("---\n")
    lines.append("index_type: entity-index\n")
    lines.append("version: 2.1\n")
    lines.append(f"generated_at: {now}\n")
    lines.append(f"source_count: {len(docs)}\n")
    lines.append("---\n\n")
    lines.append("# 👤 AI 实体索引\n\n")
    lines.append("> **实体关系入口** — 人名/组织/工具 → 文件映射\n\n---\n\n")
    lines.append("## 实体类型统计\n\n")
    lines.append("| 类型 | 数量 |\n|------|------|\n")
    for t, c in entity_type_counts.items():
        lines.append(f"| {t} | {c} |\n")
    lines.append("\n---\n\n")
    # 详情：全部实体（修复：不再限制 Top 50），按文件数降序
    lines.append(f"## 实体详情（共 {len(entity_map)} 个实体）\n\n")
    sorted_entities = sorted(entity_map.items(), key=lambda x: len(x[1]['files']), reverse=True)
    for e_name, info in sorted_entities:
        etype = entity_type_map.get(e_name, '工具')
        lines.append(f"### `{e_name}` ({etype})\n\n")
        # 限制关联实体数量为10个
        rel = ', '.join(sorted(info['related_entities'])[:10]) or '-'
        lines.append(f"- **关联实体**: {rel}\n")
        lines.append(f"- **相关文件**:\n")
        sorted_f = sorted(info['files'], key=lambda d: d.get('title', ''))
        for i, d in enumerate(sorted_f[:5], 1):
            lines.append(f"  {i}. [[{d['file_name']}]]\n")
        if len(sorted_f) > 5:
            lines.append(f"  ...及其他 {len(sorted_f) - 5} 个文件\n")
        lines.append("\n")
    return ''.join(lines)


# ======================================================================
# 状态管理（修复：存储完整 doc 元数据以支持真正增量）
# ======================================================================

def _save_index_state(docs: List[dict], vault_root: Path):
    """Save index-state.json with hash tracking AND doc metadata for incremental updates."""
    state = {
        "version": "2.1",
        "last_full_rebuild": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        "tracked_files": len(docs),
        "files": {},
    }
    for d in docs:
        doc_copy = {k: v for k, v in d.items() if k != 'hash'}
        state['files'][d['path']] = {
            "hash": d['hash'],
            "updated_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "doc": doc_copy,
        }
    _save_json(INDEX_STATE_FILE, state)


def _load_cached_docs(state: dict) -> Optional[Dict[str, dict]]:
    """Load cached docs from index-state.json. Returns None if old format (no doc metadata)."""
    files = state.get("files", {})
    if not files:
        return None
    # 检查是否有 doc 字段（新格式）
    sample = next(iter(files.values()))
    if 'doc' not in sample:
        return None
    cached = {}
    for path, info in files.items():
        doc = dict(info['doc'])
        doc['hash'] = info.get('hash', '')
        doc['path'] = path
        cached[path] = doc
    return cached


# ======================================================================
# 核心操作（修复：真正增量 + 单文件更新 + 重命名清理）
# ======================================================================

def rebuild(vault_root: Path):
    """Full rebuild of all AI_INDEX files."""
    print("🔄 开始全量重建 AI_INDEX...")
    docs = _build_document_index(vault_root)
    if not docs:
        print("  ⚠️ 没有找到任何知识文件，跳过重建。")
        return
    print(f"  共解析 {len(docs)} 个文件")
    _write_all_indexes(docs, vault_root)
    print(f"🎉 AI_INDEX 全量重建完成！（{len(docs)} 个文件）")


def incremental(vault_root: Path):
    """True incremental update: only read changed files from disk, reuse cached metadata for unchanged files."""
    print("🔄 开始增量更新 AI_INDEX...")
    state = _load_json(INDEX_STATE_FILE, {"files": {}})
    old_files = state.get("files", {})
    if not old_files:
        print("  ⚠️ 无历史状态，执行全量重建...")
        rebuild(vault_root)
        return
    cached_docs = _load_cached_docs(state)
    if cached_docs is None:
        print("  ⚠️ 旧版状态格式（无 doc 缓存），执行全量重建...")
        rebuild(vault_root)
        return
    # 快速扫描文件列表和 hash（只读文件内容计算 hash，不解析 frontmatter）
    current_files = _collect_all_md_files(vault_root)
    current_paths = set()
    new_paths = []
    modified_paths = []
    for fp in current_files:
        rel = _get_relative_path(fp, vault_root)
        current_paths.add(rel)
        try:
            content = read_text_safe(fp)
            h = _file_hash(content)
        except Exception:
            continue
        if rel not in old_files:
            new_paths.append((fp, rel))
        elif old_files[rel].get('hash') != h:
            modified_paths.append((fp, rel))
    removed = [p for p in old_files if p not in current_paths]
    if not new_paths and not modified_paths and not removed:
        print("  ✅ 没有检测到变化")
        return
    print(f"  📝 新增：{len(new_paths)}，修改：{len(modified_paths)}，删除：{len(removed)}")
    skipped = len(current_paths) - len(new_paths) - len(modified_paths)
    print(f"  ⏭️ 跳过未变化文件：{skipped} 个")
    # 只读取变化的文件
    docs_to_read = new_paths + modified_paths
    new_docs = []
    for fp, rel in docs_to_read:
        try:
            doc = _read_single_file(fp, vault_root)
            if doc:
                new_docs.append(doc)
        except Exception as e:
            print(f"  警告：解析 {fp} 失败 - {e}")
    # 合并：未变化的用缓存 + 新读取的
    changed_rel_set = {rel for _, rel in docs_to_read}
    docs = [d for path, d in cached_docs.items() if path not in changed_rel_set and path not in set(removed)]
    docs.extend(new_docs)
    _write_all_indexes(docs, vault_root)
    # 失效相关缓存
    invalidated = 0
    for d in new_docs:
        _invalidate_cache_by_path(vault_root, d['path'])
        invalidated += 1
    for path in removed:
        _invalidate_cache_by_path(vault_root, path)
        invalidated += 1
    print(f"  🔄 已失效 {invalidated} 条相关缓存")
    print(f"🎉 AI_INDEX 增量更新完成！（读取 {len(new_docs)} 个文件，跳过 {skipped} 个）")


def update_file(vault_root: Path, file_path_str: str):
    """Update single file in AI_INDEX: only read this file, reuse cached data for others."""
    print(f"🔄 更新文件：{file_path_str}")
    fp = Path(file_path_str)
    if not fp.is_absolute():
        fp = vault_root / file_path_str
    if not fp.exists():
        print(f"  ❌ 文件不存在：{fp}")
        return
    state = _load_json(INDEX_STATE_FILE, {"files": {}})
    cached_docs = _load_cached_docs(state)
    if cached_docs is None:
        print("  ⚠️ 无缓存数据，执行全量重建...")
        rebuild(vault_root)
        return
    # 只读目标文件
    doc = _read_single_file(fp, vault_root)
    if not doc:
        print(f"  ❌ 无法解析文件：{fp}")
        return
    rel = doc['path']
    cached_docs[rel] = doc
    docs = list(cached_docs.values())
    _write_all_indexes(docs, vault_root)
    _invalidate_cache_by_path(vault_root, rel)
    print(f"  ✅ 已更新，缓存已失效")


def rename_file(vault_root: Path, old_path: str, new_path: str):
    """Handle file rename: invalidate cache and rebuild indexes."""
    print(f"🔄 重命名：{old_path} → {new_path}")
    # 失效旧路径和新路径的缓存
    _invalidate_cache_by_path(vault_root, old_path)
    _invalidate_cache_by_path(vault_root, new_path)
    # 全量重建（确保路径正确）
    rebuild(vault_root)
    print(f"  ✅ 索引已更新，缓存已失效")


def _write_all_indexes(docs: List[dict], vault_root: Path):
    """Generate and write all index files + state."""
    retrieval_content = _generate_retrieval_index_md(docs, vault_root)
    tag_content = _generate_tag_index_md(docs)
    entity_content = _generate_entity_index_md(docs)
    RETRIEVAL_INDEX_FILE.write_text(retrieval_content, encoding='utf-8')
    TAG_INDEX_FILE.write_text(tag_content, encoding='utf-8')
    ENTITY_INDEX_FILE.write_text(entity_content, encoding='utf-8')
    _save_index_state(docs, vault_root)
    print(f"  ✅ retrieval-index.md 已生成")
    print(f"  ✅ tag-index.md 已生成")
    print(f"  ✅ entity-index.md 已生成")
    print(f"  ✅ index-state.json 已更新（含 doc 缓存）")


# ======================================================================
# 搜索命令（修复：激活 _compute_score 死代码）
# ======================================================================

def search_files(vault_root: Path, query: str, top_n: int = 5):
    """Search files using scoring with synonym expansion.
    优先从 index-state.json 缓存读取，避免全量扫描。"""
    state = _load_json(INDEX_STATE_FILE, {"files": {}})
    cached_docs = _load_cached_docs(state)
    
    if cached_docs is None:
        print("  ⚠️ 无索引缓存，全量扫描...")
        docs = _build_document_index(vault_root)
    else:
        docs = list(cached_docs.values())
        print(f"  📚 从索引缓存加载 {len(docs)} 个文档")
    
    scored = []
    for d in docs:
        s = _compute_score(query, d)
        if s > 0:
            scored.append((d, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"🔍 搜索: {query}")
    print(f"   同义词扩展: {', '.join(_expand_query(query))}")
    print(f"   命中 {len(scored)} 个文件，显示前 {min(top_n, len(scored))} 个:\n")
    for i, (d, s) in enumerate(scored[:top_n], 1):
        print(f"  {i}. [{s}分] {d['title']}")
        print(f"     路径: {d['path']}")
        summary = d.get('summary', '')
        if summary:
            print(f"     摘要: {summary[:100]}...")
        print()
    
    if scored:
        top_results = scored[:max(top_n, 5)]
        matched_files = [
            {"path": d['path'], "title": d['title'], "score": s}
            for d, s in top_results
        ]
        try:
            cache_write(query, json.dumps(matched_files, ensure_ascii=False))
            print(f"   💾 已自动写入缓存（{len(matched_files)} 条结果）")
        except Exception:
            pass
    
    return scored[:top_n]


# ======================================================================
# 缓存管理（修复：hit_rate 统计）
# ======================================================================

def _invalidate_cache_by_path(vault_root: Path, file_path: str):
    """Invalidate cache entries containing a specific file path."""
    cache_data = _load_json(QUERY_CACHE_FILE, {"cache": [], "stats": {"total_entries": 0, "hit_rate": 0.0, "tokens_saved": 0}})
    cache = cache_data.get("cache", [])
    before_count = len(cache)
    cache = [entry for entry in cache
             if file_path not in [m.get("path", "") for m in entry.get("matched_files", [])]]
    removed = before_count - len(cache)
    cache_data["cache"] = cache
    cache_data["stats"]["total_entries"] = len(cache)
    cache_data["last_updated"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    _save_json(QUERY_CACHE_FILE, cache_data)
    if removed > 0:
        print(f"  🔥 失效了 {removed} 条缓存条目")


def cache_read(query: str) -> Optional[dict]:
    """Read query cache. Updates hit stats on every call (hit or miss)."""
    cache_data = _load_json(QUERY_CACHE_FILE, {"cache": [], "stats": {}})
    cache = cache_data.get("cache", [])
    now = datetime.now()
    result = None
    for entry in cache:
        if entry.get("query", "").lower() == query.lower():
            expires_at = entry.get("expires_at", "")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at)
                    if now > exp:
                        continue
                except (ValueError, TypeError):
                    pass
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            result = entry
            break
    # 更新统计（修复：正确维护 hit_rate）
    stats = cache_data.setdefault("stats", {})
    stats["total_queries"] = stats.get("total_queries", 0) + 1
    if result:
        stats["cache_hits"] = stats.get("cache_hits", 0) + 1
        stats["tokens_saved"] = stats.get("tokens_saved", 0) + 1000
    total_q = stats["total_queries"]
    hits = stats.get("cache_hits", 0)
    stats["hit_rate"] = hits / total_q if total_q > 0 else 0.0
    stats["total_entries"] = len(cache)
    _save_json(QUERY_CACHE_FILE, cache_data)
    return result


def cache_write(query: str, files_json_str: str):
    """Write a query cache entry. Accepts JSON string or @filename for JSON file."""
    try:
        cleaned = files_json_str.strip()
        if cleaned.startswith("@"):
            file_path = Path(cleaned[1:])
            if not file_path.exists():
                print(f"❌ 文件不存在: {file_path}")
                return
            cleaned = file_path.read_text(encoding='utf-8-sig').strip()
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]
        elif cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        matched_files = json.loads(cleaned)
    except json.JSONDecodeError:
        print("❌ files_json 参数必须是合法 JSON")
        return
    cache_data = _load_json(QUERY_CACHE_FILE, {"cache": [], "config": {}, "stats": {}})
    cache = cache_data.get("cache", [])
    config = cache_data.get("config", {"max_entries": 500, "ttl_seconds": 86400})
    max_entries = config.get("max_entries", 500)
    ttl = config.get("ttl_seconds", 86400)
    now = datetime.now()
    expires_at = (now + timedelta(seconds=ttl)).strftime('%Y-%m-%dT%H:%M:%S')
    keywords = _extract_keywords_from_text(query, 5)
    new_entry = {
        "query": query,
        "keywords": keywords,
        "matched_files": matched_files,
        "read_level": "L0",
        "created_at": now.strftime('%Y-%m-%dT%H:%M:%S'),
        "hit_count": 0,
        "expires_at": expires_at,
    }
    cache = [e for e in cache if e.get("query", "").lower() != query.lower()]
    cache.insert(0, new_entry)
    if len(cache) > max_entries:
        cache = cache[:max_entries]
    cache_data["cache"] = cache
    cache_data["stats"]["total_entries"] = len(cache)
    cache_data["last_updated"] = now.strftime('%Y-%m-%dT%H:%M:%S')
    _save_json(QUERY_CACHE_FILE, cache_data)
    print(f"  ✅ 已写入缓存（query={query[:30]}...，文件数={len(matched_files)}）")


def cache_clear():
    """Clear all cache entries."""
    cache_data = _load_json(QUERY_CACHE_FILE, {"cache": [], "config": {}, "stats": {}})
    cache_data["cache"] = []
    cache_data["stats"] = {
        "total_entries": 0, "hit_rate": 0, "tokens_saved": 0,
        "total_queries": 0, "cache_hits": 0,
    }
    cache_data["last_updated"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    _save_json(QUERY_CACHE_FILE, cache_data)
    print("  ✅ 缓存已清空")


def cache_invalidate(vault_root: Path, file_path: str):
    """Invalidate all cache entries referencing a file."""
    _invalidate_cache_by_path(vault_root, file_path)


# ======================================================================
# 状态显示
# ======================================================================

def show_status(vault_root: Path):
    """Display AI_INDEX status."""
    state = _load_json(INDEX_STATE_FILE, {"tracked_files": 0})
    cache_data = _load_json(QUERY_CACHE_FILE, {"cache": [], "stats": {}})
    stats = cache_data.get('stats', {})
    total_q = stats.get('total_queries', 0)
    hits = stats.get('cache_hits', 0)
    hit_rate = stats.get('hit_rate', 0)
    print("=" * 50)
    print("🤖 AI_INDEX 状态")
    print("=" * 50)
    print(f"  追踪文件数: {state.get('tracked_files', 0)}")
    print(f"  最后全量重建: {state.get('last_full_rebuild', 'N/A')}")
    has_doc_cache = bool(next(iter(state.get('files', {}).values()), {}).get('doc'))
    print(f"  增量缓存: {'✅ 已启用' if has_doc_cache else '❌ 未启用（需 rebuild 激活）'}")
    print(f"  缓存条目数: {len(cache_data.get('cache', []))}")
    print(f"  查询统计: {hits}/{total_q} 命中（{hit_rate:.1%}）")
    print(f"  Token 节省估算: {stats.get('tokens_saved', 0):,}")
    print("-" * 50)
    for name, fpath in [
        ("retrieval-index.md", RETRIEVAL_INDEX_FILE),
        ("tag-index.md", TAG_INDEX_FILE),
        ("entity-index.md", ENTITY_INDEX_FILE),
        ("query-cache.json", QUERY_CACHE_FILE),
        ("index-state.json", INDEX_STATE_FILE),
    ]:
        size = fpath.stat().st_size if fpath.exists() else 0
        status = "✅" if fpath.exists() else "❌"
        print(f"  {status} {name}: {size:,} bytes")
    print("=" * 50)


# ======================================================================
# 入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="LD-DVA Final AI_INDEX Builder")
    parser.add_argument("command", choices=[
        "rebuild", "incremental", "update", "rename", "search",
        "cache-read", "cache-write", "cache-invalidate", "cache-clear", "status",
        "health",
    ])
    parser.add_argument("args", nargs="*", help="Additional arguments")
    parser.add_argument("--vault", default=str(VAULT_ROOT), help="Vault root path")
    parser.add_argument("--top", type=int, default=5, help="Search result count")
    ns = parser.parse_args()
    vault = Path(ns.vault).resolve()
    if not vault.exists():
        print(f"❌ Vault path does not exist: {vault}")
        sys.exit(1)
    AI_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ns.command
    args = ns.args
    if cmd == "rebuild":
        rebuild(vault)
    elif cmd == "incremental":
        incremental(vault)
    elif cmd == "update":
        if not args:
            print("用法：python ai_index_builder.py update <文件路径>")
            sys.exit(1)
        update_file(vault, args[0])
    elif cmd == "rename":
        if len(args) < 2:
            print("用法：python ai_index_builder.py rename <旧路径> <新路径>")
            sys.exit(1)
        rename_file(vault, args[0], args[1])
    elif cmd == "search":
        if not args:
            print("用法：python ai_index_builder.py search <查询词> [--top N]")
            sys.exit(1)
        search_files(vault, ' '.join(args), ns.top)
    elif cmd == "cache-read":
        if not args:
            print("用法：python ai_index_builder.py cache-read <查询>")
            sys.exit(1)
        result = cache_read(args[0])
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("🔍 缓存未命中")
    elif cmd == "cache-write":
        if len(args) < 2:
            print("用法：python ai_index_builder.py cache-write <查询> <files_json>")
            sys.exit(1)
        cache_write(args[0], args[1])
    elif cmd == "cache-invalidate":
        if not args:
            print("用法：python ai_index_builder.py cache-invalidate <文件路径>")
            sys.exit(1)
        cache_invalidate(vault, args[0])
    elif cmd == "cache-clear":
        cache_clear()
    elif cmd == "status":
        show_status(vault)
    elif cmd == "health":
        try:
            from health_check import HealthChecker
            checker = HealthChecker(vault_root=vault)
            report = checker.run_full_check()
            checker.save_report(report)
        except ImportError as e:
            print(f"❌ 无法导入 health_check 模块: {e}")
            print("   确保 health_check.py 位于 src/ 目录下")
            sys.exit(1)


if __name__ == "__main__":
    main()

"""LeoDiary 公共工具模块（从 LEO OS 迁移适配）

所有脚本共享的函数，消除 validate.py/kb_stats.py/lint.py 中的重复代码。
改一处全生效。

适配说明：
- ROOT 通过 set_root() 或命令行参数动态设置
- 目录结构适配 LeoDiary（7- 🧠思维框架/8- 📜核心规则/一级目录用数字前缀）
- 跳过目录适配 LeoDiary

函数清单：
    set_root()            — 设置知识库根目录
    get_root()            — 获取知识库根目录
    parse_front_matter()  — 解析 YAML front matter
    resolve_wiki_link()   — 解析 [[双链]]
    find_md_files()       — 遍历项目 .md 文件
    build_filename_index()— 构建文件名索引
    count_framework_files()— 统计框架文件数量
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ROOT: Path | None = None
_CONFIG: dict[str, Any] | None = None


def set_root(path: str | Path) -> None:
    """设置知识库根目录。设置后自动尝试加载 leo.config.json。"""
    global _ROOT, _CONFIG
    _ROOT = Path(path).resolve()
    _CONFIG = None
    config_path = _ROOT / "leo.config.json"
    if config_path.exists():
        try:
            _CONFIG = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _CONFIG = None


def get_root() -> Path:
    """获取知识库根目录，未设置时抛出异常。"""
    if _ROOT is None:
        raise RuntimeError("ROOT 未设置，请先调用 set_root()")
    return _ROOT


def get_config() -> dict[str, Any] | None:
    """获取 leo.config.json 配置，未设置或加载失败返回 None。"""
    return _CONFIG


def get_path(key: str, default: str = "") -> str:
    """从配置中获取路径，配置不存在时返回默认值。"""
    if _CONFIG and "paths" in _CONFIG:
        return _CONFIG["paths"].get(key, default)
    return default


# ============== 跳过配置 ==============

SKIP_DIRS = {
    "scripts", "migrations", ".git", ".obsidian",
    ".workbuddy", "Memory", "Conversation", "Context",
    "_trash", "logs", "Drafts", "templates",
    ".claudian", ".mimocode", ".claude", ".trae-cn",
    ".smart-env", ".vscode", "node_modules",
    "🤖AI_INDEX",
}

SKIP_PATH_PREFIXES: list[str] = []

SKIP_FILENAMES = {"CHANGELOG.md", "AGENTS.md"}

ROOT_NAV_FILES = {
    "README.md", "INDEX.md", "QUICKSTART.md", "AI_INDEX.md",
    "CLAUDE.md", "GEMINI.md", "🤖 AI指令.md",
}

WORKSPACE_KEEP_PATTERNS: tuple[str, ...] = ("AGENTS.md", "🧩 目录")

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# 思维框架维度
FRAMEWORK_DIMENSIONS = ["分析", "决策", "创新", "学习", "沟通", "管理", "名人思维", "积极心理"]


# ============== parse_front_matter ==============

def _parse_inline_list(value: str) -> list | None:
    """解析 YAML 内联数组 `[a, b, c]`。非内联数组返回 None。"""
    v = value.strip()
    if not (v.startswith("[") and v.endswith("]")):
        return None
    inner = v[1:-1].strip()
    if not inner:
        return []
    return [_scalar(item.strip()) for item in inner.split(",")]


def _scalar(value: str) -> Any:
    """把 YAML 标量转成 Python 值。"""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """解析 YAML front matter。返回 (字段字典或None, 错误信息或None)。

    这是唯一权威实现。所有脚本必须 import 此函数，不得自行实现。
    支持两种数组写法：块式（`- item`）与内联式（`[a, b, c]`）。
    """
    if not text.startswith("---"):
        return None, "缺少 front matter（文件应以 --- 开头）"
    match = re.match(r"^---\r?\n(.*?)\r?\n---\s*\r?\n", text, re.DOTALL)
    if not match:
        return None, "front matter 未正确闭合（缺少结尾的 ---）"
    body = match.group(1)
    fields: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                if current_key is not None:
                    if not isinstance(fields.get(current_key), list):
                        fields[current_key] = []
                    fields[current_key].append(_scalar(item))
            elif current_key is not None and stripped:
                existing = fields.get(current_key, "")
                if isinstance(existing, list):
                    continue
                fields[current_key] = (existing + "\n" + stripped).strip() if existing else stripped
            continue
        if ":" not in line:
            return None, f"无法解析的行：{line!r}"
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            current_key = key
            fields[key] = []
        else:
            current_key = key
            inline = _parse_inline_list(value)
            fields[key] = inline if inline is not None else _scalar(value)
    return fields, None


# ============== 文件遍历 ==============

def find_md_files(root: Path | None = None) -> list[Path]:
    """遍历根目录下所有 .md 文件，跳过非数据目录。"""
    if root is None:
        root = get_root()
    result: list[Path] = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(rel_posix.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
            continue
        if path.name in SKIP_FILENAMES:
            continue
        # 保留根目录导航文件用于链接解析，但在某些统计中会跳过
        if path.name.startswith("🧩 目录"):
            continue
        result.append(path)
    return sorted(result, key=lambda p: str(p).lower())


def build_filename_index(files: list[Path], root: Path | None = None) -> dict[str, list[Path]]:
    """构建文件名索引：{stem: [路径列表]}，用于 Obsidian 风格双链解析。"""
    if root is None:
        root = get_root()
    index: dict[str, list[Path]] = {}
    for f in files:
        stem = f.stem
        index.setdefault(stem, []).append(f)
    return index


def resolve_wiki_link(link: str, current_file: Path, filename_index: dict[str, list[Path]]) -> Path | None:
    """解析 [[...]] 双链。Obsidian 语义：纯文件名全局搜索，带路径按相对路径解析。"""
    name = link.split("|")[0].split("#")[0].strip()
    if not name:
        return None
    if "/" in name or "\\" in name:
        # 如果路径以目录名开头（如 "1- 🤖AI 相关/xxx"），从根目录解析
        # 否则从当前文件目录解析相对路径
        root = get_root()
        if "\\" in name:
            name = name.replace("\\", "/")
        if name.startswith("/"):
            target = (root / name[1:]).resolve()
        else:
            # 检查是否是从根目录开始的路径（第一个部分是根目录下的目录）
            first_part = name.split("/")[0]
            if (root / first_part).is_dir():
                target = (root / name).resolve()
            else:
                base = current_file.parent
                target = (base / name).resolve()
        candidates = [target]
        if not name.endswith(".md"):
            candidates.append(target.with_suffix(".md"))
        for cand in candidates:
            if cand.exists() and cand.is_file():
                return cand
        # 如果路径匹配不上，尝试按纯文件名搜索
        # 处理 Windows 反斜杠
        name_clean = name.replace("\\", "/")
        stem = name_clean.split("/")[-1] if "/" in name_clean else name_clean
        stem = stem[:-3] if stem.endswith(".md") else stem
        # 精确匹配
        matches = filename_index.get(stem, [])
        if matches:
            return matches[0]
        # 模糊匹配：查找包含该 stem 部分的文件名
        for key, paths in filename_index.items():
            if stem in key or key in stem:
                return paths[0]
        return None
    stem = name[:-3] if name.endswith(".md") else name
    matches = filename_index.get(stem, [])
    if matches:
        # 如果有多个匹配，优先选择与当前文件同目录或子目录中的文件
        if len(matches) > 1:
            current_dir = current_file.parent
            for match in matches:
                if current_dir in match.parents or match.parent == current_dir:
                    return match
        return matches[0]
    return None


# ============== 框架统计 ==============

def count_framework_files(root: Path | None = None) -> dict[str, int]:
    """统计每个维度的实际框架文件数（排除 🧩 目录、README.md）。"""
    if root is None:
        root = get_root()
    fw_dir = None
    for dim in FRAMEWORK_DIMENSIONS:
        candidate = root / f"7- 🧠思维框架" / dim
        if candidate.exists():
            fw_dir = root / "7- 🧠思维框架"
            break
    if fw_dir is None:
        fw_dir = root / "思维框架"

    counts: dict[str, int] = {}
    for dim in FRAMEWORK_DIMENSIONS:
        dim_dir = fw_dir / dim
        if not dim_dir.exists():
            counts[dim] = 0
            continue
        count = 0
        for f in dim_dir.glob("*.md"):
            if f.name.startswith("🧩") or f.name == "README.md":
                continue
            count += 1
        counts[dim] = count
    return counts

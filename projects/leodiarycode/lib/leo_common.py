"""LeoDiary 公共工具模块

所有脚本共享的函数，消除 lint.py/kb_stats.py 中的重复代码。

函数清单：
    set_root()            — 设置知识库根路径
    get_root()            — 获取知识库根路径
    parse_front_matter()  — 解析 YAML front matter
    resolve_wiki_link()   — 解析 [[双链]]
    find_md_files()       — 遍历知识库 .md 文件
    build_filename_index()— 构建文件名索引
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ROOT: Path | None = None


def set_root(path: str | Path) -> None:
    """设置知识库根路径。"""
    global _ROOT
    _ROOT = Path(path).resolve()


def get_root() -> Path:
    """获取知识库根路径。"""
    if _ROOT is None:
        raise RuntimeError("请先调用 set_root() 设置知识库根路径")
    return _ROOT


# ============== 跳过配置（LeoDiary 专用） ==============

SKIP_DIRS = {
    ".obsidian", ".git", ".trash", ".claude", ".claudian",
    ".smart-env", ".workbuddy", "__pycache__", "node_modules",
    ".qoderworkcn",
    "templates", "Journals",
    "assets", "Canvas", "Clippings", "Excalidraw", "obsidian-index",
    "logs", "_trash",
    "script", "skills",
}

SKIP_DIR_PREFIXES = ("processed-",)

SKIP_FILENAMES = {"CHANGELOG.md", "AGENTS.md", "README.md"}

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


# ============== parse_front_matter ==============

def _scalar(value: str) -> Any:
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
    if not text.startswith("---"):
        return None, "缺少 front matter（文件应以 --- 开头）"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "front matter 未正确闭合（缺少结尾的 ---）"
    body = parts[1]
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
            fields[key] = _scalar(value)
    return fields, None


# ============== 文件遍历 ==============

def find_md_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(rel.as_posix().startswith(prefix) for prefix in SKIP_DIR_PREFIXES):
            continue
        if path.name in SKIP_FILENAMES:
            continue
        result.append(path)
    return sorted(result, key=lambda p: str(p).lower())


def build_filename_index(files: list[Path], root: Path | None = None) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for f in files:
        stem = f.stem
        index.setdefault(stem, []).append(f)
    scan_root = root or get_root()
    for path in scan_root.rglob('*.md'):
        rel = path.relative_to(scan_root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        stem = path.stem
        if stem not in index:
            index.setdefault(stem, []).append(path)
    return index


def resolve_wiki_link(link: str, current_file: Path, filename_index: dict[str, list[Path]]) -> Path | None:
    name = link.split("|")[0].split("#")[0].strip()
    if not name:
        return None
    if "/" in name or "\\" in name:
        base = current_file.parent
        target = (base / name).resolve()
        candidates = [target]
        if not name.endswith(".md"):
            candidates.append(target.with_suffix(".md"))
        for cand in candidates:
            if cand.exists() and cand.is_file():
                return cand
        return None
    stem = name[:-3] if name.endswith(".md") else name
    matches = filename_index.get(stem, [])
    if matches:
        return matches[0]
    return None
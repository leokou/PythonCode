#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian Home 驱动整理工具
===========================
修改了 🏠 home 文件后运行此脚本：
  1. home → 🧩 反向同步（将 home 中的修改写回 🧩 目录文件）
  2. 🧩 目录驱动移动（将链接对应的文件移动到对应文件夹）
  3. 修正标题（确保所有 .md 文件第一行是 "# 文件名"）
"""

import os
import re
import sys
import shutil
import logging
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VAULT_ROOT = Path(r"D:\Obsidian\LeoDiary")

HIDDEN_DIRS = {
    ".obsidian", ".git", ".trash", ".claude", ".claudian",
    ".smart-env", ".workbuddy", "__pycache__", "node_modules",
    ".qoderworkcn", "templates", "Journals",
    "assets", "Canvas", "Clippings", "Excalidraw", "obsidian-index",
}

SKIP_EXTENSIONS = {".pyc", ".pyo"}

logging.basicConfig(level=logging.INFO, format="%(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def build_file_index(vault: Path):
    """构建文件索引。"""
    lower_index = defaultdict(list)
    exact_index = defaultdict(list)
    path_index = {}
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in HIDDEN_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for f in files:
            fp = root_path / f
            if fp.suffix in SKIP_EXTENSIONS:
                continue
            stem = fp.stem
            lower_index[stem.lower()].append(fp)
            exact_index[stem].append(fp)
            try:
                rel = fp.relative_to(vault)
                path_key = str(rel.with_suffix("")).replace("\\", "/")
                path_index[path_key] = fp
            except ValueError:
                pass
    return exact_index, lower_index, path_index


def _find_closest_branch(candidates: list, target_folder: Path):
    """同名文件中选离 target_folder 最近的。"""
    try:
        target_top = target_folder.parts[0] if target_folder.parts else ""
    except Exception:
        return None
    best, best_depth = None, -1
    for c in candidates:
        try:
            c_parts = c.parent.parts
            if not c_parts or c_parts[0] != target_top:
                continue
            depth = 0
            for a, b in zip(target_folder.parts, c_parts):
                if a == b:
                    depth += 1
                else:
                    break
            if depth > best_depth:
                best_depth, best = depth, c
        except Exception:
            continue
    return best


def resolve_link(target_name, exact_index, lower_index, path_index, target_folder=None):
    """解析 wiki 链接为实际文件路径。"""
    if "/" in target_name:
        if target_name in path_index:
            return path_index[target_name], False
        target_name = target_name.rsplit("/", 1)[-1].strip()
        if not target_name:
            return None, False
    if target_name in exact_index:
        candidates = exact_index[target_name]
        if len(candidates) == 1:
            return candidates[0], False
        if target_folder:
            in_folder = [c for c in candidates if c.parent == target_folder]
            if in_folder:
                return in_folder[0], False
            branch = _find_closest_branch(candidates, target_folder)
            if branch:
                return branch, False
        return None, True
    lower_key = target_name.lower()
    if lower_key in lower_index:
        candidates = lower_index[lower_key]
        if len(candidates) == 1:
            return candidates[0], False
        if target_folder:
            in_folder = [c for c in candidates if c.parent == target_folder]
            if in_folder:
                return in_folder[0], False
            branch = _find_closest_branch(candidates, target_folder)
            if branch:
                return branch, False
        return None, True
    return None, False


def parse_wiki_links(content: str):
    """提取所有 [[xxx]] 链接的目标文件名。"""
    targets = []
    for match in _WIKILINK_RE.finditer(content):
        raw = match.group(1).strip()
        raw = raw.split("|")[0].strip()
        raw = raw.split("#")[0].strip()
        if raw:
            targets.append(raw)
    return targets


_BROKEN_LINK_RE = re.compile(r"\[\[[^\]]*(?:\]?[^\]]*)?$")


def find_broken_links(content: str):
    """检测不完整的 wiki 链接（[[xxx] 或 [[xxx 等），返回问题行列表。"""
    problems = []
    for i, line in enumerate(content.splitlines(), 1):
        has_open = "[[" in line
        has_close = "]]" in line
        if has_open and not has_close:
            stripped = line.strip()
            problems.append((i, stripped))
    return problems


def find_dir_files(vault: Path):
    """扫描所有 🧩 目录-*.md 文件。"""
    results = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in HIDDEN_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for f in files:
            if f.startswith("🧩 目录-") and f.endswith(".md"):
                results.append(root_path / f)
    return sorted(results)


# ======================================================================
# Home 文件解析与反向同步
# ======================================================================

def parse_home_sections_content(home_path: Path) -> dict:
    """解析 home 文件，提取所有 🧩 目录模块及其完整内容。"""
    if not home_path.exists():
        return {}
    try:
        content = home_path.read_text(encoding='utf-8')
    except Exception:
        return {}
    sections = {}
    lines = content.splitlines(keepends=True)
    current_stem = None
    current_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') and '🧩 目录-' in stripped:
            if current_stem is not None:
                sections[current_stem] = _trim_section_end(''.join(current_lines))
            current_stem = stripped.lstrip('#').strip()
            current_lines = []
        elif current_stem is not None:
            current_lines.append(line)
    if current_stem is not None:
        sections[current_stem] = _trim_section_end(''.join(current_lines))
    return sections


def _trim_section_end(content: str) -> str:
    """移除末尾的 --- 分隔线和多余空行。"""
    if not content:
        return content
    lines = content.splitlines(keepends=True)
    while lines and lines[-1].strip() == '':
        lines.pop()
    if lines and lines[-1].strip() == '---':
        lines.pop()
        while lines and lines[-1].strip() == '':
            lines.pop()
    result = ''.join(lines)
    if result and not result.endswith('\n'):
        result += '\n'
    return result


def find_chip_file(base_dir: Path, stem: str):
    """在 base_dir 下查找同名 🧩 文件。"""
    best_path, best_links, best_depth = None, -1, float('inf')
    filename = stem + '.md'
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in HIDDEN_DIRS and not d.startswith(".")]
        root_path = Path(root)
        if filename in files:
            current_path = root_path / filename
            try:
                content = current_path.read_text(encoding='utf-8')
                current_links = len(parse_wiki_links(content))
            except Exception:
                continue
            try:
                depth = len(current_path.parent.relative_to(base_dir).parts)
            except ValueError:
                depth = 0
            if best_path is None or current_links > best_links or \
               (current_links == best_links and depth < best_depth):
                best_path, best_links, best_depth = current_path, current_links, depth
    return best_path


def sync_home_to_chips(base_dir: Path) -> int:
    """将 home 文件中各模块的内容反向同步回 🧩 目录文件。"""
    home_path = base_dir / f"🏠 home-{base_dir.name}.md"
    if not home_path.exists():
        return 0
    sections = parse_home_sections_content(home_path)
    if not sections:
        return 0
    synced = 0
    for stem, section_content in sections.items():
        chip_path = find_chip_file(base_dir, stem)
        if chip_path is None:
            continue
        new_content = f"# {stem}\n\n"
        if section_content:
            new_content += section_content
        if not new_content.endswith('\n'):
            new_content += '\n'
        try:
            old_content = chip_path.read_text(encoding='utf-8')
            if old_content == new_content:
                continue
            chip_path.write_text(new_content, encoding='utf-8')
            log.info(f"  🔄 已同步：{chip_path.relative_to(base_dir)}")
            synced += 1
        except Exception as e:
            log.warning(f"  ⚠️  写入失败 {chip_path} - {e}")
    return synced


# ======================================================================
# 🧩 目录文件同步（移动后更新两边）
# ======================================================================

def sync_chip_on_move(source_folder: Path, target_folder: Path, link_name: str):
    """文件移动后，同步更新源/目标 🧩 目录文件。"""
    src_chip = source_folder / f"🧩 目录-{source_folder.name}.md"
    if src_chip.exists():
        try:
            lines = src_chip.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines, removed = [], False
            for line in lines:
                if f"[[{link_name}]]" in line:
                    removed = True
                    continue
                new_lines.append(line)
            if removed:
                src_chip.write_text("".join(new_lines), encoding="utf-8")
        except Exception:
            pass
    dst_chip = target_folder / f"🧩 目录-{target_folder.name}.md"
    if dst_chip.exists():
        try:
            content = dst_chip.read_text(encoding="utf-8")
            if f"[[{link_name}]]" not in content:
                needs_nl = not content.endswith("\n") if content else True
                with open(dst_chip, "a", encoding="utf-8") as f:
                    if needs_nl:
                        f.write("\n")
                    f.write(f"[[{link_name}]]\n")
        except Exception:
            pass


# ======================================================================
# 标题修正
# ======================================================================

def ensure_title_header(file_path: Path):
    """确保 .md 文件第一行是 "# 文件名"。"""
    expected = f"# {file_path.stem}"
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not content.strip():
        new_content = expected + "\n"
    else:
        lines = content.splitlines(keepends=True)
        first_line = lines[0].rstrip("\r\n") if lines else ""
        if first_line.strip() == expected:
            return False
        if first_line.startswith("# "):
            nl = "\n" if ("\n" in lines[0] or "\r" in lines[0]) else ""
            lines[0] = expected + nl
            new_content = "".join(lines)
        else:
            new_content = expected + "\n\n" + content
    try:
        file_path.write_text(new_content, encoding="utf-8")
        log.info(f"   🏷️  修正标题: {file_path.name} → '{expected}'")
    except Exception:
        return False
    return True


def ensure_all_titles(vault: Path) -> int:
    """遍历所有 .md 文件修正标题。"""
    fixed = 0
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in HIDDEN_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for f in files:
            if not f.endswith(".md"):
                continue
            if f.startswith("🧩 目录-") or f.startswith("🏠 home-") or f == "🤖 AI指令.md":
                continue
            if ensure_title_header(root_path / f):
                fixed += 1
    return fixed


# ======================================================================
# 主逻辑
# ======================================================================

def main():
    log.info(f"{'='*60}")
    log.info(f"📥 Home 驱动整理（修改了 home 文件后运行）")
    log.info(f"Vault: {VAULT_ROOT}")
    log.info(f"{'='*60}\n")

    # ── 1. 反向同步（home → 🧩）──
    log.info("📥 第 1 步：home → 🧩 反向同步...")
    home_dirs = [d for d in VAULT_ROOT.iterdir()
                 if d.is_dir() and d.name not in HIDDEN_DIRS and not d.name.startswith(".")]
    total_synced = 0
    for subdir in home_dirs:
        if (subdir / f"🏠 home-{subdir.name}.md").exists():
            synced = sync_home_to_chips(subdir)
            if synced > 0:
                log.info(f"🏠 {subdir.name} : 已同步 {synced} 个模块")
            total_synced += synced
    if total_synced == 0:
        log.info("   无变化")
    log.info("")

    # ── 2. 🧩 目录驱动移动 ──
    log.info("📂 第 2 步：🧩 目录驱动移动...")
    dir_files = find_dir_files(VAULT_ROOT)
    log.info(f"   找到 {len(dir_files)} 个 🧩 目录文件")
    exact_index, lower_index, path_index = build_file_index(VAULT_ROOT)
    log.info(f"   文件索引: {sum(len(v) for v in exact_index.values())} 个文件\n")

    stats = {"links_total": 0, "already_in_place": 0, "moved": 0, "not_found": 0, "conflict": 0}
    broken_count = 0
    for dir_file in dir_files:
        target_folder = dir_file.parent
        content = dir_file.read_text(encoding="utf-8")
        broken = find_broken_links(content)
        if broken:
            broken_count += len(broken)
            log.warning(f"⚠️  {dir_file.relative_to(VAULT_ROOT)} 有 {len(broken)} 个不完整链接:")
            for line_no, line_text in broken[:5]:
                log.warning(f"   第 {line_no} 行: {line_text}")
            if len(broken) > 5:
                log.warning(f"   ... 还有 {len(broken) - 5} 个")
        links = parse_wiki_links(content)
        if not links:
            continue
        log.info(f"── {dir_file.relative_to(VAULT_ROOT)} ──")
        for link_name in links:
            stats["links_total"] += 1
            if link_name == dir_file.stem:
                continue
            resolved, _ = resolve_link(link_name, exact_index, lower_index, path_index, target_folder)
            if resolved is None:
                stats["not_found"] += 1
                continue
            if resolved.parent == target_folder:
                stats["already_in_place"] += 1
                continue
            dest = target_folder / resolved.name
            if dest.exists() and dest != resolved:
                stats["conflict"] += 1
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(resolved), str(dest))
                log.info(f"   ✅ [[{link_name}]] → {resolved.relative_to(VAULT_ROOT)} ⇒ {dest.relative_to(VAULT_ROOT)}")
                stats["moved"] += 1
                sync_chip_on_move(resolved.parent, target_folder, link_name)
            except Exception as e:
                log.error(f"   ❌ [[{link_name}]] → {e}")
        log.info("")

    log.info(f"📊 移动: 已在目标 {stats['already_in_place']}, 已移动 {stats['moved']}, "
             f"未找到 {stats['not_found']}, 冲突 {stats['conflict']}\n")

    # ── 3. 修正标题 ──
    log.info("🏷️  第 3 步：修正标题...")
    title_fixed = ensure_all_titles(VAULT_ROOT)
    log.info(f"   修正了 {title_fixed} 个文件\n")

    log.info(f"{'='*60}")
    log.info(f"📊 反向同步: {total_synced} | 移动: {stats['moved']} | 标题: {title_fixed}")
    log.info(f"🎉 整理完成！")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()

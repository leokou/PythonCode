#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 目录驱动整理工具
===========================
修改了 🧩 目录文件后运行此脚本：
  1. 🧩 目录驱动移动（将链接对应的文件移动到对应文件夹）
  2. 重建所有 home（从 🧩 文件重新生成 home，同步到 home）
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
# Home 文件重建（🧩 → home）
# ======================================================================

def rebuild_home_from_chips(home_path: Path, base_dir: Path) -> int:
    """
    重建 home 文件：按顺序将每个 🧩 文件包装为分模块展示。
    同名 🧩 文件去重：链接数多的胜出，相同时层级浅的胜出。
    """
    chip_dict = {}
    for sub in base_dir.iterdir():
        if not sub.is_dir() or sub.name in HIDDEN_DIRS or sub.name.startswith("."):
            continue
        for root, dirs, files in os.walk(sub):
            dirs[:] = [d for d in dirs if d not in HIDDEN_DIRS and not d.startswith(".")]
            root_path = Path(root)
            for file in files:
                if file.startswith("🧩 目录-") and file.endswith(".md"):
                    stem = file[:-3]
                    current_path = root_path / file
                    if stem not in chip_dict:
                        chip_dict[stem] = current_path
                        continue
                    existing_path = chip_dict[stem]
                    try:
                        existing_content = existing_path.read_text(encoding="utf-8")
                        current_content = current_path.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    existing_links = len(parse_wiki_links(existing_content))
                    current_links = len(parse_wiki_links(current_content))
                    if current_links > existing_links:
                        chip_dict[stem] = current_path
                    elif current_links == existing_links:
                        try:
                            existing_depth = len(existing_path.parent.relative_to(base_dir).parts)
                            current_depth = len(current_path.parent.relative_to(base_dir).parts)
                            if current_depth < existing_depth:
                                chip_dict[stem] = current_path
                        except ValueError:
                            pass

    chip_files = list(chip_dict.values())
    chip_files.sort(key=lambda p: (str(p.parent), p.name))

    if not chip_files:
        home_path.write_text('', encoding='utf-8')
        return 0

    lines = []
    for chip_path in chip_files:
        try:
            rel = chip_path.parent.relative_to(base_dir)
            level = len(rel.parts) + 1
        except ValueError:
            level = 2
        heading = "#" * level
        lines.append(f"{heading} {chip_path.stem}\n")

        try:
            content = chip_path.read_text(encoding='utf-8')
            if content:
                content_lines = content.splitlines(keepends=True)
                if content_lines and content_lines[0].lstrip().startswith("# "):
                    content_lines = content_lines[1:]
                    while content_lines and content_lines[0].strip() == "":
                        content_lines = content_lines[1:]
                content = "".join(content_lines)
            lines.append(content)
            if content and not content.endswith('\n'):
                lines.append('\n')
        except Exception as e:
            log.warning(f"  ⚠️  读取 {chip_path} 失败 - {e}")
            lines.append(f"\n*（读取失败）*\n")

        lines.append('\n---\n\n')

    final_content = ''.join(lines)
    if not final_content.endswith('\n'):
        final_content += '\n'

    try:
        home_path.write_text(final_content, encoding='utf-8')
    except Exception as e:
        log.warning(f"  ⚠️  写入 home 失败 {home_path} - {e}")
        return 0
    return len(chip_files)


def rebuild_all_homes(vault: Path) -> int:
    """重建所有一级目录的 home 文件。"""
    count = 0
    for entry in vault.iterdir():
        if not entry.is_dir() or entry.name in HIDDEN_DIRS or entry.name.startswith("."):
            continue
        home_path = entry / f"🏠 home-{entry.name}.md"
        if not home_path.exists():
            continue
        chip_count = rebuild_home_from_chips(home_path, entry)
        log.info(f"   🏠 {entry.name} : 已重建（{chip_count} 个模块）")
        count += 1
    return count


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
    log.info(f"📂 目录驱动整理（修改了 🧩 目录文件后运行）")
    log.info(f"Vault: {VAULT_ROOT}")
    log.info(f"{'='*60}\n")

    # ── 1. 🧩 目录驱动移动 ──
    log.info("📂 第 1 步：🧩 目录驱动移动...")
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

    # ── 2. 重建所有 home ──
    log.info("🏠 第 2 步：重建所有 home 文件（从 🧩 文件重新生成）...")
    home_count = rebuild_all_homes(VAULT_ROOT)
    log.info(f"   重建了 {home_count} 个 home 文件\n")

    # ── 3. 修正标题 ──
    log.info("🏷️  第 3 步：修正标题...")
    title_fixed = ensure_all_titles(VAULT_ROOT)
    log.info(f"   修正了 {title_fixed} 个文件\n")

    log.info(f"{'='*60}")
    log.info(f"📊 移动: {stats['moved']} | 重建home: {home_count} | 标题: {title_fixed}")
    log.info(f"🎉 整理完成！")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 索引文件自动管理工具
- 生成/更新 🤖 AI指令.md（根/一级/二级，不存在则创建空文件）
- 一级目录：🏠 home-文件夹名.md
    - 完全重建：按子目录中所有 🧩 目录-*.md 文件分模块展示
    - 每个模块：## 文件名 + 空行 + 文件原内容 + 空行 + --- + 空行
- 二至五级目录：🧩 目录-文件夹名.md
    - 不存在则创建空文件
    - 存在时：仅删除失效链接行，追加新链接到末尾（不改变顺序和其他内容）
"""

import sys
import os
from pathlib import Path
from typing import Set, List

# 设置标准输出和标准错误为UTF-8编码，解决Windows环境下emoji输出问题
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 白名单文件夹（完全跳过，不进入也不处理）
SKIP_DIRS = {
    'assets', 'Canvas', 'Clippings', 'Excalidraw', 'Journals',
    'obsidian-index', 'templates', '.claude', '.claudian',
    '.obsidian', '.smart-env', '.trash'
}

MAX_DEPTH = 5


def get_relative_level(base_path: Path, subdir_path: Path) -> int:
    """计算子目录相对于基准目录的层级（从1开始）"""
    try:
        rel = subdir_path.relative_to(base_path)
        return len(rel.parts) + 1
    except ValueError:
        return 0


def scan_md_files(dir_path: Path, index_filename: str) -> Set[str]:
    """扫描目录下所有直接 .md 文件（排除索引文件自身），返回文件名（不含扩展名）集合"""
    md_files = set()
    try:
        for entry in dir_path.iterdir():
            if entry.is_file() and entry.suffix.lower() == '.md':
                if entry.name != index_filename:
                    md_files.add(entry.stem)
    except PermissionError:
        print(f"  警告：无法读取目录 {dir_path}，权限不足")
    return md_files


def extract_links_from_content(content: str) -> Set[str]:
    """从文件内容中提取所有 [[xxx]] 中的 xxx"""
    links = set()
    start = 0
    while True:
        pos1 = content.find('[[', start)
        if pos1 == -1:
            break
        pos2 = content.find(']]', pos1 + 2)
        if pos2 == -1:
            break
        link = content[pos1+2:pos2].strip()
        if link:
            links.add(link)
        start = pos2 + 2
    return links


def remove_stale_links(index_path: Path, actual_files: Set[str]) -> int:
    """
    从索引文件中删除所有对应文件已不存在的 [[链接]] 行。
    保留所有其他行（空行、注释、自定义文字等）的原有顺序和内容。
    返回删除的行数。
    """
    if not index_path.exists():
        return 0
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  警告：读取索引文件失败 {index_path} - {e}")
        return 0

    new_lines = []
    removed_count = 0
    for line in lines:
        start = line.find('[[')
        if start != -1:
            end = line.find(']]', start + 2)
            if end != -1:
                link_text = line[start+2:end].strip()
                if link_text and link_text not in actual_files:
                    removed_count += 1
                    continue
        new_lines.append(line)

    if removed_count > 0:
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"  错误：无法写入索引文件 {index_path} - {e}")
            return 0
    return removed_count


def append_new_links_to_end(index_path: Path, new_links: List[str]) -> int:
    """
    将新链接追加到文件末尾（每行一个 [[xxx]]）。
    如果文件末尾没有换行，则自动添加一个换行后再追加。
    返回成功追加的链接数量。
    """
    if not new_links:
        return 0
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        needs_newline = not content.endswith('\n') if content else True
        with open(index_path, 'a', encoding='utf-8') as f:
            if needs_newline:
                f.write('\n')
            for link in new_links:
                f.write(f"[[{link}]]\n")
    except Exception as e:
        print(f"  错误：无法追加链接到 {index_path} - {e}")
        return 0
    return len(new_links)


def ensure_ai_instruction_file(dir_path: Path) -> None:
    """在指定目录下创建 🤖 AI指令.md（如果不存在）"""
    ai_file = dir_path / "🤖 AI指令.md"
    if not ai_file.exists():
        ai_file.touch()
        print(f"🤖 已创建：{ai_file}")


def process_directory(dir_path: Path, level: int, base_path: Path, use_chip_for_level1: bool = False) -> dict:
    """
    处理单个目录（用于递归遍历）：
    - 一级、二级目录：确保 🤖 AI指令.md 存在
    - 一级目录：默认仅确保 home 文件存在（稍后完全重建），use_chip_for_level1=True时生成 🧩 文件
    - 二级及以上目录：删除失效链接 + 追加新链接
    """
    folder_name = dir_path.name

    if level == 1 or level == 2:
        ensure_ai_instruction_file(dir_path)

    if level == 1 and not use_chip_for_level1:
        index_name = f"🏠 home-{folder_name}.md"
        index_path = dir_path / index_name
        if not index_path.exists():
            index_path.touch()
            print(f"  ✨ 创建空 home 文件：{index_path.name}")
        return {'removed': 0, 'added': 0}

    # 一级（use_chip_for_level1=True）及以上目录：处理 🧩 文件
    index_name = f"🧩 目录-{folder_name}.md"
    index_path = dir_path / index_name

    if not index_path.exists():
        index_path.touch()
        print(f"  ✨ 创建空 🧩 索引文件：{index_path.name}")

    # 获取当前目录下所有 .md 文件（排除索引文件和AI指令文件）
    actual_files = scan_md_files(dir_path, index_name)
    # 添加 AI 指令文件到实际文件列表
    ai_file = dir_path / "🤖 AI指令.md"
    if ai_file.exists():
        actual_files.add("🤖 AI指令")
    
    removed = remove_stale_links(index_path, actual_files)

    try:
        current_content = index_path.read_text(encoding='utf-8')
        existing_links = extract_links_from_content(current_content)
    except Exception as e:
        print(f"  警告：无法读取索引文件内容 - {e}")
        existing_links = set()

    new_files = actual_files - existing_links
    added = append_new_links_to_end(index_path, sorted(new_files))

    return {'removed': removed, 'added': added}


def walk_and_process(start_dir: Path, target_dir: Path) -> None:
    """递归遍历目标目录下的子目录，更新 🧩 文件并创建空 home"""
    try:
        entries = list(start_dir.iterdir())
    except PermissionError:
        print(f"无法访问目录：{start_dir}")
        return

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS or entry.name.startswith("."):
            print(f"⏭️  跳过目录：{entry}")
            continue

        level = get_relative_level(target_dir, entry)
        if level == 0 or level > MAX_DEPTH:
            continue

        stats = process_directory(entry, level, target_dir)
        rel_path = entry.relative_to(target_dir)

        msg_parts = []
        if stats['removed'] > 0:
            msg_parts.append(f"删除了 {stats['removed']} 个失效链接")
        if stats['added'] > 0:
            msg_parts.append(f"新增了 {stats['added']} 个链接")
        if msg_parts:
            print(f"📄 {rel_path} : {'，'.join(msg_parts)}")
        elif level != 1:
            print(f"✅ {rel_path} : 无变化")

        walk_and_process(entry, target_dir)


def rebuild_home_from_chips(home_path: Path, base_dir: Path) -> int:
    """
    重建 home 文件：按顺序将每个 🧩 文件包装为：
    # 文件名（不含 .md）
    （空行）
    原文件内容（去掉第一行 # 标题）
    （空行）
    ---
    （空行）
    返回处理的文件数量。
    """
    chip_files = []
    # 遍历 base_dir 下的所有子目录（二级及更深）
    for sub in base_dir.iterdir():
        if not sub.is_dir() or sub.name in SKIP_DIRS or sub.name.startswith("."):
            continue
        for root, dirs, files in os.walk(sub):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            root_path = Path(root)
            for file in files:
                if file.startswith("🧩 目录-") and file.endswith(".md"):
                    chip_files.append(root_path / file)

    # 按目录层级排序：父目录的 🧩 文件排在前面，子目录的排在后面
    # 排序键：父目录路径（确保父目录内容在子目录前），然后是文件名
    def sort_key(p):
        try:
            rel = p.parent.relative_to(base_dir)
            return (str(rel), p.name)
        except ValueError:
            return ("", p.name)
    chip_files.sort(key=sort_key)

    if not chip_files:
        # 没有 🧩 文件时清空 home 文件
        home_path.write_text('', encoding='utf-8')
        return 0

    lines = []
    for chip_path in chip_files:
        # 一级标题：文件名（去掉 .md），标题后空一行
        title = f"# {chip_path.stem}\n"
        lines.append(title)

        try:
            content = chip_path.read_text(encoding='utf-8')
            # 去掉第一行 # 标题（避免重复）
            if content:
                content_lines = content.splitlines(keepends=True)
                if content_lines and content_lines[0].lstrip().startswith("# "):
                    content_lines = content_lines[1:]
                    # 去掉标题后紧接着的空行
                    while content_lines and content_lines[0].strip() == "":
                        content_lines = content_lines[1:]
                content = "".join(content_lines)
            lines.append(content)
            # 确保内容末尾有换行（如果原文件没有则添加）
            if content and not content.endswith('\n'):
                lines.append('\n')
        except Exception as e:
            print(f"  警告：读取 {chip_path} 失败 - {e}")
            lines.append(f"\n*（读取失败）*\n")

        # 横线前后各空一行
        lines.append('\n---\n\n')

    # 最终内容末尾确保有换行
    final_content = ''.join(lines)
    if not final_content.endswith('\n'):
        final_content += '\n'

    try:
        home_path.write_text(final_content, encoding='utf-8')
    except Exception as e:
        print(f"  错误：写入 home 文件失败 {home_path} - {e}")
        return 0

    return len(chip_files)


def aggregate_and_update_home(target_dir: Path, root_dirs: List[Path]) -> None:
    """为每个一级子目录重建 home 文件（分模块展示）"""
    for subdir in root_dirs:
        home_name = f"🏠 home-{subdir.name}.md"
        home_path = subdir / home_name
        chip_count = rebuild_home_from_chips(home_path, subdir)
        rel_path = subdir.relative_to(target_dir)
        print(f"🏠 {rel_path} : 已重建 home（包含 {chip_count} 个模块）")


def process_root_and_para_dirs(target_dir: Path) -> None:
    """处理根目录和PARA文件夹：生成🧩目录文件而非home文件"""
    # PARA文件夹列表
    PARA_DIRS = {'A📥 收集（Capture）', 'B🧹 整理（Organize）', 'C⚙️ 处理（Process）', 'D📦 归档（Archive）'}
    
    # 处理根目录：生成 🧩 目录文件
    print(f"📁 根目录 : 生成 🧩 目录文件...")
    stats = process_directory(target_dir, level=1, base_path=target_dir, use_chip_for_level1=True)
    
    # 删除根目录下的旧home文件（如果存在）
    old_home = target_dir / f"🏠 home-{target_dir.name}.md"
    if old_home.exists():
        old_home.unlink()
        print(f"  🗑️ 删除旧 home 文件：{old_home.name}")
    
    # 遍历一级子目录，对PARA文件夹使用🧩目录逻辑
    for subdir in target_dir.iterdir():
        if not subdir.is_dir() or subdir.name in SKIP_DIRS or subdir.name.startswith("."):
            continue
            
        if subdir.name in PARA_DIRS:
            print(f"📁 {subdir.name} : 生成 🧩 目录文件（PARA文件夹）...")
            stats = process_directory(subdir, level=1, base_path=target_dir, use_chip_for_level1=True)
            
            # 删除PARA文件夹下的旧home文件（如果存在）
            old_home = subdir / f"🏠 home-{subdir.name}.md"
            if old_home.exists():
                old_home.unlink()
                print(f"  🗑️ 删除旧 home 文件：{old_home.name}")
            
            # 递归处理PARA文件夹的子目录
            walk_and_process(subdir, target_dir)


def main():
    # 默认使用固定目录 D:\Obsidian\LeoDiary（根据项目配置）
    DEFAULT_DIR = Path(r"D:\Obsidian\LeoDiary")
    
    if len(sys.argv) > 1:
        target = Path(sys.argv[1]).resolve()
        if not target.exists() or not target.is_dir():
            print(f"错误：指定的目录不存在或不是文件夹：{target}")
            sys.exit(1)
    else:
        target = DEFAULT_DIR
        if not target.exists() or not target.is_dir():
            print(f"错误：默认目录不存在或不是文件夹：{target}")
            sys.exit(1)

    print(f"🎯 目标目录：{target}")
    print(f"📏 最大索引深度：{MAX_DEPTH} 级")
    print(f"🚫 跳过白名单：{', '.join(sorted(SKIP_DIRS))}")
    print("-" * 60)

    # 目标根目录创建 AI 指令文件（如果不存在）
    ensure_ai_instruction_file(target)

    # 获取目标目录下的一级子目录
    root_dirs = [d for d in target.iterdir() if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")]
    if not root_dirs:
        print("⚠️ 目标目录下没有可处理的子目录。")
        return

    # PARA文件夹列表
    PARA_DIRS = {'A📥 收集（Capture）', 'B🧹 整理（Organize）', 'C⚙️ 处理（Process）', 'D📦 归档（Archive）'}
    
    # 第一阶段：处理根目录和PARA文件夹（生成🧩），处理其他一级目录（生成home）
    for subdir in root_dirs:
        print(f"📁 {subdir.relative_to(target)} : 处理子目录索引...")
        if subdir.name in PARA_DIRS:
            # 先删除旧home文件（如果存在），再处理目录
            old_home = subdir / f"🏠 home-{subdir.name}.md"
            if old_home.exists():
                old_home.unlink()
                print(f"  🗑️ 删除旧 home 文件：{old_home.name}")
            process_directory(subdir, level=1, base_path=target, use_chip_for_level1=True)
        else:
            process_directory(subdir, level=1, base_path=target)
        walk_and_process(subdir, target)
    
    # 处理根目录自身（生成🧩）
    print(f"📁 根目录 : 生成 🧩 目录文件...")
    # 先删除旧home文件（如果存在），再处理目录
    old_home = target / f"🏠 home-{target.name}.md"
    if old_home.exists():
        old_home.unlink()
        print(f"  🗑️ 删除旧 home 文件：{old_home.name}")
    process_directory(target, level=1, base_path=target, use_chip_for_level1=True)

    print("-" * 60)
    print("🔄 开始重建一级目录的 home 索引（分模块展示）...")

    # 第二阶段：仅为非PARA文件夹重建 home 文件
    non_para_dirs = [d for d in root_dirs if d.name not in PARA_DIRS]
    aggregate_and_update_home(target, non_para_dirs)

    print("-" * 60)
    print("🎉 索引更新完成！")


if __name__ == "__main__":
    main()
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
    - 存在时：仅删除失效链接行（不再追加新链接，新增文件由Skill处理）
"""

import sys
import os
import re
from pathlib import Path
from typing import Set, List

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from obsidian_common import (
    VAULT_ROOT, SKIP_DIRS, SKIP_FILES_PREFIX, SKIP_FILES_EXACT,
    PARA_DIRS, should_skip_dir, should_skip_file, strip_frontmatter, read_text_safe,
)

MAX_DEPTH = 5

# 高频领域（手动置顶，排在快速定位表前面）
PRIORITY_DOMAINS = ["1- 🤖AI 相关", "5- 🧁项目"]

# 访问频率文件路径（相对vault根目录）
ACCESS_FREQ_FILE = "logs/index/access-frequency.json"

# 快速定位表每个领域取几个文件
QUICK_JUMP_PER_DOMAIN = 2

# 快速定位表最大条数
QUICK_JUMP_MAX = 25


def load_access_frequency(vault_root: Path) -> dict:
    """加载访问频率数据，返回 {文件路径: {count, last_time}}"""
    freq_path = vault_root / ACCESS_FREQ_FILE
    if not freq_path.exists():
        return {}
    try:
        import json
        with open(freq_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_access_frequency(vault_root: Path, freq_data: dict) -> None:
    """保存访问频率数据"""
    freq_path = vault_root / ACCESS_FREQ_FILE
    freq_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import json
        with open(freq_path, 'w', encoding='utf-8') as f:
            json.dump(freq_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  警告：保存访问频率失败 - {e}")


def record_file_access(vault_root: Path, file_path: str) -> None:
    """记录一次文件访问（供Skill调用）"""
    freq_data = load_access_frequency(vault_root)
    now = __import__('datetime').datetime.now().isoformat()
    if file_path in freq_data:
        freq_data[file_path]['count'] = freq_data[file_path].get('count', 0) + 1
        freq_data[file_path]['last_time'] = now
    else:
        freq_data[file_path] = {'count': 1, 'last_time': now}
    save_access_frequency(vault_root, freq_data)


def get_file_access_count(freq_data: dict, file_key: str) -> int:
    """获取文件的访问次数，没有则返回0"""
    if file_key in freq_data:
        return freq_data[file_key].get('count', 0)
    # 尝试用文件名匹配（不含路径）
    pure_name = file_key.split('\\')[-1].split('/')[-1]
    for k, v in freq_data.items():
        if k.endswith(pure_name) or k.endswith('\\' + pure_name):
            return v.get('count', 0)
    return 0


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


def extract_all_links(index_path: Path) -> Set[str]:
    """从索引文件全文提取所有 [[链接]]（不管在哪个区域）。"""
    if not index_path.exists():
        return set()
    try:
        content = index_path.read_text(encoding='utf-8')
    except Exception:
        return set()
    return extract_links_from_content(content)


def extract_summaries_from_chip_files(target_dir: Path) -> dict:
    """
    从所有🧩目录文件中提取 [[链接]] 后面的 ✍️ 摘要文本。
    返回字典：key=纯文件名（不含路径），value=✍️摘要文本（包含✍️符号）
    """
    summaries = {}
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for f in files:
            if f.startswith("🧩 目录-") and f.endswith(".md"):
                chip_path = Path(root) / f
                try:
                    content = read_text_safe(chip_path)
                    content = strip_frontmatter(content)
                    for line in content.splitlines():
                        match = re.search(r'\[\[([^\]]+)\]\]\s*(✍️.*)', line)
                        if match:
                            link_name = match.group(1).strip()
                            summary_text = match.group(2).strip()
                            pure_name = link_name.replace('\\', '/').split('/')[-1]
                            if pure_name and summary_text and pure_name not in summaries:
                                summaries[pure_name] = summary_text
                except Exception:
                    pass
    return summaries


def extract_summaries_from_skill_dirs() -> dict:
    """
    从 C:\\Users\\leokou\\.claude\\skills 下各 skill 的 SKILL.md 中提取 description 作为摘要。
    返回字典：key=skill名（如 obsidian-pipeline），value=✍️摘要文本
    """
    summaries = {}
    skill_base = Path(r"C:\Users\leokou\.claude\skills")
    if not skill_base.exists():
        return summaries
    
    def _parse_frontmatter_description(content: str) -> str:
        """从 SKILL.md 的 frontmatter 中提取 description 字段"""
        if not content.startswith('---'):
            return ""
        end = content.find('---', 3)
        if end == -1:
            return ""
        fm = content[3:end]
        for line in fm.splitlines():
            line = line.strip()
            if line.startswith('description:'):
                desc = line[len('description:'):].strip()
                if desc.startswith('"') and desc.endswith('"'):
                    desc = desc[1:-1]
                return desc
        return ""
    
    skill_dirs_to_scan = ["Obsidian"]
    
    for sub_dir_name in skill_dirs_to_scan:
        sub_dir = skill_base / sub_dir_name
        if not sub_dir.exists() or not sub_dir.is_dir():
            continue
        for entry in sub_dir.iterdir():
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = read_text_safe(skill_md)
                desc = _parse_frontmatter_description(content)
                if desc:
                    skill_name = entry.name
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    summaries[skill_name] = f"✍️ {desc}"
            except Exception:
                pass
    
    return summaries


def remove_stale_links(index_path: Path, actual_files: Set[str]) -> int:
    """
    从索引文件全文删除失效链接所在的行。
    只删除包含 [[失效链接]] 的行，保留其他所有内容（分类标题、说明文字等）。
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

    kept_lines = []
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
        kept_lines.append(line)

    if removed_count > 0:
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                f.writelines(kept_lines)
        except Exception as e:
            print(f"  错误：无法写入索引文件 {index_path} - {e}")
            return 0
    return removed_count


def append_new_links_to_end(index_path: Path, new_links: List[str]) -> int:
    """
    将新链接直接追加到文件末尾。
    如果文件已有内容，先确保末尾有空行。
    返回成功追加的链接数量。
    """
    if not new_links:
        return 0
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    except Exception as e:
        print(f"  错误：无法读取 {index_path} - {e}")
        return 0

    existing_links = extract_all_links(index_path)

    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    if lines and lines[-1].strip() != '':
        lines.append('\n')

    added = 0
    for link in new_links:
        if link not in existing_links:
            lines.append(f"[[{link}]]\n")
            added += 1

    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"  错误：无法写入 {index_path} - {e}")
        return 0
    return added


def append_new_links_to_default_category(index_path: Path, new_links: List[str]) -> int:
    """
    将新链接追加到默认分类（## � 待归类）下。
    如果该分类不存在，在文件末尾创建。
    返回成功追加的链接数量。
    """
    if not new_links:
        return 0
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines(keepends=True)
    except FileNotFoundError:
        lines = []
    except Exception as e:
        print(f"  错误：无法读取 {index_path} - {e}")
        return 0

    existing_links = extract_all_links(index_path)

    default_category_header = "##### 📥 待归类\n"
    category_found = False
    insert_pos = -1
    added = 0

    for i, line in enumerate(lines):
        if line.strip() == "##### 📥 待归类":
            category_found = True
            insert_pos = i + 1
            while insert_pos < len(lines) and lines[insert_pos].strip().startswith('- [['):
                insert_pos += 1
            break

    new_link_lines = []
    for link in new_links:
        if link not in existing_links:
            new_link_lines.append(f"- [[{link}]]\n")
            added += 1

    if added == 0:
        return 0

    if not category_found:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        if lines and lines[-1].strip() != '':
            lines.append('\n')
        lines.append(default_category_header)
        lines.extend(new_link_lines)
    else:
        for j, line in enumerate(new_link_lines):
            lines.insert(insert_pos + j, line)

    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"  错误：无法写入 {index_path} - {e}")
        return 0
    return added


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

    # 找出新增文件，追加到默认分类（##### 📥 待归类）
    existing_links = extract_all_links(index_path)
    new_files = sorted(actual_files - existing_links)
    # 排除AI指令文件（不放入待归类）
    new_files = [f for f in new_files if f != "🤖 AI指令"]
    added = append_new_links_to_default_category(index_path, new_files)

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
        if should_skip_dir(entry.name):
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
    保留用户在 home 文件 [[链接]] 后手动添加的注释。
    """
    # 先读取旧home文件中的用户注释
    old_annotations = {}
    if home_path.exists():
        try:
            old_content = home_path.read_text(encoding='utf-8')
            for line in old_content.splitlines():
                match = re.search(r'\[\[([^\]]+)\]\](.*)', line)
                if match:
                    link_name = match.group(1).strip()
                    user_text = match.group(2).strip()
                    if user_text:
                        pure_name = link_name.replace('\\', '/').split('/')[-1]
                        old_annotations[pure_name] = user_text
        except Exception:
            pass
    
    chip_files = []
    # 遍历 base_dir 下的所有子目录（二级及更深）
    for sub in base_dir.iterdir():
        if not sub.is_dir() or should_skip_dir(sub.name):
            continue
        for root, dirs, files in os.walk(sub):
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
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
        if home_path.exists():
            try:
                existing = home_path.read_text(encoding='utf-8')
                if existing == '':
                    return 0
            except Exception:
                pass
        home_path.write_text('', encoding='utf-8')
        return 0

    lines = []
    for chip_path in chip_files:
        # 一级标题：文件名（去掉 .md），标题后空一行
        title = f"# {chip_path.stem}\n"
        lines.append(title)

        try:
            content = read_text_safe(chip_path)
            # 先去除frontmatter（skill生成的🧩文件可能包含）
            content = strip_frontmatter(content)
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
    
    # 合并用户注释（以home文件中的旧注释为准）
    if old_annotations:
        new_lines = []
        for line in final_content.splitlines(keepends=True):
            match = re.search(r'\[\[([^\]]+)\]\](.*)', line)
            if match:
                link_name = match.group(1).strip()
                existing_text = match.group(2).strip()
                pure_name = link_name.replace('\\', '/').split('/')[-1]
                if pure_name in old_annotations and existing_text != old_annotations[pure_name]:
                    # 用旧home文件中的注释替换
                    line = re.sub(r'(\[\[[^\]]+\]\])(.*)', 
                                  lambda m: m.group(1) + ' ' + old_annotations[pure_name], 
                                  line.rstrip('\r\n')) + '\n'
            new_lines.append(line)
        final_content = ''.join(new_lines)

    try:
        if home_path.exists():
            old_content = home_path.read_text(encoding='utf-8')
            if old_content == final_content:
                return len(chip_files)
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


def _collect_dir_files(target_dir: Path, sub_dir: Path, link_annotations: dict,
                       skill_summaries: dict, chip_summaries: dict) -> tuple:
    """
    收集某个一级目录下的所有文件和目录信息，用于生成二级索引。
    返回 (dir_count, file_count, tree_lines, all_files_list)
    all_files_list: [(rel_path_from_subdir, file_stem, annotation), ...]
    """
    def _get_annotation(link_key: str, fallback_stem: str = "") -> str:
        if link_key in link_annotations:
            return link_annotations[link_key]
        if fallback_stem and fallback_stem in link_annotations:
            return link_annotations[fallback_stem]
        if fallback_stem:
            for skill_name, summary in skill_summaries.items():
                if skill_name.lower() in fallback_stem.lower():
                    return summary
        return ""

    dir_count = 0
    file_count = 0
    tree_lines = []
    all_files = []

    for root, dirs, files in os.walk(sub_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        root_path = Path(root)
        try:
            rel = root_path.relative_to(sub_dir)
            depth = len(rel.parts)
        except ValueError:
            depth = 0

        if root_path != sub_dir:
            dir_count += 1
            indent = "  " * depth
            tree_lines.append(f"{indent}📁 {root_path.name}\n")

        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            # 过滤系统文件（🏠 home-、🧩 目录-、🤖 AI指令），不放入域索引
            if should_skip_file(f):
                continue
            file_count += 1
            indent = "  " * (depth + 1)
            file_stem = f[:-3]
            # 用简单文件名链接，不用路径（Obsidian 全局解析 [[文件名]]）
            link_path = file_stem

            user_text = _get_annotation(link_path, file_stem)
            if user_text:
                tree_lines.append(f"{indent}📄 [[{link_path}]] {user_text}\n")
            else:
                tree_lines.append(f"{indent}📄 [[{link_path}]]\n")
            all_files.append((link_path, file_stem, user_text))

    return dir_count, file_count, tree_lines, all_files


def _extract_keywords_from_name(name: str, max_count: int = 5) -> list:
    """从文件名中提取关键词，用于快速定位表"""
    name = name.replace('@', ' ').replace('-', ' ').replace('_', ' ')
    parts = re.split(r'[\s@\-_]+', name)
    keywords = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and not re.match(r'^[\d\.]+$', p):
            keywords.append(p)
    seen = set()
    unique = []
    for k in keywords:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            unique.append(k)
    return unique[:max_count]


def generate_domain_index(target_dir: Path, first_dir: Path,
                          link_annotations: dict, skill_summaries: dict,
                          chip_summaries: dict, freq_data: dict = None) -> dict:
    """
    为单个一级目录生成领域首页文件（🏠 home-{目录名}.md）。
    返回该领域的元数据：{name, file_count, dir_count, index_file, keywords, sample_files}
    """
    if freq_data is None:
        freq_data = {}
    
    dir_name = first_dir.name
    index_name = f"🏠 home-{dir_name}.md"
    index_path = target_dir / dir_name / index_name

    dir_count, file_count, tree_lines, all_files = _collect_dir_files(
        target_dir, first_dir, link_annotations, skill_summaries, chip_summaries
    )

    lines = []
    lines.append(f"# 🏠 home-{dir_name}\n")
    lines.append(f"{dir_name} 领域的完整目录索引，用于精准检索该领域文件，节省 Token。\n\n")
    lines.append("---\n\n")

    lines.append("## 📂 目录结构树\n\n")
    lines.extend(tree_lines)

    lines.append("\n---\n\n")
    lines.append("## 📊 统计摘要\n\n")
    lines.append(f"- **目录数**: {dir_count}\n")
    lines.append(f"- **文件数**: {file_count}\n")
    lines.append(f"- **更新时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    try:
        new_content = ''.join(lines)
        if index_path.exists():
            old_content = index_path.read_text(encoding='utf-8')
            if old_content == new_content:
                pass
            else:
                index_path.write_text(new_content, encoding='utf-8')
        else:
            index_path.write_text(new_content, encoding='utf-8')
    except Exception as e:
        print(f"  错误：写入领域索引文件失败 {index_path} - {e}")

    def _is_system_file(file_stem: str) -> bool:
        """判断是否为系统/索引文件（排除出快速定位表）"""
        if file_stem.startswith("🏠 home-"):
            return True
        if file_stem.startswith("🧩 目录-"):
            return True
        if file_stem == "🤖 AI指令":
            return True
        return False

    knowledge_files = [(lp, fs, anno) for lp, fs, anno in all_files if not _is_system_file(fs)]

    all_keywords = set()
    for _, file_stem, _ in knowledge_files[:50]:
        for kw in _extract_keywords_from_name(file_stem, 3):
            all_keywords.add(kw)

    # 按访问频率排序（高频在前）
    def _sort_by_freq(item):
        link_path, file_stem, _ = item
        full_key = f"{dir_name}\\{link_path}"
        count = get_file_access_count(freq_data, full_key)
        return (-count, link_path)

    knowledge_files_sorted = sorted(knowledge_files, key=_sort_by_freq)

    sample_files = []
    for link_path, file_stem, annotation in knowledge_files_sorted[:10]:
        sample_files.append((link_path, file_stem, annotation))

    return {
        'name': dir_name,
        'file_count': file_count,
        'dir_count': dir_count,
        'index_file': index_name,
        'keywords': list(all_keywords)[:15],
        'sample_files': sample_files,
    }


def generate_directory_index(target_dir: Path) -> int:
    """
    生成分层索引体系：
    1. 各领域首页：🏠 home-{一级目录名}.md（存储在对应子目录下）
    2. 总路由索引：📖目录 索引.md（含关键词快速定位 + 领域导航）
    
    最快检索路径：关键词快速定位表 → 直接命中文件
                 → 未命中则按领域导航 → 读取对应home文件
    """
    index_path = target_dir / "📖目录 索引.md"
    
    link_annotations = {}
    if index_path.exists():
        try:
            old_content = index_path.read_text(encoding='utf-8')
            for line in old_content.splitlines():
                match = re.search(r'\[\[([^\]]+)\]\](.*)', line)
                if match:
                    link_name = match.group(1).strip()
                    user_text = match.group(2).strip()
                    if user_text:
                        link_annotations[link_name] = user_text
                        pure_name = link_name.replace('\\', '/').split('/')[-1]
                        if pure_name not in link_annotations:
                            link_annotations[pure_name] = user_text
        except Exception:
            pass
    
    chip_summaries = extract_summaries_from_chip_files(target_dir)
    for pure_name, summary in chip_summaries.items():
        link_annotations[pure_name] = summary
    
    skill_summaries = extract_summaries_from_skill_dirs()
    
    # 加载访问频率数据
    freq_data = load_access_frequency(target_dir)
    
    first_level_dirs = []
    for entry in target_dir.iterdir():
        if entry.is_dir() and not should_skip_dir(entry.name):
            first_level_dirs.append(entry)
    first_level_dirs.sort(key=lambda x: x.name)
    
    print("📖 生成各领域二级索引...")
    domain_metas = []
    total_dirs = 0
    total_files = 0
    
    for first_dir in first_level_dirs:
        meta = generate_domain_index(target_dir, first_dir,
                                     link_annotations, skill_summaries, chip_summaries,
                                     freq_data)
        domain_metas.append(meta)
        total_dirs += meta['dir_count']
        total_files += meta['file_count']
        print(f"  📄 {meta['index_file']} : {meta['file_count']} 个文件")
    
    # 清理孤儿首页文件（不对应任何一级目录的 🏠 home-*.md）
    valid_index_names = {meta['index_file'] for meta in domain_metas}
    valid_index_names.add("📖目录 索引.md")  # 总路由不算孤儿
    for sub in target_dir.iterdir():
        if not sub.is_dir() or should_skip_dir(sub.name):
            continue
        for f in sub.iterdir():
            if f.is_file() and f.name.startswith("🏠 home-") and f.name.endswith(".md"):
                if f.name not in valid_index_names:
                    f.unlink()
                    print(f"  🗑️ 删除孤儿首页：{sub.name}/{f.name}")
    
    root_files = []
    for f in sorted(target_dir.iterdir()):
        if f.is_file() and f.name.endswith(".md") and f.name != "📖目录 索引.md" and not f.name.startswith("🏠 home-"):
            file_stem = f.name[:-3]
            
            def _get_anno(link_key, fallback_stem=""):
                if link_key in link_annotations:
                    return link_annotations[link_key]
                if fallback_stem and fallback_stem in link_annotations:
                    return link_annotations[fallback_stem]
                if fallback_stem:
                    for sn, sv in skill_summaries.items():
                        if sn.lower() in fallback_stem.lower():
                            return sv
                return ""
            
            anno = _get_anno(file_stem, file_stem)
            root_files.append((file_stem, anno))
    
    print("📖 生成总路由索引...")
    
    # 按优先级领域排序：PRIORITY_DOMAINS 中的领域排前面，其他按原顺序
    priority_set = set(PRIORITY_DOMAINS)
    priority_metas = []
    other_metas = []
    for meta in domain_metas:
        if meta['name'] in priority_set:
            priority_metas.append(meta)
        else:
            other_metas.append(meta)
    # 优先级领域按 PRIORITY_DOMAINS 顺序排序
    priority_metas.sort(key=lambda m: PRIORITY_DOMAINS.index(m['name']) if m['name'] in PRIORITY_DOMAINS else 999)
    sorted_domains = priority_metas + other_metas
    
    quick_jump = []
    for meta in sorted_domains:
        for i, (link_path, file_stem, annotation) in enumerate(meta['sample_files']):
            if i >= QUICK_JUMP_PER_DOMAIN:
                break
            full_link = f"{meta['name']}\\{link_path}"
            short_anno = annotation
            if len(short_anno) > 50:
                short_anno = short_anno[:47] + "..."
            quick_jump.append((file_stem, full_link, short_anno, meta['name']))
    
    # 限制最大条数
    quick_jump = quick_jump[:QUICK_JUMP_MAX]
    
    lines = []
    lines.append("# 📖目录 索引\n")
    lines.append("LeoDiary 知识库分层索引总路由。**请按以下顺序检索以节省 Token**：\n\n")
    lines.append("1. 先查 `⚡ 关键词快速定位` — 直接命中则跳转，无需读其他\n")
    lines.append("2. 未命中则看 `🧭 领域导航` — 根据关键词判断读哪个home文件\n")
    lines.append("3. 打开对应home文件继续查找\n\n")
    lines.append("---\n\n")
    
    lines.append("## ⚡ 关键词快速定位\n\n")
    lines.append("高频文件直接跳转表（命中即止，无需读完整索引）：\n\n")
    lines.append("| 文件名 | 所在领域 | 摘要 |\n")
    lines.append("|--------|---------|------|\n")
    for file_stem, full_link, short_anno, domain_name in quick_jump:
        display_name = file_stem if len(file_stem) <= 30 else file_stem[:27] + "..."
        anno_display = short_anno.replace('✍️ ', '').replace('|', '\\|')
        lines.append(f"| [[{full_link}\\|{display_name}]] | {domain_name} | {anno_display} |\n")
    
    lines.append("\n> 💡 在表中找到关键词匹配的文件，直接点击跳转即可，无需继续往下读。\n\n")
    lines.append("---\n\n")
    
    lines.append("## 🧭 领域导航\n\n")
    lines.append("按一级目录划分的home文件，精准定位到具体领域后再深入：\n\n")
    lines.append("| home文件 | 文件数 | 核心关键词 |\n")
    lines.append("|---------|-------|----------|\n")
    
    for meta in domain_metas:
        kws = "、".join(meta['keywords'][:8])
        lines.append(f"| [[{meta['index_file']}]] | {meta['file_count']} | {kws} |\n")
    
    lines.append("\n> 💡 根据问题关键词匹配上表，**只读取命中的home文件**，其他跳过。\n\n")
    lines.append("---\n\n")
    
    if root_files:
        lines.append("## 📄 根目录文件\n\n")
        for file_stem, anno in root_files:
            if anno:
                lines.append(f"- [[{file_stem}]] {anno}\n")
            else:
                lines.append(f"- [[{file_stem}]]\n")
        lines.append("\n---\n\n")
    
    lines.append("## 📊 统计摘要\n\n")
    lines.append(f"- **领域数**: {len(domain_metas)}\n")
    lines.append(f"- **总目录数**: {total_dirs}\n")
    lines.append(f"- **总文件数**: {total_files}\n")
    lines.append(f"- **更新时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        new_content = ''.join(lines)
        if index_path.exists():
            old_content = index_path.read_text(encoding='utf-8')
            if old_content == new_content:
                print(f"📖 总路由索引 : 无变化，跳过写入")
                return total_dirs + total_files
        index_path.write_text(new_content, encoding='utf-8')
        print(f"📖 总路由索引 : 已生成（{len(domain_metas)} 个领域，{total_files} 个文件）")
        return total_dirs + total_files
    except Exception as e:
        print(f"  错误：写入总路由索引失败 - {e}")
        return 0

def process_root_and_para_dirs(target_dir: Path) -> None:
    """处理根目录和PARA文件夹：生成🧩目录文件而非home文件"""
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
        if not subdir.is_dir() or should_skip_dir(subdir.name):
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
    # 支持子命令：record-access（记录访问）/ update（更新索引，默认）
    subcommand = "update"
    args = sys.argv[1:]
    
    if args and args[0] in ("record-access", "update"):
        subcommand = args[0]
        args = args[1:]
    
    if subcommand == "record-access":
        # 记录文件访问：record-access <vault路径> <文件路径（相对vault）>
        if len(args) < 2:
            print("用法：python Obsidian - index_updater.py record-access <vault路径> <文件相对路径>")
            sys.exit(1)
        vault_path = Path(args[0]).resolve()
        file_rel_path = args[1]
        record_file_access(vault_path, file_rel_path)
        print(f"✅ 已记录访问：{file_rel_path}")
        return
    
    # 默认：更新索引
    if len(args) > 0:
        target = Path(args[0]).resolve()
        if not target.exists() or not target.is_dir():
            print(f"错误：指定的目录不存在或不是文件夹：{target}")
            sys.exit(1)
    else:
        target = VAULT_ROOT
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
    root_dirs = [d for d in target.iterdir() if d.is_dir() and not should_skip_dir(d.name)]
    if not root_dirs:
        print("⚠️ 目标目录下没有可处理的子目录。")
        return

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
    print("📖 生成目录索引文件（方便AI检索）...")
    generate_directory_index(target)

    print("-" * 60)
    print("🎉 索引更新完成！")


if __name__ == "__main__":
    main()
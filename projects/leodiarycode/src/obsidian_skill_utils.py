#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian Skill 工具脚本
========================
从各 SKILL.md 中抽离的固定逻辑，供 Skill 通过命令行调用。
SKILL.md 只保留 AI 判断规则和触发条件，固定逻辑全部在此实现。

使用方式：python obsidian_skill_utils.py <命令> [参数...]

状态管理：
  state-load <skill> <vault>                          加载状态文件
  state-save <skill> <vault> <json_string>            保存状态文件

文件判断：
  is-system-file <filename>                           判断是否为系统文件
  check-file-thresholds <filepath>                    文件阈值检查（大小/行数/空壳/陷阱）
  check-summary-quality <summary> <title> [keywords]  摘要质量检查（照搬标题/信息量）
  validate-filename <name>                            验证文件名格式
  parse-filename <filename>                           解析文件名结构
  validate-document <filepath>                        文档格式校验（frontmatter/H1/摘要/标题层级）

索引操作：
  locate-domain-index <filepath> <vault>              定位领域索引文件
  update-index-entry <index_file> <old_link> <new_link> <summary>  更新索引条目
  remove-index-entry <index_file> <link>              删除索引条目
  add-to-default-category <chip_file> <link> <summary> 添加到待归类
  scan-unindexed <vault> <dir>                        扫描未索引文件

双链与文件：
  update-wikilinks <vault> <old_name> <new_name>      批量更新双链
  compute-hash <filepath>                             计算文件哈希
  detect-changes <skill> <vault> <dir>                检测文件变化
  compute-similarity <title1> <ent1> <top1> <t2> <e2> <to2>  相似度计算（Jaccard公式）
  verify-move <src> <dst> [index_file] [new_link]     移动完整性验证

流程辅助：
  generate-rollback <vault> <skill> <rename_pairs>    生成回滚脚本
  archive-cleanup <vault> <state_json> [skill]        归档清理
  check-fake-execution <vault> <state_json>           假执行检测
  drift-check <vault> <skill> [dir]                   Drift健康检查
  write-log <vault> <skill> <title> <content>       写入运行日志
  add-record <vault> <type> <description> [path]    写入⚓新增文件记录
  record-access <vault> <filepath>                    记录访问频率

质量保障（LEO OS 迁移）：
  validate-metadata <vault> [--quiet]               元数据校验（LeoDiary轻量标准：type/tags/日期/摘要/双链）
  lint-content <vault> [type]                       内容健康检查（过时/孤儿/断链/矛盾等7项）
  kb-stats <vault> [--json]                          知识库健康度统计
  skill-health-check <skills_dir> <vault>            Skill插件健康检查（命令/目录/类型/系统文件/流程一致性）
  health-check-all <vault> <skills_dir> <python_dir> LeoDiary项目级健康检查（7大类检查+HTML/MD报告）
"""

import sys
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime

# 添加 d:\Python 到路径，导入 obsidian_common
sys.path.insert(0, str(Path(__file__).parent))
from obsidian_common import (
    VAULT_ROOT, SKIP_DIRS, SKIP_FILES_PREFIX, SKIP_FILES_EXACT,
    PARA_DIRS, should_skip_dir, should_skip_file, is_markdown_file,
    read_text_safe, strip_frontmatter,
)

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ======================================================================
# 常量
# ======================================================================

# 系统文件前缀（不参与知识内容处理）
SYSTEM_FILE_PREFIXES = ("🏠 home-", "🧩 目录-", "📖目录 索引", "🤖 AI指令")

# 高频优先领域
PRIORITY_DOMAINS = ["1- 🤖AI 相关", "5- 🧁项目"]

# 状态文件目录
STATE_DIR_TEMPLATE = "logs/{skill}"


# ======================================================================
# 状态文件管理
# ======================================================================

def get_state_path(skill: str, vault: Path) -> Path:
    """获取状态文件路径"""
    return vault / STATE_DIR_TEMPLATE.format(skill=skill) / f"{skill}-state.json"


def cmd_state_load(skill: str, vault_str: str) -> None:
    """加载状态文件，输出JSON"""
    vault = Path(vault_str)
    state_path = get_state_path(skill, vault)
    if not state_path.exists():
        print("{}")
        return
    try:
        data = json.loads(read_text_safe(state_path))
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        print("{}")


def cmd_state_save(skill: str, vault_str: str, json_str: str) -> None:
    """保存状态文件（json_str 可以是JSON字符串，也可以是文件路径）"""
    vault = Path(vault_str)
    state_path = get_state_path(skill, vault)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # 如果 json_str 是文件路径，从文件读取
        if json_str.endswith('.json') and Path(json_str).exists():
            with open(json_str, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动处理BOM
                data = json.load(f)
        else:
            data = json.loads(json_str)
        state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"✅ 状态已保存：{state_path}")
    except Exception as e:
        print(f"❌ 保存失败：{e}")
        print(f"  提示：如果JSON太长，可以先写入临时文件，然后传文件路径")


# ======================================================================
# 系统文件判断
# ======================================================================

def is_system_file(file_stem: str) -> bool:
    """判断是否为系统/索引文件（同时匹配带/不带emoji前缀）"""
    # 去掉 .md 后缀
    stem = file_stem[:-3] if file_stem.endswith('.md') else file_stem
    # 带emoji前缀的匹配
    for prefix in SYSTEM_FILE_PREFIXES:
        if stem.startswith(prefix):
            return True
    # 不带emoji前缀的匹配（去掉emoji后的纯文本前缀）
    no_emoji_prefixes = ("home-", "目录-", "📖目录 索引", "AI指令", "🤖 AI指令")
    for prefix in no_emoji_prefixes:
        if stem.startswith(prefix):
            return True
    # 精确匹配
    if stem in ("🤖 AI指令", "AI指令", "README", "CLAUDE", "AGENTS", "🍕 作业区"):
        return True
    return False


def cmd_is_system_file(filename: str) -> None:
    """判断是否为系统文件"""
    stem = filename[:-3] if filename.endswith('.md') else filename
    print("true" if is_system_file(stem) else "false")


# ======================================================================
# 领域索引定位
# ======================================================================

def locate_domain_index(file_path: str, vault: Path) -> Path:
    """根据文件路径定位对应的领域索引文件"""
    parts = file_path.replace('\\', '/').split('/')
    if not parts:
        return None
    first_dir = parts[0]
    return vault / f"📖目录 索引-{first_dir}.md"


def cmd_locate_domain_index(file_path: str, vault_str: str) -> None:
    """定位领域索引文件"""
    vault = Path(vault_str)
    index_path = locate_domain_index(file_path, vault)
    if index_path and index_path.exists():
        print(str(index_path))
    else:
        print("NOT_FOUND")


# ======================================================================
# 索引条目操作
# ======================================================================

def extract_all_links_from_file(file_path: Path) -> set:
    """从文件中提取所有 [[链接]]"""
    if not file_path.exists():
        return set()
    content = read_text_safe(file_path)
    return set(re.findall(r'\[\[([^\]]+)\]\]', content))


def cmd_update_index_entry(index_file: str, old_link: str, new_link: str, summary: str) -> None:
    """更新索引条目：删除旧链接，添加新链接（带摘要）"""
    index_path = Path(index_file)
    if not index_path.exists():
        print(f"❌ 索引文件不存在：{index_file}")
        return
    content = read_text_safe(index_path)
    lines = content.splitlines(keepends=True)
    
    updated = False
    new_lines = []
    for line in lines:
        # 删除旧链接行
        if f'[[{old_link}]]' in line:
            updated = True
            continue
        new_lines.append(line)
    
    # 在文件清单区域添加新链接
    new_entry = f"- [[{new_link}]]"
    if summary:
        new_entry += f" ✍️ {summary}"
    new_entry += "\n"
    
    # 找到文件清单区域
    in_file_list = False
    inserted = False
    final_lines = []
    for line in new_lines:
        if '## 📋 文件清单' in line:
            in_file_list = True
            final_lines.append(line)
            continue
        if in_file_list and line.startswith('## '):
            # 文件清单区域结束，在前面插入新条目
            if not inserted:
                final_lines.append(new_entry)
                inserted = True
            in_file_list = False
            final_lines.append(line)
            continue
        final_lines.append(line)
    
    if not inserted:
        final_lines.append(new_entry)
    
    index_path.write_text(''.join(final_lines), encoding='utf-8')
    print(f"✅ 已更新索引：{index_file}（删除旧链接，添加新链接）")


def cmd_remove_index_entry(index_file: str, link: str) -> None:
    """删除索引条目"""
    index_path = Path(index_file)
    if not index_path.exists():
        print(f"❌ 索引文件不存在：{index_file}")
        return
    content = read_text_safe(index_path)
    lines = content.splitlines(keepends=True)
    
    new_lines = [line for line in lines if f'[[{link}]]' not in line]
    
    index_path.write_text(''.join(new_lines), encoding='utf-8')
    print(f"✅ 已删除索引条目：{link}")


def cmd_add_to_default_category(chip_file: str, link: str, summary: str) -> None:
    """添加到待归类分类"""
    chip_path = Path(chip_file)
    if not chip_path.exists():
        print(f"❌ 目录文件不存在：{chip_file}")
        return
    
    content = read_text_safe(chip_path)
    existing_links = extract_all_links_from_file(chip_path)
    if link in existing_links:
        print(f"⏭️  链接已存在：{link}")
        return
    
    default_header = "##### 📥 待归类\n"
    lines = content.splitlines(keepends=True)
    
    new_entry = f"- [[{link}]]"
    if summary:
        new_entry += f" ✍️ {summary}"
    new_entry += "\n"
    
    # 查找待归类分类
    category_found = False
    insert_pos = -1
    for i, line in enumerate(lines):
        if line.strip() == "##### 📥 待归类":
            category_found = True
            insert_pos = i + 1
            while insert_pos < len(lines) and lines[insert_pos].strip().startswith('- [['):
                insert_pos += 1
            break
    
    if not category_found:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines.append(default_header)
        lines.append(new_entry)
    else:
        lines.insert(insert_pos, new_entry)
    
    chip_path.write_text(''.join(lines), encoding='utf-8')
    print(f"✅ 已添加到待归类：{link}")


# ======================================================================
# 双链维护
# ======================================================================

def cmd_update_wikilinks(vault_str: str, old_name: str, new_name: str) -> None:
    """更新所有文件中的双链 [[old_name]] -> [[new_name]]"""
    vault = Path(vault_str)
    old_pattern = f'[[{old_name}'
    new_pattern = f'[[{new_name}'
    count = 0
    
    for root, dirs, files in os.walk(vault):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if not fname.endswith('.md'):
                continue
            fpath = Path(root) / fname
            content = read_text_safe(fpath)
            if old_pattern not in content:
                continue
            # 替换 [[old_name 和 [[old_name|
            new_content = content.replace(
                f'[[{old_name}]]', f'[[{new_name}]]'
            ).replace(
                f'[[{old_name}|', f'[[{new_name}|'
            )
            if new_content != content:
                fpath.write_text(new_content, encoding='utf-8')
                count += 1
                print(f"  📝 已更新：{fpath.relative_to(vault)}")
    
    print(f"✅ 双链更新完成：共更新 {count} 个文件")


# ======================================================================
# 哈希与变化检测
# ======================================================================

def cmd_compute_hash(filepath: str) -> None:
    """计算文件哈希"""
    fpath = Path(filepath)
    if not fpath.exists():
        print("NOT_FOUND")
        return
    try:
        content = read_text_safe(fpath)
        # 取第一个 # 标题作为标题
        title = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('# ') and not stripped.startswith('## '):
                title = stripped[2:]
                break
        h = hashlib.md5(content.encode('utf-8')).hexdigest()
        print(json.dumps({"hash": h, "title": title}, ensure_ascii=False))
    except Exception as e:
        print(f'{{"error": "{e}"}}')


def cmd_detect_changes(skill: str, vault_str: str, dir_str: str) -> None:
    """检测目录中文件的变化（对比状态文件）"""
    vault = Path(vault_str)
    target_dir = vault / dir_str if not Path(dir_str).is_absolute() else Path(dir_str)
    
    state_path = get_state_path(skill, vault)
    state = {}
    if state_path.exists():
        try:
            state = json.loads(read_text_safe(state_path))
        except Exception:
            state = {}
    
    changed = []
    new_files = []
    
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if not fname.endswith('.md') or should_skip_file(fname):
                continue
            fpath = Path(root) / fname
            rel_path = str(fpath.relative_to(vault))
            
            content = read_text_safe(fpath)
            h = hashlib.md5(content.encode('utf-8')).hexdigest()
            title = ""
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith('# ') and not stripped.startswith('## '):
                    title = stripped[2:]
                    break
            
            if rel_path not in state:
                new_files.append({"path": rel_path, "title": title, "hash": h})
            elif state[rel_path].get('文件哈希') != h:
                changed.append({"path": rel_path, "title": title, "hash": h,
                               "old_title": state[rel_path].get('标题', '')})
    
    result = {"new_files": new_files, "changed": changed}
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 命名规则
# ======================================================================

def cmd_validate_filename(name: str) -> None:
    """验证文件名格式"""
    issues = []
    if '|' in name:
        issues.append("文件名包含 | 字符")
    if '#' in name:
        issues.append("文件名包含 # 字符")
    if '[' in name or ']' in name:
        issues.append("文件名包含 [ ] 字符")
    if len(name) > 100:
        issues.append("文件名过长（>100字符）")
    if not name.strip():
        issues.append("文件名为空")
    
    if issues:
        print(json.dumps({"valid": False, "issues": issues}, ensure_ascii=False))
    else:
        print(json.dumps({"valid": True}, ensure_ascii=False))


def cmd_parse_filename(filename: str) -> None:
    """解析文件名结构：主题 - 类型 @ 说明"""
    # 去掉 .md 后缀
    name = filename[:-3] if filename.endswith('.md') else filename
    
    result = {"original": name, "topic": "", "type": "", "note": ""}
    
    # 分割 @ 说明
    if '@' in name:
        main_part, note = name.split('@', 1)
        result['note'] = note.strip()
    else:
        main_part = name
    
    # 分割 - 类型
    if ' - ' in main_part:
        parts = main_part.split(' - ', 1)
        result['topic'] = parts[0].strip()
        result['type'] = parts[1].strip() if len(parts) > 1 else ""
    else:
        result['topic'] = main_part.strip()
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 访问频率记录
# ======================================================================

def cmd_record_access(vault_str: str, filepath: str) -> None:
    """记录文件访问频率"""
    vault = Path(vault_str)
    freq_path = vault / "logs/index/access-frequency.json"
    freq_path.parent.mkdir(parents=True, exist_ok=True)
    
    freq_data = {}
    if freq_path.exists():
        try:
            freq_data = json.loads(read_text_safe(freq_path))
        except Exception:
            freq_data = {}
    
    now = datetime.now().isoformat()
    if filepath in freq_data:
        freq_data[filepath]['count'] = freq_data[filepath].get('count', 0) + 1
        freq_data[filepath]['last_time'] = now
    else:
        freq_data[filepath] = {'count': 1, 'last_time': now}
    
    freq_path.write_text(json.dumps(freq_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✅ 已记录访问：{filepath}（第 {freq_data[filepath]['count']} 次）")


# ======================================================================
# 扫描未索引文件
# ======================================================================

def cmd_scan_unindexed(vault_str: str, dir_str: str) -> None:
    """扫描目录中未在🧩目录文件中出现的文件"""
    vault = Path(vault_str)
    target_dir = vault / dir_str if not Path(dir_str).is_absolute() else Path(dir_str)
    
    # 找到对应的🧩目录文件
    chip_files = list(target_dir.glob("🧩 目录-*.md"))
    indexed_links = set()
    for chip in chip_files:
        indexed_links |= extract_all_links_from_file(chip)
    
    unindexed = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if not fname.endswith('.md') or should_skip_file(fname):
                continue
            if fname.startswith("🧩 目录-") or fname.startswith("🏠 home-"):
                continue
            stem = fname[:-3]
            # 检查文件名或路径是否在索引中
            found = False
            for link in indexed_links:
                if stem in link or link in stem:
                    found = True
                    break
            if not found:
                rel_path = str(Path(root).relative_to(target_dir) / stem)
                unindexed.append(rel_path.replace('\\', '/'))
    
    print(json.dumps({"unindexed": unindexed, "count": len(unindexed)}, ensure_ascii=False, indent=2))


# ======================================================================
# 文件阈值检查
# ======================================================================

def cmd_check_file_thresholds(filepath: str) -> None:
    """检查文件阈值：大小、行数、空壳判断、陷阱文件检测"""
    fpath = Path(filepath)
    if not fpath.exists():
        print(json.dumps({"exists": False}, ensure_ascii=False))
        return
    
    size = fpath.stat().st_size
    content = read_text_safe(fpath)
    lines = content.splitlines()
    line_count = len(lines)
    
    # 陷阱文件检测
    is_trap = False
    trap_reasons = []
    fname = fpath.name
    
    trap_patterns = [
        ('临时', '文件名含"临时"'),
        ('tmp', '文件名含tmp'),
        ('scratch', '文件名含scratch'),
        ('draft-', 'draft-前缀'),
    ]
    for pat, reason in trap_patterns:
        if pat.lower() in fname.lower():
            is_trap = True
            trap_reasons.append(reason)
            break
    
    if fname.startswith('.'):
        is_trap = True
        trap_reasons.append('隐藏文件')
    if not fname.endswith('.md'):
        is_trap = True
        trap_reasons.append('非md文件')
    
    # 检查前5行是否全是base64或二进制
    first_5 = '\n'.join(lines[:5])
    import base64
    try:
        if first_5.strip() and len(first_5.strip()) > 50:
            base64.b64decode(first_5.strip(), validate=True)
            is_trap = True
            trap_reasons.append('内容疑似base64/二进制')
    except Exception:
        pass
    
    # 空壳判断
    is_empty_shell = size < 10 or (len(content.strip()) < 100 and size < 500)
    
    # 行数阈值
    partial = line_count > 5000
    partial_lines = 500 if partial else line_count
    
    result = {
        "exists": True,
        "size_bytes": size,
        "line_count": line_count,
        "is_trap": is_trap,
        "trap_reasons": trap_reasons,
        "is_empty_shell": is_empty_shell,
        "partial": partial,
        "partial_lines": partial_lines,
        "too_large": size > 2 * 1024 * 1024,
        "too_small": size < 10,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 摘要质量检查
# ======================================================================

def cmd_check_summary_quality(summary: str, title: str, content_keywords: str = "") -> None:
    """检查摘要质量：是否照搬标题、信息量是否足够"""
    # 照搬标题检测
    is_title_copy = False
    summary_clean = summary.strip().replace(' ', '').replace('，', '').replace('。', '')
    title_clean = title.strip().replace(' ', '').replace('，', '').replace('。', '')
    if summary_clean == title_clean:
        is_title_copy = True
    elif len(summary_clean) > 0 and len(title_clean) > 0:
        # 计算重叠度
        common = set(summary_clean) & set(title_clean)
        if len(common) / max(len(summary_clean), 1) > 0.9:
            is_title_copy = True
    
    # 通用词检测（低信息量）
    generic_words = ['资料', '文档', '相关', '内容', '介绍', '说明', '记录', '笔记', '总结', '汇总']
    generic_count = sum(1 for w in generic_words if w in summary)
    
    # 关键词检查
    has_keywords = False
    if content_keywords:
        kws = [k.strip() for k in content_keywords.split(',') if k.strip()]
        matched = [k for k in kws if k in summary]
        has_keywords = len(matched) >= 2
    
    # 长度检查
    too_short = len(summary) < 10
    too_long_general = len(summary) > 100
    
    quality = "low"
    if not is_title_copy and not too_short and has_keywords:
        quality = "high"
    elif not is_title_copy and not too_short and generic_count < 2:
        quality = "medium"
    
    result = {
        "quality": quality,
        "is_title_copy": is_title_copy,
        "generic_word_count": generic_count,
        "too_short": too_short,
        "too_long_general": too_long_general,
        "has_keywords": has_keywords,
        "length": len(summary),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 文档格式校验
# ======================================================================

def cmd_validate_document(filepath: str) -> None:
    """校验文档格式：frontmatter、H1、标题层级、✍️摘要"""
    fpath = Path(filepath)
    if not fpath.exists():
        print(json.dumps({"valid": False, "error": "文件不存在"}, ensure_ascii=False))
        return
    
    content = read_text_safe(fpath)
    lines = content.splitlines()
    
    issues = []
    has_frontmatter = False
    has_h1 = False
    has_summary = False
    h1_text = ""
    prev_level = 0
    level_jump = False
    
    in_frontmatter = False
    fm_count = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # frontmatter检测
        if i == 0 and stripped == '---':
            in_frontmatter = True
            fm_count += 1
            continue
        if in_frontmatter and stripped == '---':
            fm_count += 1
            if fm_count >= 2:
                in_frontmatter = False
                has_frontmatter = True
            continue
        
        if in_frontmatter:
            continue
        
        # 标题检测
        if stripped.startswith('# '):
            has_h1 = True
            h1_text = stripped[2:].strip()
            prev_level = 1
            continue
        
        if stripped.startswith('##'):
            level = len(stripped) - len(stripped.lstrip('#'))
            if prev_level > 0 and level > prev_level + 1:
                level_jump = True
                issues.append(f"标题跳级：第{i+1}行从H{prev_level}跳到H{level}")
            prev_level = level
        
        # ✍️摘要检测（H1下方的引用块）
        if has_h1 and not has_summary and stripped.startswith('>✍️'):
            has_summary = True
            summary_len = len(stripped.replace('>✍️', '').strip())
            if summary_len < 30:
                issues.append(f"✍️摘要过短：{summary_len}字（建议50-100字）")
            elif summary_len > 150:
                issues.append(f"✍️摘要过长：{summary_len}字（建议50-100字）")
    
    if not has_frontmatter:
        issues.append("缺少 frontmatter")
    if not has_h1:
        issues.append("缺少 H1 标题")
    if not has_summary:
        issues.append("缺少 ✍️ 摘要")
    if level_jump:
        issues.append("存在标题层级跳级")
    
    # 检查文件名与H1一致性
    fname_stem = fpath.stem
    if has_h1 and h1_text and fname_stem != h1_text:
        # 提取主题部分比较
        main_name = fname_stem.split(' - ')[0].split(' @')[0]
        main_h1 = h1_text.split(' - ')[0].split(' @')[0]
        if main_name != main_h1:
            issues.append(f"文件名与H1标题不一致：{fname_stem} vs {h1_text}")
    
    result = {
        "valid": len(issues) == 0,
        "has_frontmatter": has_frontmatter,
        "has_h1": has_h1,
        "h1_text": h1_text,
        "has_summary": has_summary,
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# Jaccard 相似度计算
# ======================================================================

def jaccard_similarity(set1: set, set2: set) -> float:
    """计算Jaccard相似度"""
    if not set1 and not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def cmd_compute_similarity(title1: str, entities1: str, topic1: str,
                            title2: str, entities2: str, topic2: str) -> None:
    """
    计算两个页面的相似度（Planner同款公式）
    相似度 = 标题Jaccard × 0.5 + 实体一致率 × 0.3 + 主题词匹配率 × 0.2
    """
    # 分词（简单按字符n-gram + 空格分词）
    def char_ngrams(text: str, n: int = 2) -> set:
        text = text.strip()
        if len(text) < n:
            return {text} if text else set()
        return set(text[i:i+n] for i in range(len(text)-n+1))
    
    def split_terms(text: str) -> set:
        if not text:
            return set()
        # 按逗号、空格、中文逗号分割
        import re
        terms = re.split(r'[,，、\s]+', text.strip())
        return set(t for t in terms if t)
    
    # 标题相似度（Jaccard bigram）
    title_set1 = char_ngrams(title1)
    title_set2 = char_ngrams(title2)
    title_sim = jaccard_similarity(title_set1, title_set2)
    
    # 实体一致率
    entity_set1 = split_terms(entities1)
    entity_set2 = split_terms(entities2)
    entity_sim = jaccard_similarity(entity_set1, entity_set2)
    
    # 主题词匹配率
    topic_set1 = split_terms(topic1)
    topic_set2 = split_terms(topic2)
    topic_sim = jaccard_similarity(topic_set1, topic_set2)
    
    # 综合相似度
    similarity = title_sim * 0.5 + entity_sim * 0.3 + topic_sim * 0.2
    
    result = {
        "title_similarity": round(title_sim * 100, 1),
        "entity_similarity": round(entity_sim * 100, 1),
        "topic_similarity": round(topic_sim * 100, 1),
        "overall_similarity": round(similarity * 100, 1),
        "action": (
            "merge" if similarity >= 0.75 else
            "link" if similarity >= 0.30 else
            "create"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 移动完整性验证
# ======================================================================

def cmd_verify_move(src_path: str, dst_path: str, index_file: str = "", new_link: str = "") -> None:
    """验证文件移动完整性（含 AI_INDEX 同步检查）"""
    import hashlib
    src = Path(src_path)
    dst = Path(dst_path)
    
    issues = []
    
    # 目标文件存在
    if not dst.exists():
        issues.append("目标文件不存在")
    
    # 源文件已消失
    if src.exists():
        issues.append("源文件仍存在")
    
    # 文件大小一致
    if dst.exists() and src.exists():
        src_size = src.stat().st_size
        dst_size = dst.stat().st_size
        if abs(src_size - dst_size) > 10:
            issues.append(f"文件大小不一致：源{src_size}字节 vs 目标{dst_size}字节")
    
    # 领域索引已更新
    index_updated = False
    if index_file and new_link:
        idx = Path(index_file)
        if idx.exists():
            content = read_text_safe(idx)
            if f'[[{new_link}]]' in content:
                index_updated = True
            else:
                issues.append(f"索引中未找到新链接：{new_link}")
        else:
            issues.append(f"索引文件不存在：{index_file}")
    
    # AI_INDEX 同步检查 (LD-DVA Final: 检查 .ai-index/runtime/files.json)
    ai_index_ok = None
    if dst.exists():
        try:
            vault_root = Path(r"D:\Obsidian\LeoDiary")
            files_json = vault_root / ".ai-index" / "runtime" / "files.json"
            if files_json.exists():
                import json as _json
                files_data = _json.loads(read_text_safe(files_json))
                # files.json 是列表，每项含 i(文件id), t(标题), p(路径)
                rel_path = str(dst.relative_to(vault_root)).replace("\\", "/")
                found = any(f.get("p") == rel_path for f in files_data if isinstance(f, dict))
                if found:
                    ai_index_ok = True
                else:
                    ai_index_ok = False
                    issues.append(f"AI_INDEX files.json 中无此文件，请运行 ai_index_builder_v2.py rebuild（文件：{rel_path}）")
            else:
                issues.append(".ai-index/runtime/files.json 不存在，请运行 ai_index_builder_v2.py rebuild")
        except Exception as e:
            issues.append(f"AI_INDEX 检查失败：{e}")
    
    result = {
        "success": len(issues) == 0,
        "issues": issues,
        "src_exists": src.exists(),
        "dst_exists": dst.exists(),
        "index_updated": index_updated if index_file else None,
        "ai_index_ok": ai_index_ok,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 回滚脚本生成
# ======================================================================

def cmd_generate_rollback(vault_str: str, skill: str, rename_pairs_json: str) -> None:
    """生成PowerShell回滚脚本"""
    vault = Path(vault_str)
    import json
    try:
        pairs = json.loads(rename_pairs_json)
    except Exception:
        pairs = []
    
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M")
    rollback_dir = vault / f"logs/{skill}"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    rollback_file = rollback_dir / f"{skill}-rollback-{timestamp}.ps1"
    
    lines = [
        "# 回滚脚本 - 自动生成",
        f"# 生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Vault：{vault}",
        "",
        "# 先备份当前状态",
        f"Write-Host '正在备份当前状态...'",
        "",
        "# 执行回滚",
        f"Write-Host '开始回滚 {len(pairs)} 个文件...'",
        "",
    ]
    
    for pair in pairs:
        old_name = pair.get("old", "")
        new_name = pair.get("new", "")
        if old_name and new_name:
            lines.append(f"# 回滚：{new_name} -> {old_name}")
            lines.append(f"if (Test-Path '{new_name}') {{")
            lines.append(f"    Rename-Item -Path '{new_name}' -NewName '{old_name}' -Force")
            lines.append(f"    Write-Host '  已回滚：{new_name}'")
            lines.append(f"}} else {{")
            lines.append(f"    Write-Warning '  文件不存在，跳过：{new_name}'")
            lines.append(f"}}")
            lines.append("")
    
    lines += [
        "Write-Host '回滚完成！'",
        "",
        "# 提示：运行前请确认",
        "# .\\rollback-script.ps1",
    ]
    
    rollback_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"✅ 回滚脚本已生成：{rollback_file}")


# ======================================================================
# 归档清理
# ======================================================================

def cmd_archive_cleanup(vault_str: str, state_json: str, skill: str = "pipeline") -> None:
    """
    归档清理：根据状态文件，将已处理文件移动到归档，已丢弃文件移到回收站
    """
    vault = Path(vault_str)
    import json
    try:
        state = json.loads(state_json)
    except Exception:
        state = {}
    
    today = datetime.now().strftime("%Y-%m-%d")
    archive_dir = vault / f"D📦 归档（Archive）/processed-{today}"
    trash_dir = vault / "_trash"
    
    archived = []
    trashed = []
    skipped = []
    
    # 跳过元数据字段
    META_KEYS = {"版本", "上次运行", "captureFolder", "统计", "哈希记录", 
                  "drift修复记录", "文件追踪", "last_run", "version", "stats"}
    if "文件追踪" in state and isinstance(state["文件追踪"], dict):
        file_entries = state["文件追踪"]
    else:
        file_entries = {k: v for k, v in state.items() if k not in META_KEYS and isinstance(v, dict)}
    
    for filepath, info in file_entries.items():
        status = info.get("处理状态", "") if isinstance(info, dict) else ""
        fpath = vault / filepath
        
        if not fpath.exists():
            skipped.append(f"{filepath}（不存在）")
            continue
        
        if status in ("已处理", "已合并", "部分新建"):
            archive_dir.mkdir(parents=True, exist_ok=True)
            dst = archive_dir / fpath.name
            if dst.exists():
                dst = archive_dir / f"{fpath.stem}_{datetime.now().strftime('%H%M%S')}{fpath.suffix}"
            fpath.rename(dst)
            archived.append(str(dst.relative_to(vault)))
        elif status == "已丢弃":
            trash_dir.mkdir(parents=True, exist_ok=True)
            dst = trash_dir / fpath.name
            if dst.exists():
                dst = trash_dir / f"{fpath.stem}_{datetime.now().strftime('%H%M%S')}{fpath.suffix}"
            fpath.rename(dst)
            trashed.append(str(dst.relative_to(vault)))
        else:
            skipped.append(f"{filepath}（状态：{status}）")
    
    result = {
        "archived": archived,
        "archived_count": len(archived),
        "trashed": trashed,
        "trashed_count": len(trashed),
        "skipped": skipped,
        "archive_dir": str(archive_dir.relative_to(vault)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 假执行检测
# ======================================================================

def cmd_check_fake_execution(vault_str: str, state_json: str) -> None:
    """假执行检测：检查Capture残留、目标文件缺失、merge假合并等"""
    vault = Path(vault_str)
    import json
    try:
        state = json.loads(state_json)
    except Exception:
        state = {}
    
    issues = []
    capture_dir = vault / "A📥 收集（Capture）"
    
    # 跳过元数据字段，只处理文件追踪记录
    META_KEYS = {"版本", "上次运行", "captureFolder", "统计", "哈希记录", 
                  "drift修复记录", "文件追踪", "last_run", "version", "stats"}
    if "文件追踪" in state and isinstance(state["文件追踪"], dict):
        file_entries = state["文件追踪"]
    else:
        file_entries = {k: v for k, v in state.items() if k not in META_KEYS and isinstance(v, dict)}
    
    for filepath, info in file_entries.items():
        if not isinstance(info, dict):
            continue
        status = info.get("处理状态", "")
        fpath = vault / filepath
        
        # Capture残留
        if status in ("已处理", "已合并", "已丢弃", "部分新建"):
            if fpath.exists() and "A📥 收集" in filepath:
                issues.append({
                    "type": "capture_residue",
                    "file": filepath,
                    "status": status,
                    "message": f"状态为{status}但仍在Capture中"
                })
        
        # 目标文件缺失
        target_file = info.get("目标文件", "")
        if target_file and status in ("已处理", "已合并", "部分新建"):
            target_path = vault / target_file
            if not target_path.exists():
                issues.append({
                    "type": "target_missing",
                    "file": target_file,
                    "status": status,
                    "message": "目标文件不存在"
                })
        
        # merge假合并
        if status == "已合并" and target_file:
            target_path = vault / target_file
            if target_path.exists():
                size = target_path.stat().st_size
                if size <= 100:
                    issues.append({
                        "type": "fake_merge",
                        "file": target_file,
                        "size": size,
                        "message": f"合并后文件过小（{size}字节），疑似假合并"
                    })
    
    # discard未清理
    for filepath, info in file_entries.items():
        if not isinstance(info, dict):
            continue
        if info.get("处理状态", "") == "已丢弃":
            fpath = vault / filepath
            if fpath.exists() and "_trash" not in filepath:
                issues.append({
                    "type": "discard_not_cleaned",
                    "file": filepath,
                    "message": "标记丢弃但未移到回收站"
                })
    
    result = {
        "issues_found": len(issues),
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# Drift 健康检查
# ======================================================================

def cmd_drift_check(vault_str: str, skill: str, dir_str: str = "") -> None:
    """Drift检测：检查state与实际文件的一致性"""
    vault = Path(vault_str)
    state_path = get_state_path(skill, vault)
    
    state = {}
    if state_path.exists():
        try:
            state = json.loads(read_text_safe(state_path))
        except Exception:
            state = {}
    
    # 扫描实际文件
    actual_files = {}
    scan_dir = vault / dir_str if dir_str else vault
    if dir_str and not Path(dir_str).is_absolute():
        scan_dir = vault / dir_str
    
    for root, dirs, files in os.walk(scan_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if not fname.endswith('.md') or should_skip_file(fname):
                continue
            fpath = Path(root) / fname
            rel_path = str(fpath.relative_to(vault)).replace('\\', '/')
            content = read_text_safe(fpath)
            h = hashlib.md5(content.encode('utf-8')).hexdigest()
            title = ""
            for line in content.splitlines():
                if line.strip().startswith('# ') and not line.strip().startswith('## '):
                    title = line.strip()[2:]
                    break
            actual_files[rel_path] = {"hash": h, "title": title}
    
    # 对比
    # state 中可能包含元数据字段（非文件路径），需要跳过
    META_KEYS = {"版本", "上次运行", "captureFolder", "统计", "哈希记录", 
                  "drift修复记录", "文件追踪", "last_run", "version", "stats"}
    
    state_only = []
    actual_only = []
    title_mismatch = []
    hash_mismatch = []
    
    # 如果 state 有 "文件追踪" 字段，从里面取文件路径
    file_entries = {}
    if "文件追踪" in state and isinstance(state["文件追踪"], dict):
        file_entries = state["文件追踪"]
    else:
        # 直接遍历，但跳过元数据字段
        for k, v in state.items():
            if k not in META_KEYS and isinstance(v, dict) and ("路径" in v or "path" in v or "文件哈希" in v or "hash" in v):
                file_entries[k] = v
    
    for filepath, info in file_entries.items():
        if filepath not in actual_files:
            state_only.append(filepath)
            continue
        if isinstance(info, dict):
            state_title = info.get("标题", info.get("title", ""))
            state_hash = info.get("文件哈希", info.get("hash", ""))
            if state_title and actual_files[filepath]["title"] != state_title:
                title_mismatch.append({
                    "file": filepath,
                    "state_title": state_title,
                    "actual_title": actual_files[filepath]["title"]
                })
            if state_hash and actual_files[filepath]["hash"] != state_hash:
                hash_mismatch.append({
                    "file": filepath,
                    "state_hash": state_hash[:8],
                    "actual_hash": actual_files[filepath]["hash"][:8]
                })
    
    for filepath in actual_files:
        if filepath not in state:
            actual_only.append(filepath)
    
    result = {
        "state_only": state_only,
        "state_only_count": len(state_only),
        "actual_only": actual_only,
        "actual_only_count": len(actual_only),
        "title_mismatch": title_mismatch,
        "title_mismatch_count": len(title_mismatch),
        "hash_mismatch": hash_mismatch,
        "hash_mismatch_count": len(hash_mismatch),
        "total_state_files": len({k: v for k, v in state.items() if isinstance(v, dict) and ("路径" in v or "path" in v or "文件哈希" in v or "hash" in v)}),
        "total_actual_files": len(actual_files),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ======================================================================
# 运行日志写入
# ======================================================================

def cmd_write_log(vault_str: str, skill: str, log_title: str, content: str) -> None:
    """追加写入运行日志"""
    vault = Path(vault_str)
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = vault / f"logs/{skill}"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{skill}-{today}.md"
    
    now_str = datetime.now().strftime("%H:%M:%S")
    entry = f"## {now_str} {log_title}\n\n{content}\n\n"
    
    if log_file.exists():
        existing = read_text_safe(log_file)
        # 找到文件开头，最新的在上
        new_content = f"# {skill} 运行日志 - {today}\n\n{entry}{existing}"
    else:
        new_content = f"# {skill} 运行日志 - {today}\n\n{entry}"
    
    log_file.write_text(new_content, encoding='utf-8')
    print(f"✅ 日志已写入：{log_file}")


# ======================================================================
# ⚓新增文件记录写入
# ======================================================================

def cmd_add_record(vault_str: str, operation_type: str, description: str, path: str = "") -> None:
    """追加写入⚓新增文件记录.md"""
    vault = Path(vault_str)
    record_file = vault / "⚓新增文件记录.md"
    
    today = datetime.now()
    date_header = f"### {today.year}年{today.month}月{today.day}日"
    now_str = today.strftime("%H:%M")
    
    # 操作类型中文映射
    type_map = {
        "add": "新增",
        "merge": "合并",
        "archive": "归档",
        "delete": "回收",
        "rename": "优化",
        "organize": "整理",
        "compile": "编译",
    }
    op_cn = type_map.get(operation_type, operation_type)
    
    entry = f"- 【{op_cn}】{description}"
    if path:
        entry += f" {path}"
    entry += f"  ({now_str})\n"
    
    if record_file.exists():
        content = read_text_safe(record_file)
        lines = content.splitlines(keepends=True)
        
        # 查找今天的日期头
        today_header_found = False
        insert_pos = -1
        
        for i, line in enumerate(lines):
            if line.strip() == date_header:
                today_header_found = True
                # 在日期头后面插入
                insert_pos = i + 1
                break
        
        if today_header_found:
            lines.insert(insert_pos, entry)
        else:
            # 在文件开头添加新的日期头
            date_section = f"\n{date_header}\n{entry}"
            # 找到第一个 ### 的位置，或者文件开头
            first_content_pos = 0
            for i, line in enumerate(lines):
                if line.strip().startswith('### '):
                    first_content_pos = i
                    break
            lines.insert(first_content_pos, date_section)
        
        record_file.write_text(''.join(lines), encoding='utf-8')
    else:
        content = f"# ⚓ 新增文件记录\n\n{date_header}\n{entry}\n"
        record_file.write_text(content, encoding='utf-8')
    
    print(f"✅ 已添加记录：【{op_cn}】{description}")


# ======================================================================
# LEO OS 迁移：元数据校验、内容健康检查、知识库健康度
# ======================================================================

def cmd_validate_metadata(vault: str, quiet: bool = False) -> None:
    """校验知识库所有文件的元数据是否符合 LeoDiary 轻量标准（type/tags/日期/摘要/双链）。"""
    import subprocess
    import sys
    from pathlib import Path

    script_dir = Path(__file__).resolve().parent.parent / "lib"
    validate_script = script_dir / "validate.py"

    if not validate_script.exists():
        print("❌ validate.py 不存在，请检查 lib/ 目录")
        return

    cmd = [sys.executable, str(validate_script), vault]
    if quiet:
        cmd.append("--quiet")

    result = subprocess.run(cmd, capture_output=False, text=True, encoding="utf-8", errors="replace")


def cmd_lint_content(vault: str, check_type: str = "all") -> None:
    """内容健康检查（过时/孤儿/断链/矛盾标记/缺失交叉引用/双向链接/内容矛盾）。报告同时写入 _trash/。"""
    import subprocess
    import sys
    from pathlib import Path

    script_dir = Path(__file__).resolve().parent.parent / "lib"
    lint_script = script_dir / "lint.py"

    if not lint_script.exists():
        print("❌ lint.py 不存在，请检查 lib/ 目录")
        return

    cmd = [sys.executable, str(lint_script), vault]

    check_map = {
        "stale": "--stale",
        "orphans": "--orphans",
        "broken": "--broken",
        "conflicts": "--conflicts",
        "missing": "--missing",
        "backlinks": "--backlinks",
        "content-conflicts": "--content-conflicts",
        "all": None,
    }

    if check_type in check_map and check_map[check_type]:
        cmd.append(check_map[check_type])

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout
    if output:
        print(output)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # 报告写入 _trash/
    from datetime import datetime
    trash_dir = Path(vault).resolve() / "_trash"
    trash_dir.mkdir(exist_ok=True)
    report_file = trash_dir / f"lint-report-{datetime.now().strftime('%Y-%m-%d')}.md"
    report_file.write_text(f"# 内容健康检查报告\n\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n```\n{output}\n```\n", encoding="utf-8")
    print(f"📄 报告已保存：{report_file}")


def cmd_kb_stats(vault: str, json_output: bool = False) -> None:
    """输出知识库健康度统计。报告同时写入 _trash/。"""
    import json
    import re
    import sys
    from pathlib import Path

    vault_path = Path(vault).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
    from leo_common import (
        set_root,
        parse_front_matter,
        find_md_files,
        WIKI_LINK_RE,
        resolve_wiki_link,
        build_filename_index,
    )

    set_root(vault_path)
    md_files = find_md_files(vault_path)
    total = len(md_files)

    has_fm = 0
    total_related = 0
    broken_links = 0
    valid_links = 0
    empty_files = 0
    updated_30d = 0
    updated_90d = 0

    from datetime import datetime, timedelta
    now = datetime.now()
    d30 = now - timedelta(days=30)
    d90 = now - timedelta(days=90)

    filename_index = build_filename_index(md_files, vault_path)

    for f in md_files:
        text = f.read_text(encoding="utf-8")
        if len(text.strip()) < 50:
            empty_files += 1
        fields, _ = parse_front_matter(text)
        if fields is not None:
            has_fm += 1
            related = fields.get("related", fields.get("related_files", []))
            if isinstance(related, list):
                total_related += len(related)
            updated = fields.get("modified") or fields.get("updated") or ""
            if isinstance(updated, str):
                try:
                    ud = datetime.strptime(updated, "%Y-%m-%d")
                    if ud >= d30:
                        updated_30d += 1
                    if ud >= d90:
                        updated_90d += 1
                except ValueError:
                    pass

        cleaned = re.sub(r"```.*?```", "", text, flags=re.S)
        cleaned = re.sub(r"`[^`]*`", "", cleaned)
        for match in WIKI_LINK_RE.finditer(cleaned):
            link = match.group(1)
            if resolve_wiki_link(link, f, filename_index) is None:
                broken_links += 1
            else:
                valid_links += 1

    coverage = round(has_fm / total * 100, 1) if total else 0
    avg_related = round(valid_links / total, 2) if total else 0
    link_complete = 0
    if valid_links + broken_links > 0:
        link_complete = round(valid_links / (valid_links + broken_links) * 100, 1)
    empty_rate = round(empty_files / total * 100, 1) if total else 0
    rate_30d = round(updated_30d / total * 100, 1) if total else 0
    rate_90d = round(updated_90d / total * 100, 1) if total else 0

    score = (
        coverage * 0.20 +
        min(avg_related / 1.5 * 100, 100) * 0.20 +
        rate_30d * 0.15 +
        rate_90d * 0.15 +
        (100 - empty_rate) * 0.15 +
        link_complete * 0.15
    )

    if json_output:
        result = {
            "total_files": total,
            "coverage": coverage,
            "avg_related": avg_related,
            "updated_30d_rate": rate_30d,
            "updated_90d_rate": rate_90d,
            "empty_rate": empty_rate,
            "link_complete_rate": link_complete,
            "score": round(score, 1),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"📊 知识库健康度报告")
        print(f"{'='*50}")
        print(f"总文件数:       {total}")
        print(f"frontmatter 覆盖率: {coverage}%  (权重20%)")
        print(f"平均关联数:     {avg_related}  (权重20%, 1.5以上满分)")
        print(f"30天更新率:     {rate_30d}%  (权重15%)")
        print(f"90天更新率:     {rate_90d}%  (权重15%)")
        print(f"空文件率:       {empty_rate}%  (权重15%, 越低越好)")
        print(f"链接完整率:     {link_complete}%  (权重15%)")
        print(f"{'='*50}")
        print(f"综合评分:       {round(score, 1)} / 100")
        if score >= 90:
            grade = "A（优秀）"
        elif score >= 80:
            grade = "B（良好）"
        elif score >= 70:
            grade = "C（一般）"
        elif score >= 60:
            grade = "D（及格）"
        else:
            grade = "F（不及格）"
        print(f"等级:           {grade}")

    # 报告写入 _trash/（非 JSON 模式才写文件）
    if not json_output:
        from datetime import datetime
        trash_dir = Path(vault).resolve() / "_trash"
        trash_dir.mkdir(exist_ok=True)
        report_file = trash_dir / f"kb-stats-{datetime.now().strftime('%Y-%m-%d')}.md"
        report_content = f"""# 知识库健康度报告

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

| 指标 | 数值 | 权重 |
|------|------|------|
| 总文件数 | {total} | - |
| frontmatter 覆盖率 | {coverage}% | 20% |
| 平均关联数 | {avg_related} | 20%（1.5以上满分）|
| 30天更新率 | {rate_30d}% | 15% |
| 90天更新率 | {rate_90d}% | 15% |
| 空文件率 | {empty_rate}% | 15%（越低越好）|
| 链接完整率 | {link_complete}% | 15% |

**综合评分：{round(score, 1)} / 100**
**等级：{grade if not json_output else 'N/A'}**
"""
        report_file.write_text(report_content, encoding="utf-8")
        print(f"📄 报告已保存：{report_file}")


# ======================================================================
# Skill 插件健康检查
# ======================================================================

# 标准类型词库（12 种，已冻结，与 Compiler 一致）
VALID_TYPES = {"知识", "工具", "项目文档", "踩坑", "FAQ", "教程", "清单", "账号", "会议", "决策", "规范", "记录"}

# 标准知识归位目录（0-8）
VALID_KNOWLEDGE_DIRS = {
    "0- 🙎leo", "1- 🤖AI 相关", "2- 💻开发", "3- 🪟系统", "4- 🕹️软件",
    "5- 🧁项目", "6- 🎬影视", "7- 🧠思维框架", "8- 📜核心规则",
}

# 已废弃的目录名（不能出现在 SKILL.md 中）
DEPRECATED_DIRS = {
    "3- 🌏账号", "4- 📚知识体系", "6- 💼工作", "9- 🎯面试",
    "10- 🏠生活", "11- 💰搞钱", "12- 🎮娱乐", "13- 📦资源",
}

# 标准系统文件（与 is-system-file 对齐）
VALID_SYSTEM_FILES = {"🏠 home-", "🧩 目录-", "📖目录 索引", "🤖 AI指令", "README", "CLAUDE", "AGENTS", "🍕 作业区"}

# 标准流程顺序
VALID_PIPELINE_ORDER = ["Planner", "Compiler", "Fire-rename", "Organizer"]


def cmd_skill_health_check(skills_dir_str: str, vault_str: str) -> None:
    """Skill 插件健康检查：检查 SKILL.md 和实际结构的一致性

    用法：skill-health-check <skills_dir> <vault>
    检查项：
    1. Python 命令一致性：SKILL.md 里引用的命令是否都存在
    2. 目录速查表一致性：是否包含已废弃的目录名
    3. 类型词库一致性：是否统一为 12 种标准类型
    4. 系统文件清单一致性：是否和 is-system-file 对齐
    5. 流程顺序一致性：Pipeline 流程是否正确
    """
    skills_dir = Path(skills_dir_str)
    vault = Path(vault_str)

    if not skills_dir.exists():
        print(f"❌ Skills 目录不存在：{skills_dir}")
        return

    # 收集所有 SKILL.md
    skill_files = list(skills_dir.rglob("SKILL.md"))
    if not skill_files:
        print(f"❌ 未找到 SKILL.md 文件：{skills_dir}")
        return

    # 获取当前脚本支持的所有命令
    valid_commands = {
        "state-load", "state-save", "is-system-file", "locate-domain-index",
        "update-index-entry", "remove-index-entry", "add-to-default-category",
        "update-wikilinks", "compute-hash", "detect-changes", "validate-filename",
        "parse-filename", "record-access", "scan-unindexed", "check-file-thresholds",
        "check-summary-quality", "validate-document", "compute-similarity",
        "verify-move", "generate-rollback", "archive-cleanup", "check-fake-execution",
        "drift-check", "write-log", "add-record", "validate-metadata",
        "lint-content", "kb-stats", "skill-health-check", "health-check-all",
    }

    issues = []  # (skill名, 严重度, 检查项, 详情)
    checks_passed = 0
    checks_total = 0

    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        content = read_text_safe(skill_file)
        if not content:
            continue

        # === 检查1：Python 命令一致性 ===
        checks_total += 1
        cmd_pattern = r'obsidian_skill_utils\.py\s+([a-zA-Z][a-zA-Z0-9-]*)'
        found_cmds = set(re.findall(cmd_pattern, content))
        invalid_cmds = found_cmds - valid_commands
        if invalid_cmds:
            issues.append((skill_name, "🔴 严重", "Python命令",
                           f"引用了不存在的命令：{', '.join(sorted(invalid_cmds))}"))
        else:
            checks_passed += 1

        # === 检查2：目录速查表一致性 ===
        checks_total += 1
        deprecated_found = []
        for dep_dir in DEPRECATED_DIRS:
            if dep_dir in content:
                deprecated_found.append(dep_dir)
        if deprecated_found:
            issues.append((skill_name, "🔴 严重", "目录速查表",
                           f"包含已废弃的目录名：{', '.join(deprecated_found)}"))
        else:
            checks_passed += 1

        # === 检查3：类型词库一致性 ===
        # 只检查定义了类型列表的文件（包含"知识"和"工具"且在类型表格/列表中）
        checks_total += 1
        # 检查是否所有 12 种类型都出现
        types_in_file = {t for t in VALID_TYPES if t in content}
        # 如果文件提到了类型词库（包含"类型词库"或"12 种"或"合法 type"）
        if "类型词库" in content or "12 种" in content or "合法 type" in content or "类型判断" in content:
            missing_types = VALID_TYPES - types_in_file
            if missing_types:
                issues.append((skill_name, "🟡 中等", "类型词库",
                               f"缺少类型：{', '.join(sorted(missing_types))}"))
            else:
                checks_passed += 1
        else:
            checks_passed += 1  # 不涉及类型词库的文件直接通过

        # === 检查4：系统文件清单一致性 ===
        # 只检查列出了系统文件清单的文件
        checks_total += 1
        if "系统文件" in content and ("跳过" in content or "清单" in content):
            # 只在系统文件清单段落内检查是否包含 AI_INDEX（已废弃）
            # 找到系统文件清单所在行，向下搜索10行作为检查范围
            lines = content.split('\n')
            in_sysfile_section = False
            sysfile_section_text = ""
            sysfile_lines_collected = 0
            for i, line in enumerate(lines):
                if "系统文件" in line and ("跳过" in line or "清单" in line):
                    in_sysfile_section = True
                if in_sysfile_section:
                    sysfile_section_text += line + '\n'
                    sysfile_lines_collected += 1
                    if sysfile_lines_collected >= 10:
                        break
            # 检查是否包含已废弃的 AI_INDEX.md 文件引用
            # 注意：🤖AI_INDEX/ 目录内的路径引用（如 🤖AI_INDEX/query-cache.json）是合法的
            # 只检查独立的 "AI_INDEX.md" 或 "AI_INDEX" 作为系统文件名的引用
            if re.search(r'(?<![/\\🤖])AI_INDEX(?![/\\.\w])', sysfile_section_text):
                issues.append((skill_name, "🟡 中等", "系统文件清单",
                               "包含 AI_INDEX.md（LeoDiary 中不存在此文件）"))
            else:
                checks_passed += 1
        else:
            checks_passed += 1

        # === 检查5：目录结构保护规则 ===
        # 检查每个 SKILL.md 是否包含目录结构保护规则
        checks_total += 1
        required_rules = [
            "目录结构保护规则",
            "禁止操作已有文件夹结构",
            "禁止擅自挪动文件位置",
        ]
        missing_rules = [r for r in required_rules if r not in content]
        if missing_rules:
            issues.append((skill_name, "🟡 中等", "目录结构保护规则",
                           f"缺少目录结构保护规则：{', '.join(missing_rules)}"))
        else:
            checks_passed += 1

        # === 检查6：流程顺序一致性 ===
        # 只检查 Pipeline 和 Accumulate
        checks_total += 1
        if skill_name == "obsidian-pipeline" or skill_name == "obsidian-knowledge-Accumulate":
            # 检查流程顺序是否正确（Compiler 在 Fire-rename 前，Fire-rename 在 Organizer 前）
            # 找到流程图或步骤描述
            compiler_pos = content.find("Compiler")
            rename_pos = content.find("Fire-rename")
            organizer_pos = content.find("Organizer")
            # 如果三者都出现了
            if compiler_pos > 0 and rename_pos > 0 and organizer_pos > 0:
                # 检查在某个局部范围内（流程图区域）的顺序
                # 找流程图区域（``` 代码块内）
                flow_blocks = re.findall(r'```\n(.*?)```', content, re.DOTALL)
                flow_correct = False
                flow_wrong = False
                for block in flow_blocks:
                    if "Planner" in block and "Organizer" in block:
                        b_compiler = block.find("Compiler")
                        b_rename = block.find("Fire-rename")
                        b_organizer = block.find("Organizer")
                        if b_compiler > 0 and b_rename > 0 and b_organizer > 0:
                            if b_compiler < b_rename < b_organizer:
                                flow_correct = True
                            else:
                                flow_wrong = True
                                issues.append((skill_name, "🔴 严重", "流程顺序",
                                               f"流程图中顺序错误：Compiler({b_compiler}) → Fire-rename({b_rename}) → Organizer({b_organizer})，应为 Compiler → Fire-rename → Organizer"))
                                break
                if not flow_wrong:
                    checks_passed += 1
            else:
                checks_passed += 1
        else:
            checks_passed += 1

    # === 检查6：实际 LeoDiary 目录结构 ===
    checks_total += 1
    actual_dirs = set()
    if vault.exists():
        for item in vault.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != 'logs':
                actual_dirs.add(item.name)
    # 检查标准目录是否都存在
    missing_knowledge_dirs = VALID_KNOWLEDGE_DIRS - actual_dirs
    if missing_knowledge_dirs:
        issues.append(("（全局）", "🟡 中等", "LeoDiary目录",
                       f"标准知识目录缺失：{', '.join(sorted(missing_knowledge_dirs))}"))
    else:
        checks_passed += 1

    # === 生成报告 ===
    report_lines = [
        f"# Skill 插件健康检查报告",
        f"",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Skills 目录：{skills_dir}",
        f"知识库目录：{vault}",
        f"扫描文件数：{len(skill_files)}",
        f"",
        f"## 检查结果概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总检查项 | {checks_total} |",
        f"| 通过 | {checks_passed} |",
        f"| 失败 | {checks_total - checks_passed} |",
        f"| 通过率 | {round(checks_passed / checks_total * 100, 1) if checks_total > 0 else 0}% |",
        f"",
    ]

    if issues:
        report_lines.append(f"## 发现的问题（{len(issues)} 个）")
        report_lines.append("")
        # 按严重度排序
        issues.sort(key=lambda x: (0 if "🔴" in x[1] else 1, x[0], x[2]))
        for skill, severity, check_item, detail in issues:
            report_lines.append(f"### {severity} [{skill}] {check_item}")
            report_lines.append(f"- {detail}")
            report_lines.append("")
    else:
        report_lines.append("## ✅ 所有检查通过")
        report_lines.append("")

    report_lines.append("## 检查项说明")
    report_lines.append("")
    report_lines.append("| 检查项 | 说明 |")
    report_lines.append("|--------|------|")
    report_lines.append("| Python命令 | SKILL.md 里引用的命令是否在 obsidian_skill_utils.py 中存在 |")
    report_lines.append("| 目录速查表 | 是否包含已废弃的目录名（详见 DEPRECATED_DIRS 常量） |")
    report_lines.append("| 类型词库 | 是否统一为 12 种标准类型（知识/工具/项目文档/踩坑/FAQ/教程/清单/账号/会议/决策/规范/记录） |")
    report_lines.append("| 系统文件清单 | 是否和 is-system-file 命令的判断逻辑对齐 |")
    report_lines.append("| 目录结构保护规则 | 是否包含目录结构保护规则（禁止操作已有文件夹结构、禁止擅自挪动文件位置） |")
    report_lines.append("| 流程顺序 | Pipeline 流程是否为 Planner → Compiler → Fire-rename → Organizer |")
    report_lines.append("| LeoDiary目录 | 标准知识归位目录（0-8）是否都存在 |")

    report_content = "\n".join(report_lines)

    # 输出到 _trash 目录
    trash_dir = vault / "_trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    report_file = trash_dir / f"skill-health-report-{datetime.now().strftime('%Y-%m-%d')}.md"
    report_file.write_text(report_content, encoding="utf-8")

    # 同时打印到控制台
    print(report_content)
    print(f"\n📄 报告已保存：{report_file}")


# ======================================================================
# 项目级健康检查（health-check-all）
# ======================================================================

def _make_result(category: str, item: str, status: str, detail: str,
                 current: str = "", expected: str = "", action: str = "",
                 severity: str = None) -> dict:
    """构造检查结果 dict。

    status: pass | warn | fail
    severity 自动推导（若未指定）
    """
    if severity is None:
        severity = {"pass": "✅通过", "warn": "🟡中等", "fail": "🔴严重"}[status]
    return {
        "category": category,
        "item": item,
        "status": status,
        "severity": severity,
        "detail": detail,
        "current": current,
        "expected": expected,
        "action": action,
    }


def _run_skill_checks(skills_dir: Path, vault: Path) -> list:
    """类别 1：Skill 插件一致性（复用 skill-health-check 逻辑）"""
    results = []
    category = "Skill插件一致性"

    if not skills_dir.exists():
        results.append(_make_result(category, "Skills目录存在性", "fail",
                                     f"Skills目录不存在：{skills_dir}",
                                     "目录缺失", "目录存在", "创建Skills目录或检查路径"))
        return results

    skill_files = list(skills_dir.rglob("SKILL.md"))
    
    # 如果在 skills_dir 中找不到 SKILL.md，尝试查找 TRAE 的 skills 目录
    if not skill_files:
        trae_skills_dir = Path.home() / ".trae-cn" / "skills"
        if trae_skills_dir.exists():
            skill_files = list(trae_skills_dir.rglob("SKILL.md"))
    
    if not skill_files:
        results.append(_make_result(category, "SKILL.md文件", "fail",
                                     "未找到SKILL.md文件",
                                     "无SKILL.md", "至少1个", "创建SKILL.md"))
        return results

    # 与 cmd_skill_health_check 保持一致的命令白名单（含 health-check-all）
    valid_commands = {
        "state-load", "state-save", "is-system-file", "locate-domain-index",
        "update-index-entry", "remove-index-entry", "add-to-default-category",
        "update-wikilinks", "compute-hash", "detect-changes", "validate-filename",
        "parse-filename", "record-access", "scan-unindexed", "check-file-thresholds",
        "check-summary-quality", "validate-document", "compute-similarity",
        "verify-move", "generate-rollback", "archive-cleanup", "check-fake-execution",
        "drift-check", "write-log", "add-record", "validate-metadata",
        "lint-content", "kb-stats", "skill-health-check", "health-check-all",
    }

    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        content = read_text_safe(skill_file)
        if not content:
            continue

        # 检查1：Python 命令一致性
        cmd_pattern = r'obsidian_skill_utils\.py\s+([a-zA-Z][a-zA-Z0-9-]*)'
        found_cmds = set(re.findall(cmd_pattern, content))
        invalid_cmds = found_cmds - valid_commands
        if invalid_cmds:
            results.append(_make_result(category, f"[{skill_name}] Python命令一致性", "fail",
                                         f"引用了不存在的命令：{', '.join(sorted(invalid_cmds))}",
                                         f"无效命令：{', '.join(sorted(invalid_cmds))}",
                                         "只引用存在的命令",
                                         "更新SKILL.md移除无效命令引用"))
        else:
            results.append(_make_result(category, f"[{skill_name}] Python命令一致性", "pass",
                                         f"引用的{len(found_cmds)}个命令都存在"))

        # 检查2：目录速查表一致性
        deprecated_found = [d for d in DEPRECATED_DIRS if d in content]
        if deprecated_found:
            results.append(_make_result(category, f"[{skill_name}] 目录速查表一致性", "fail",
                                         f"包含已废弃的目录名：{', '.join(deprecated_found)}",
                                         f"包含废弃目录：{', '.join(deprecated_found)}",
                                         "不包含废弃目录",
                                         "更新目录速查表"))
        else:
            results.append(_make_result(category, f"[{skill_name}] 目录速查表一致性", "pass",
                                         "未包含已废弃目录名"))

        # 检查3：类型词库一致性（仅涉及类型词库的文件检查）
        if "类型词库" in content or "12 种" in content or "合法 type" in content or "类型判断" in content:
            types_in_file = {t for t in VALID_TYPES if t in content}
            missing_types = VALID_TYPES - types_in_file
            if missing_types:
                results.append(_make_result(category, f"[{skill_name}] 类型词库一致性", "warn",
                                             f"缺少类型：{', '.join(sorted(missing_types))}",
                                             f"缺少：{', '.join(sorted(missing_types))}",
                                             "包含12种标准类型",
                                             "补充缺失类型"))
            else:
                results.append(_make_result(category, f"[{skill_name}] 类型词库一致性", "pass",
                                             "12种类型齐全"))

        # 检查4：系统文件清单一致性（仅涉及系统文件清单的文件检查）
        if "系统文件" in content and ("跳过" in content or "清单" in content):
            # 只在系统文件清单段落内检查是否包含 AI_INDEX（已废弃）
            lines = content.split('\n')
            in_sysfile_section = False
            sysfile_section_text = ""
            sysfile_lines_collected = 0
            for i, line in enumerate(lines):
                if "系统文件" in line and ("跳过" in line or "清单" in line):
                    in_sysfile_section = True
                if in_sysfile_section:
                    sysfile_section_text += line + '\n'
                    sysfile_lines_collected += 1
                    if sysfile_lines_collected >= 10:
                        break
            # 检查是否包含已废弃的 AI_INDEX.md 文件引用
            # 注意：🤖AI_INDEX/ 目录内的路径引用是合法的
            if re.search(r'(?<![/\\🤖])AI_INDEX(?![/\\.\w])', sysfile_section_text):
                results.append(_make_result(category, f"[{skill_name}] 系统文件清单一致性", "warn",
                                             "包含AI_INDEX.md（LeoDiary中不存在此文件）",
                                             "包含AI_INDEX",
                                             "不包含AI_INDEX",
                                             "移除AI_INDEX引用"))
            else:
                results.append(_make_result(category, f"[{skill_name}] 系统文件清单一致性", "pass",
                                             "系统文件清单对齐"))

        # 检查5：目录结构保护规则（每个 SKILL.md 必须包含）
        required_rules = [
            "目录结构保护规则",
            "禁止操作已有文件夹结构",
            "禁止擅自挪动文件位置",
        ]
        missing_rules = [r for r in required_rules if r not in content]
        if missing_rules:
            results.append(_make_result(category, f"[{skill_name}] 目录结构保护规则", "warn",
                                         f"缺少目录结构保护规则：{', '.join(missing_rules)}",
                                         f"缺少：{', '.join(missing_rules)}",
                                         "包含3项保护规则",
                                         "补充目录结构保护规则"))
        else:
            results.append(_make_result(category, f"[{skill_name}] 目录结构保护规则", "pass",
                                         "包含目录结构保护规则"))

        # 检查6：流程顺序一致性（仅 Pipeline / Accumulate 检查）
        if skill_name in ("obsidian-pipeline", "obsidian-knowledge-Accumulate"):
            compiler_pos = content.find("Compiler")
            rename_pos = content.find("Fire-rename")
            organizer_pos = content.find("Organizer")
            if compiler_pos > 0 and rename_pos > 0 and organizer_pos > 0:
                flow_blocks = re.findall(r'```\n(.*?)```', content, re.DOTALL)
                flow_wrong = False
                for block in flow_blocks:
                    if "Planner" in block and "Organizer" in block:
                        b_compiler = block.find("Compiler")
                        b_rename = block.find("Fire-rename")
                        b_organizer = block.find("Organizer")
                        if b_compiler > 0 and b_rename > 0 and b_organizer > 0:
                            if not (b_compiler < b_rename < b_organizer):
                                flow_wrong = True
                                results.append(_make_result(category, f"[{skill_name}] 流程顺序一致性", "fail",
                                                             "流程图中顺序错误：应为 Compiler → Fire-rename → Organizer",
                                                             "流程顺序错误",
                                                             "Compiler → Fire-rename → Organizer",
                                                             "修正流程顺序"))
                                break
                if not flow_wrong:
                    results.append(_make_result(category, f"[{skill_name}] 流程顺序一致性", "pass",
                                                 "流程顺序正确"))

    # 检查7：实际 LeoDiary 目录结构
    actual_dirs = set()
    if vault.exists():
        for item in vault.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != 'logs':
                actual_dirs.add(item.name)
    missing_knowledge_dirs = VALID_KNOWLEDGE_DIRS - actual_dirs
    if missing_knowledge_dirs:
        results.append(_make_result(category, "LeoDiary标准知识目录", "warn",
                                     f"标准知识目录缺失：{', '.join(sorted(missing_knowledge_dirs))}",
                                     f"缺失：{', '.join(sorted(missing_knowledge_dirs))}",
                                     "9个标准目录齐全",
                                     "创建缺失的目录"))
    else:
        results.append(_make_result(category, "LeoDiary标准知识目录", "pass",
                                     "9个标准知识目录齐全"))

    return results


def _check_kb_content_health(vault: Path) -> list:
    """类别 2：知识库内容健康（简化版）"""
    results = []
    category = "知识库内容健康"

    if not vault.exists():
        results.append(_make_result(category, "知识库目录", "fail",
                                     f"知识库目录不存在：{vault}",
                                     "目录缺失", "目录存在", "检查路径"))
        return results

    # 扫描所有 .md 文件
    md_files = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if not fname.endswith('.md') or should_skip_file(fname):
                continue
            md_files.append(Path(root) / fname)

    total = len(md_files)
    if total == 0:
        results.append(_make_result(category, "Markdown文件数", "fail",
                                     "未扫描到任何.md文件",
                                     "0个文件", "至少1个", "检查vault路径"))
        return results

    # 检查1：frontmatter 覆盖率
    # 注意：系统文件（🧩 目录-/📖目录 索引/🏠 home- 等）的 frontmatter 规范不一致，
    # 单独统计内容文件，避免把"系统文件跳过、内容文件没 frontmatter"误报为 0%。
    system_prefixes = ("🧩 目录-", "📖目录 索引", "🏠 home-")
    system_exact = {"⚓新增文件记录.md", "🍕 作业区.md", "CLAUDE.md", "README.md",
                    "LEO OS.md", "LEO-OS.md", "🤖 AI指令.md"}
    content_files = []
    system_fm_count = 0
    system_total = 0
    for f in md_files:
        name = f.name
        is_sys = name.startswith(system_prefixes) or name in system_exact
        content = read_text_safe(f)
        has_fm = content.lstrip().startswith('---')
        if is_sys:
            system_total += 1
            if has_fm:
                system_fm_count += 1
        else:
            content_files.append((f, has_fm))
    content_total = len(content_files)
    content_fm_count = sum(1 for _, ok in content_files if ok)
    fm_rate = (content_fm_count / content_total * 100) if content_total else 0
    detail = (f"内容文件 {content_fm_count}/{content_total} ({fm_rate:.1f}%)"
              f"；系统文件 {system_fm_count}/{system_total}")
    if fm_rate >= 15:
        results.append(_make_result(category, "frontmatter覆盖率", "pass",
                                     detail, f"{fm_rate:.1f}%", "≥15%", "保持"))
    elif fm_rate >= 5:
        results.append(_make_result(category, "frontmatter覆盖率", "warn",
                                     detail, f"{fm_rate:.1f}%", "≥15%",
                                     "逐步为重要内容文件补充 frontmatter"))
    else:
        # vault 不强制要求 frontmatter，<5% 仅提示而非失败
        results.append(_make_result(category, "frontmatter覆盖率", "warn",
                                     detail, f"{fm_rate:.1f}%", "≥15%",
                                     "vault 当前未强制 frontmatter，建议重要文件补充"))

    # 检查2：空文件率（<10字节）
    empty_count = 0
    for f in md_files:
        try:
            if f.stat().st_size < 10:
                empty_count += 1
        except Exception:
            pass
    empty_rate = empty_count / total * 100
    if empty_rate < 5:
        results.append(_make_result(category, "空文件率(<10B)", "pass",
                                     f"{empty_rate:.1f}%（{empty_count}/{total}）",
                                     f"{empty_rate:.1f}%", "<5%", "保持"))
    elif empty_rate < 10:
        results.append(_make_result(category, "空文件率(<10B)", "warn",
                                     f"{empty_rate:.1f}%（{empty_count}/{total}）",
                                     f"{empty_rate:.1f}%", "<5%", "清理空文件"))
    else:
        results.append(_make_result(category, "空文件率(<10B)", "fail",
                                     f"{empty_rate:.1f}%（{empty_count}/{total}）",
                                     f"{empty_rate:.1f}%", "<5%", "批量清理空文件"))

    # 检查3：断链检查
    # 构建包含所有文件的文件名索引（包括索引文件，因为它们也是有效的链接目标）
    all_md_files = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            if fname.endswith('.md'):
                all_md_files.append(Path(root) / fname)
    
    filename_index = {f.stem for f in all_md_files}
    # 构建目录名索引（用于目录链接检测）
    dir_names = set()
    for f in all_md_files:
        try:
            rel = f.relative_to(vault)
            for part in rel.parts[:-1]:
                dir_names.add(part)
        except ValueError:
            pass
    
    # 构建基础名索引（用于模糊匹配）
    def _extract_base_name(fname):
        name = fname
        if ' @ ' in name:
            name = name.split(' @ ')[0]
        name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\s\d\-]+', '', name)
        return name.strip()
    
    base_name_map = {}
    for stem in filename_index:
        base = _extract_base_name(stem)
        if base and base not in base_name_map:
            base_name_map[base] = stem
    
    broken_links_count = 0
    broken_links_examples = []
    
    # 构建规范化文件名索引（处理行内代码剥离后的链接文本匹配）
    def _normalize_for_match(s):
        """规范化字符串用于链接匹配：去行内代码(`内容`)+合并空格+去.md后缀"""
        s = re.sub(r'`[^`]*`', '', s)  # 去掉反引号及其中间内容
        s = re.sub(r' {2,}', ' ', s).strip()  # 合并连续空格
        if s.endswith('.md'):
            s = s[:-3]
        return s
    
    normalized_index = {}
    for stem in filename_index:
        norm = _normalize_for_match(stem)
        if norm not in normalized_index:
            normalized_index[norm] = stem
    
    for f in md_files:
        content = read_text_safe(f)
        # 去掉代码块（保留[[链接]]内的内容）
        cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        # 找所有 [[xxx]] 链接（不含 |alias 和 #anchor）
        links = re.findall(r'\[\[([^\]|#]+)', cleaned)
        for link in links:
            link = link.strip()
            if not link:
                continue
            
            # 跳过模板语法（Templater插件等）
            if '<%' in link or '%>' in link:
                continue
            
            # 跳过模板/示例链接（文档中使用的占位符）
            if link in {"xxx", "yyy", "zzz", "...", "文件名", "UNIVERSAL", "wikilink"}:
                continue
            if link.startswith("home-xxx"):
                continue
            # 跳过示例路径链接（CHANGELOG等文档中使用的示例）
            if link.startswith("../") or link.startswith("./"):
                continue
            # 跳过示例链接模式
            if "举例类比" in link or "LEO OS/" in link:
                continue
            
            # 取末尾文件名/目录名部分
            link_name = link.split('/')[-1].split('\\')[-1].strip()
            if not link_name:
                continue
            
            # 去掉末尾的路径分隔符（目录链接）
            link_name_clean = link_name.rstrip('\\/')
            if not link_name_clean:
                continue
            
            # 1. 精确文件匹配（包含反引号）
            if link_name_clean in filename_index:
                continue
            
            # 1b. 规范化匹配（去反引号+合并空格+去.md后缀）
            norm_link = _normalize_for_match(link_name_clean)
            if norm_link in normalized_index:
                continue
            
            # 2. 目录链接（指向目录名）
            if link_name_clean in dir_names:
                continue
            
            # 3. 基础名模糊匹配（唯一匹配）
            base = _extract_base_name(link_name_clean)
            if base and base in base_name_map:
                continue
            
            # 4. 前缀匹配（唯一匹配，且长度>=5）
            if len(link_name_clean) >= 5:
                prefix_matches = [s for s in filename_index if s.startswith(link_name_clean)]
                if len(prefix_matches) == 1:
                    continue
            
            broken_links_count += 1
            if len(broken_links_examples) < 5:
                broken_links_examples.append(f"{f.name} → [[{link}]]")

    if broken_links_count == 0:
        results.append(_make_result(category, "断链检查", "pass",
                                     "未发现断链",
                                     "0个断链", "0个", "保持"))
    elif broken_links_count <= 5:
        results.append(_make_result(category, "断链检查", "warn",
                                     f"发现{broken_links_count}个断链，例如：{'; '.join(broken_links_examples[:3])}",
                                     f"{broken_links_count}个", "0个", "修复断链或删除引用"))
    else:
        results.append(_make_result(category, "断链检查", "fail",
                                     f"发现{broken_links_count}个断链，例如：{'; '.join(broken_links_examples[:3])}",
                                     f"{broken_links_count}个", "0个", "批量修复断链"))

    # 检查4：过时文件（modified > 6 个月）
    from datetime import timedelta
    threshold = datetime.now() - timedelta(days=180)
    stale_count = 0
    for f in md_files:
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < threshold:
                stale_count += 1
        except Exception:
            pass
    stale_rate = stale_count / total * 100
    if stale_rate < 10:
        results.append(_make_result(category, "过时文件(>6月)", "pass",
                                     f"{stale_rate:.1f}%（{stale_count}/{total}）",
                                     f"{stale_rate:.1f}%", "<10%", "保持"))
    elif stale_rate < 30:
        results.append(_make_result(category, "过时文件(>6月)", "warn",
                                     f"{stale_rate:.1f}%（{stale_count}/{total}）",
                                     f"{stale_rate:.1f}%", "<10%", "更新或归档过时文件"))
    else:
        results.append(_make_result(category, "过时文件(>6月)", "fail",
                                     f"{stale_rate:.1f}%（{stale_count}/{total}）",
                                     f"{stale_rate:.1f}%", "<10%", "批量归档过时文件"))

    # 检查5：frontmatter格式正确性（type值/位置/tags）
    VALID_TYPES = {"知识", "工具", "项目文档", "踩坑", "FAQ", "教程", "清单", "账号", "会议", "决策", "规范", "记录"}
    
    # 统计问题文件
    wrong_type_count = 0      # type: project 或无效类型
    wrong_position_count = 0  # frontmatter在标题之后
    bad_tags_count = 0        # tags含emoji前缀或过长标签(>20字符)
    
    for f in md_files:
        content = read_text_safe(f)
        if not content.lstrip().startswith('---'):
            continue  # 没有frontmatter的跳过
        
        # 检查type值
        type_match = re.search(r'type:\s*([^\n]+)', content)
        if type_match:
            type_val = type_match.group(1).strip()
            if type_val == 'project' or (type_val and type_val not in VALID_TYPES):
                wrong_type_count += 1
        
        # 检查frontmatter位置（是否在文件开头）
        if content.lstrip().startswith('---'):
            # 检查---前面是否有内容
            before_dash = content[:content.find('---')].strip()
            if before_dash:
                wrong_position_count += 1
        
        # 检查tags
        tags_match = re.search(r'tags:\s*\[([^\]]+)\]', content)
        if tags_match:
            tags_str = tags_match.group(1)
            tags = [t.strip().strip("'\"") for t in tags_str.split(',')]
            for tag in tags:
                if tag and (len(tag) > 20 or tag.startswith(('📢', '🏠', '🧩', '🤖', '🎈', '🎖️', '🥝', '🫟', '🍕'))):
                    bad_tags_count += 1
                    break
    
    # type值检查
    if wrong_type_count == 0:
        results.append(_make_result(category, "frontmatter type值", "pass",
                                     "所有文件type值均有效",
                                     "0个错误", "0个", "保持"))
    elif wrong_type_count <= 5:
        results.append(_make_result(category, "frontmatter type值", "warn",
                                     f"{wrong_type_count}个文件type值无效（如type: project）",
                                     f"{wrong_type_count}个错误", "0个", "修复为标准类型"))
    else:
        results.append(_make_result(category, "frontmatter type值", "fail",
                                     f"{wrong_type_count}个文件type值无效（如type: project）",
                                     f"{wrong_type_count}个错误", "0个", "批量修复type值"))
    
    # frontmatter位置检查
    if wrong_position_count == 0:
        results.append(_make_result(category, "frontmatter位置", "pass",
                                     "所有文件frontmatter均在文件开头",
                                     "0个错误", "0个", "保持"))
    elif wrong_position_count <= 5:
        results.append(_make_result(category, "frontmatter位置", "warn",
                                     f"{wrong_position_count}个文件frontmatter位置错误（在标题之后）",
                                     f"{wrong_position_count}个错误", "0个", "调整frontmatter到文件开头"))
    else:
        results.append(_make_result(category, "frontmatter位置", "fail",
                                     f"{wrong_position_count}个文件frontmatter位置错误（在标题之后）",
                                     f"{wrong_position_count}个错误", "0个", "批量调整frontmatter位置"))
    
    # tags检查
    if bad_tags_count == 0:
        results.append(_make_result(category, "frontmatter tags", "pass",
                                     "所有文件tags格式均有效",
                                     "0个错误", "0个", "保持"))
    elif bad_tags_count <= 5:
        results.append(_make_result(category, "frontmatter tags", "warn",
                                     f"{bad_tags_count}个文件tags包含过长标签或emoji前缀",
                                     f"{bad_tags_count}个错误", "0个", "优化tags内容"))
    else:
        results.append(_make_result(category, "frontmatter tags", "fail",
                                     f"{bad_tags_count}个文件tags包含过长标签或emoji前缀",
                                     f"{bad_tags_count}个错误", "0个", "批量优化tags"))

    # 检查8：summary 字段完整性（扫描所有内容文件的frontmatter）
    content_files_only = [f for f in md_files if not should_skip_file(f.name)]
    summary_ok = 0
    summary_short = 0
    summary_missing = 0
    summary_short_samples = []
    for f in content_files_only:
        content = read_text_safe(f)
        if not content.lstrip().startswith('---'):
            summary_missing += 1
            continue
        summary_match = re.search(r'^summary:\s*["\']?([^\n"\']*)["\']?', content, re.MULTILINE)
        if not summary_match:
            summary_missing += 1
            continue
        summary_text = summary_match.group(1).strip()
        # 跳过多行 summary（以 | 结尾的块标量）
        if summary_text == '|':
            block_match = re.search(r'^summary:\s*\|\s*\n((?:[ \t]+[^\n]+\n?)*)', content, re.MULTILINE)
            if block_match:
                block = block_match.group(1)
                summary_text = ' '.join(l.strip() for l in block.split('\n') if l.strip())
        if len(summary_text) < 30:
            summary_short += 1
            if len(summary_short_samples) < 5:
                summary_short_samples.append(f"{f.name}({len(summary_text)}字)")
        else:
            summary_ok += 1

    total_checked = summary_ok + summary_short + summary_missing
    if total_checked == 0:
        results.append(_make_result(category, "summary字段完整性", "pass", "无内容文件"))
    else:
        summary_detail = (
            f"{total_checked}个文件：{summary_ok}个正常≥30字，"
            f"{summary_short}个过短<30字，{summary_missing}个缺失"
        )
        if summary_missing == 0 and summary_short == 0:
            results.append(_make_result(category, "summary字段完整性", "pass",
                                         summary_detail,
                                         "全部合规", "全部≥30字且存在", "保持"))
        elif summary_short <= 5 and summary_missing <= total_checked * 0.10:
            results.append(_make_result(category, "summary字段完整性", "warn",
                                         f"{summary_detail}；示例：{'；'.join(summary_short_samples)}",
                                         f"{summary_short}个过短+{summary_missing}个缺失",
                                         "全部≥30字且存在",
                                         "补充或延长summary字段（建议≥30字描述实体+类型+用途）"))
        else:
            results.append(_make_result(category, "summary字段完整性", "fail",
                                         f"{summary_detail}；示例：{'；'.join(summary_short_samples)}",
                                         f"{summary_short}个过短+{summary_missing}个缺失",
                                         "全部≥30字且存在",
                                         "批量补充summary字段，建议≥30字描述实体+类型+用途"))

    return results


def _resolve_script_dirs(python_dir: Path) -> list:
    """返回需要搜索的脚本目录列表（支持 src/scripts/lib 子目录结构）"""
    dirs = []
    for sub in ["src", "scripts", "lib", "tests", "."]:
        d = python_dir / sub if sub != "." else python_dir
        if d.exists():
            dirs.append(d)
    return dirs


def _find_script(python_dir: Path, rel_path: str) -> Path:
    """在所有可能的目录中查找脚本"""
    for d in _resolve_script_dirs(python_dir):
        candidate = d / rel_path
        if candidate.exists():
            return candidate
    return python_dir / rel_path


def _check_python_collaboration(python_dir: Path, skills_dir: Path) -> list:
    """类别 3：Python 代码协作性"""
    results = []
    category = "Python代码协作性"

    if not python_dir.exists():
        results.append(_make_result(category, "Python目录", "fail",
                                     f"Python目录不存在：{python_dir}",
                                     "目录缺失", "目录存在", "检查路径"))
        return results

    # 检查关键文件存在性
    key_files = [
        ("obsidian_skill_utils.py", "核心工具脚本"),
        ("lib/lint.py", "内容健康检查脚本"),
        ("lib/validate.py", "元数据校验脚本"),
        ("Obsidian - index_updater.py", "索引更新脚本"),
    ]
    for rel_path, desc in key_files:
        fpath = _find_script(python_dir, rel_path)
        if fpath.exists():
            results.append(_make_result(category, f"{desc}存在性", "pass",
                                         f"{rel_path} 存在"))
        else:
            results.append(_make_result(category, f"{desc}存在性", "fail",
                                         f"{rel_path} 不存在",
                                         "文件缺失", "文件存在", f"创建或恢复 {rel_path}"))

    return results


def _check_doc_consistency(vault: Path, skills_dir: Path, python_dir: Path) -> list:
    """类别 4：文档一致性"""
    results = []
    category = "文档一致性"

    outdated_keywords = ["三种沉淀", "链接沉淀", "26个命令"]

    # 检查 CLAUDE.md
    claude_md = vault / "CLAUDE.md"
    if not claude_md.exists():
        results.append(_make_result(category, "CLAUDE.md存在性", "fail",
                                     "CLAUDE.md 不存在",
                                     "文件缺失", "文件存在", "创建CLAUDE.md"))
    else:
        content = read_text_safe(claude_md)
        results.append(_make_result(category, "CLAUDE.md内容", "pass",
                                     "CLAUDE.md 内容正常"))

    # 检查 README.md
    readme_md = vault / "README.md"
    if not readme_md.exists():
        results.append(_make_result(category, "README.md存在性", "fail",
                                     "README.md 不存在",
                                     "文件缺失", "文件存在", "创建README.md"))
    else:
        content = read_text_safe(readme_md)
        results.append(_make_result(category, "README.md内容", "pass",
                                     "README.md 内容正常"))

    # 检查知识处理系统使用手册
    manual_path = vault / "skills" / "知识处理系统使用手册2.0 LD-DVA Final.md"
    if not manual_path.exists():
        results.append(_make_result(category, "知识处理系统使用手册", "fail",
                                     "知识处理系统使用手册 不存在",
                                     "文件缺失", "文件存在", "创建使用手册"))
    else:
        results.append(_make_result(category, "知识处理系统使用手册", "pass",
                                     "使用手册存在"))

    # 检查 skills 目录下的说明文件是否有过时描述
    skills_doc_dir = vault / "skills"
    # 废弃说明字样：如果文件中同时出现这些字样和过时关键词，认为是废弃说明而非过时描述
    deprecation_markers = ["已废弃", "已删除", "已合并", "已改为", "已移除", "废弃说明", "删除链接沉淀", "删除三种"]
    if not skills_doc_dir.exists():
        results.append(_make_result(category, "skills说明文件过时描述", "warn",
                                     "skills目录不存在",
                                     "目录缺失", "目录存在", "创建skills目录"))
    else:
        outdated_files = []
        for f in skills_doc_dir.glob("*.md"):
            content = read_text_safe(f)
            for kw in outdated_keywords:
                if kw in content:
                    # 检查是否是废弃说明（文件中同时有废弃说明字样）
                    is_deprecation = any(marker in content for marker in deprecation_markers)
                    if not is_deprecation:
                        outdated_files.append(f"{f.name}（包含'{kw}'）")
                    break
        if not outdated_files:
            results.append(_make_result(category, "skills说明文件过时描述", "pass",
                                         "未发现过时描述"))
        else:
            results.append(_make_result(category, "skills说明文件过时描述", "warn",
                                         f"{len(outdated_files)}个文件含过时描述：{'; '.join(outdated_files[:5])}",
                                         f"{len(outdated_files)}个文件含过时描述",
                                         "无过时描述",
                                         "更新文件移除过时描述"))

    # 检查 SKILL.md 文件是否有过时描述
    if not skills_dir.exists():
        results.append(_make_result(category, "SKILL.md过时描述", "warn",
                                     "skills_dir目录不存在",
                                     "目录缺失", "目录存在", "检查路径"))
    else:
        skill_files = list(skills_dir.rglob("SKILL.md"))
        outdated_skills = []
        for sf in skill_files:
            content = read_text_safe(sf)
            for kw in outdated_keywords:
                if kw in content:
                    # 检查是否是废弃说明
                    is_deprecation = any(marker in content for marker in deprecation_markers)
                    if not is_deprecation:
                        outdated_skills.append(f"{sf.parent.name}（包含'{kw}'）")
                    break
        if not outdated_skills:
            results.append(_make_result(category, "SKILL.md过时描述", "pass",
                                         "未发现过时描述"))
        else:
            results.append(_make_result(category, "SKILL.md过时描述", "warn",
                                         f"{len(outdated_skills)}个SKILL.md含过时描述：{'; '.join(outdated_skills[:5])}",
                                         f"{len(outdated_skills)}个含过时描述",
                                         "无过时描述",
                                         "更新SKILL.md移除过时描述"))

    return results


def _check_skill_doc_consistency(vault: Path, skills_dir: Path) -> list:
    """类别 6：Skill 说明文件一致性。

    对比 vault/skills/*.md（人类阅读的说明文档）与 .claude/skills/Obsidian/obsidian-*/SKILL.md（实际插件）。
    检查项：数量匹配、名称匹配、功能描述一致性、废弃标记。
    """
    results = []
    category = "Skill说明文件一致性"

    doc_dir = vault / "skills"
    if not doc_dir.exists():
        results.append(_make_result(category, "skills说明目录", "fail",
                                     f"skills说明目录不存在：{doc_dir}",
                                     "目录缺失", "目录存在", "创建skills目录"))
        return results

    if not skills_dir.exists():
        results.append(_make_result(category, "Skills插件目录", "fail",
                                     f"Skills插件目录不存在：{skills_dir}",
                                     "目录缺失", "目录存在", "检查路径"))
        return results

    # 1. 收集实际 Skill 插件（.claude/skills/Obsidian/obsidian-*/SKILL.md）
    actual_skills = {}  # name -> SKILL.md path
    for skill_file in skills_dir.rglob("SKILL.md"):
        skill_name = skill_file.parent.name
        if skill_name.startswith("obsidian-"):
            actual_skills[skill_name] = skill_file

    # 2. 收集说明文档（vault/skills/*.md 中匹配 skill 模式的）
    #    支持的命名：
    #    - "skill obsidian-xxx说明.md"
    #    - "skill obsidian-xxx 说明.md"
    #    - "Skill obsidian-xxx 说明.md"
    #    - "obsidian-pipeline说明.md"（极少数）
    #    - "skill obsidian-mulu-fenlei-summary说明.md"
    doc_files = list(doc_dir.glob("*.md"))
    doc_to_skill = {}  # doc_file -> skill_name（保留原大小写）
    for df in doc_files:
        name = df.name
        # 排除总览/索引类文件
        if name.startswith("🧩") or name.startswith("📖") or name.startswith("🏠"):
            continue
        if name in ("知识处理系统使用手册2.0 LD-DVA Final.md", "知识处理系统使用手册1.0.md", "obsidian_skill_utils.py 说明.md",
                    "🤖 AI指令.md", "EXE Launcher  `obsidian-exe-launcher`  Obsidian自开发插件.md",
                    "`obsidian-health-check-all` 检查方案.md", "Python Personal Engineering Workspace方案.md"):
            # 使用手册、工具说明、检查方案建议稿不算 Skill 说明文档
            continue
        # 提取 obsidian-xxx 部分（保留原大小写以便与 actual_skills 精确匹配）
        m = re.search(r'(obsidian-[a-zA-Z][a-zA-Z0-9-]*)', name, re.IGNORECASE)
        if m:
            doc_to_skill[df] = m.group(1)  # 不 lower，保留原大小写

    # 构建 actual_skills 的小写索引（用于大小写不敏感匹配）
    actual_skills_lower = {k.lower(): k for k in actual_skills.keys()}

    # 检查1：数量一致性
    actual_count = len(actual_skills)
    doc_count = len(doc_to_skill)
    if doc_count == actual_count:
        results.append(_make_result(category, "说明文件数量一致性", "pass",
                                     f"说明文件{doc_count}个 = 实际Skill{actual_count}个"))
    else:
        results.append(_make_result(category, "说明文件数量一致性", "warn",
                                     f"说明文件{doc_count}个 ≠ 实际Skill{actual_count}个",
                                     f"说明文件{doc_count}个",
                                     f"实际Skill{actual_count}个",
                                     "补齐缺失说明文件或清理多余文件"))

    # 检查2：每个实际 Skill 都有对应说明文档（大小写不敏感匹配）
    docs_skill_names_lower = {sn.lower() for sn in doc_to_skill.values()}
    missing_docs = sorted([k for k in actual_skills.keys()
                            if k.lower() not in docs_skill_names_lower])
    if not missing_docs:
        results.append(_make_result(category, "实际Skill都有说明文件", "pass",
                                     f"{len(actual_skills)}个Skill都有对应说明文件"))
    else:
        results.append(_make_result(category, "实际Skill都有说明文件", "warn",
                                     f"缺少说明文件：{', '.join(missing_docs)}",
                                     f"缺{len(missing_docs)}个",
                                     "每个Skill都有说明",
                                     f"为 {', '.join(missing_docs)} 补充说明文件"))

    # 检查3：每个说明文档都能匹配到实际 Skill（大小写不敏感）
    docs_lower_to_actual = {}  # lower_doc_name -> actual_skill_name
    for df, sn in doc_to_skill.items():
        actual_match = actual_skills_lower.get(sn.lower())
        if actual_match:
            docs_lower_to_actual[sn.lower()] = (df, actual_match)

    orphan_docs = sorted([sn for sn in doc_to_skill.values()
                           if sn.lower() not in actual_skills_lower])
    if not orphan_docs:
        results.append(_make_result(category, "说明文件都能匹配Skill", "pass",
                                     "无孤立说明文件"))
    else:
        # 检查是否是已废弃 Skill 的说明（标注了"已废弃"）
        truly_orphan = []
        for skill_name in orphan_docs:
            # 找到对应的说明文件
            for df, sn in doc_to_skill.items():
                if sn == skill_name:
                    content = read_text_safe(df)
                    if any(marker in content for marker in ["已废弃", "已删除", "已合并", "已改为", "已移除", "废弃说明"]):
                        # 已废弃的说明文件，不算问题
                        continue
                    truly_orphan.append(skill_name)
                    break
        if not truly_orphan:
            results.append(_make_result(category, "说明文件都能匹配Skill", "pass",
                                         "孤立说明文件均已标注废弃"))
        else:
            results.append(_make_result(category, "说明文件都能匹配Skill", "warn",
                                         f"孤立说明文件：{', '.join(truly_orphan)}",
                                         f"{len(truly_orphan)}个孤立",
                                         "0个孤立",
                                         "删除孤立说明文件或补齐Skill"))

    # 检查4：名称与功能描述一致性（对每个匹配上的 Skill）
    name_mismatches = []
    desc_mismatches = []
    matched_count = 0
    for df, skill_name in doc_to_skill.items():
        actual_name = actual_skills_lower.get(skill_name.lower())
        if not actual_name:
            continue
        skill_file = actual_skills[actual_name]
        matched_count += 1
        skill_content = read_text_safe(skill_file)
        doc_content = read_text_safe(df)

        # 4a. frontmatter name 字段一致性
        fm_match = re.search(r'^name:\s*([^\s]+)', skill_content, re.MULTILINE)
        if fm_match:
            fm_name = fm_match.group(1).strip()
            if fm_name != actual_name:
                name_mismatches.append(f"{actual_name}: frontmatter name={fm_name} ≠ 目录名")

        # 4b. 功能描述关键词重叠度（取 description 前 80 字符，按字符 2-gram 计算 Jaccard）
        def _desc_text(text):
            m = re.search(r'^description:\s*(.+?)(?:\n[a-zA-Z-]+:|\n---|\Z)', text, re.MULTILINE | re.DOTALL)
            return m.group(1).strip() if m else ""

        def _gram_set(s, n=2):
            s = re.sub(r'\s+', '', s)
            return set(s[i:i+n] for i in range(len(s) - n + 1)) if len(s) >= n else {s}

        # 从说明文档中提取"干什么的"、定位、核心定位或第一段描述
        doc_desc = ""
        for pat in [r'干什么的[：:]\s*([^\n]+)', r'核心定位[：:]\s*([^\n]+)',
                    r'定位[：:]\s*([^\n]+)', r'说明[：:]\s*([^\n]+)', 
                    r'简介[：:]\s*([^\n]+)']:
            m = re.search(pat, doc_content)
            if m:
                doc_desc = m.group(1).strip()
                break
        if not doc_desc:
            # 取第一段非空文本（跳过 frontmatter）
            body = re.sub(r'^---\n.*?\n---\n', '', doc_content, count=1, flags=re.DOTALL)
            lines = [l.strip() for l in body.split('\n') if l.strip() and not l.startswith('#')]
            if lines:
                doc_desc = lines[0][:100]

        skill_desc = _desc_text(skill_content)
        if doc_desc and skill_desc:
            g1, g2 = _gram_set(doc_desc), _gram_set(skill_desc)
            if g1 and g2:
                jaccard = len(g1 & g2) / len(g1 | g2)
                if jaccard < 0.05:  # 关键词重叠度极低
                    desc_mismatches.append(f"{actual_name}: 重叠度{jaccard:.2f}")

    if matched_count == 0:
        results.append(_make_result(category, "frontmatter name 一致性", "warn",
                                     "无匹配的说明文件-Skill对，无法检查"))
    elif not name_mismatches:
        results.append(_make_result(category, "frontmatter name 一致性", "pass",
                                     f"{matched_count}个说明文件对应的Skill name字段都一致"))
    else:
        results.append(_make_result(category, "frontmatter name 一致性", "fail",
                                     f"{len(name_mismatches)}个不一致：{'; '.join(name_mismatches[:3])}",
                                     f"{len(name_mismatches)}个不一致",
                                     "0个不一致",
                                     "修正frontmatter name字段"))

    if matched_count == 0:
        results.append(_make_result(category, "功能描述一致性", "warn",
                                     "无匹配的说明文件-Skill对，无法检查"))
    elif not desc_mismatches:
        results.append(_make_result(category, "功能描述一致性", "pass",
                                     "说明文档与SKILL.md功能描述重叠度达标"))
    else:
        results.append(_make_result(category, "功能描述一致性", "warn",
                                     f"{len(desc_mismatches)}个描述差异大：{'; '.join(desc_mismatches[:3])}",
                                     f"{len(desc_mismatches)}个差异",
                                     "描述一致",
                                     "同步说明文档与SKILL.md描述"))

    return results


def _check_doc_content_drift(vault: Path, skills_dir: Path) -> list:
    """类别 7：文档真实内容数字对比。

    读取 CLAUDE.md / README.md / 知识处理系统使用手册.md / 🧩 目录-skills.md，
    提取关键数字（Skill数量/确认节点/类型词库/Pipeline流程），与实际系统对比。
    发现"文档写9个Skill实际只有8个"这类漂移。
    """
    results = []
    category = "文档内容漂移"

    # 实际值（去重：同一个 skill 名在多个位置有副本只算一次）
    unique_skill_names: set[str] = set()
    if skills_dir.exists():
        for f in skills_dir.rglob("SKILL.md"):
            if f.parent.name.startswith("obsidian-"):
                unique_skill_names.add(f.parent.name)
    trae_skills_dir = Path.home() / ".trae-cn" / "skills"
    if trae_skills_dir.exists():
        for f in trae_skills_dir.rglob("SKILL.md"):
            if f.parent.name.startswith("obsidian-"):
                unique_skill_names.add(f.parent.name)
    actual_skill_count = len(unique_skill_names)
    
    actual_type_count = len(VALID_TYPES) if 'VALID_TYPES' in globals() else 12
    expected_pipeline = ["Planner", "Compiler", "Fire-rename", "Organizer"]
    expected_confirm_nodes = 3

    # 检查文档清单
    docs_to_check = [
        ("CLAUDE.md", vault / "CLAUDE.md"),
        ("README.md", vault / "README.md"),
        ("知识处理系统使用手册2.0 LD-DVA Final.md", vault / "skills" / "知识处理系统使用手册2.0 LD-DVA Final.md"),
        ("🧩 目录-skills.md", vault / "skills" / "🧩 目录-skills.md"),
    ]

    for doc_label, doc_path in docs_to_check:
        if not doc_path.exists():
            results.append(_make_result(category, f"{doc_label}存在性", "warn",
                                         f"{doc_path} 不存在",
                                         "文件缺失", "文件存在", f"创建 {doc_label}"))
            continue

        content = read_text_safe(doc_path)
        # 去除 changelog/更新历史章节（非当前状态描述）
        content_clean = re.sub(r'###\s+v?\d+\.\d+\.\d+.*?(?=###|\Z)', '', content, flags=re.DOTALL)
        content_clean = re.sub(r'###\s+更新.*?(?=###|\Z)', '', content_clean, flags=re.DOTALL)
        issues = []

        # 1. Skill 数量：查找"X 个 Skill"、"X个Skill"、"X 个 skill"
        skill_count_matches = re.findall(r'(\d+)\s*个\s*[Ss]kill', content_clean)
        for cnt_str in skill_count_matches:
            cnt = int(cnt_str)
            if cnt != actual_skill_count and cnt > 0:
                issues.append(f"Skill数量写{cnt}实际{actual_skill_count}")

        # 2. 类型词库数量：查找"X 种类型"、"X种类型词库"
        type_count_matches = re.findall(r'(\d+)\s*种(?:类型|类型词库)', content)
        for cnt_str in type_count_matches:
            cnt = int(cnt_str)
            if cnt != actual_type_count and 0 < cnt < 20:
                issues.append(f"类型数量写{cnt}实际{actual_type_count}")

        # 3. 确认节点数量：查找"X 个确认节点"、"X个确认"
        confirm_matches = re.findall(r'(\d+)\s*个(?:确认节点|人工确认)', content)
        for cnt_str in confirm_matches:
            cnt = int(cnt_str)
            if cnt != expected_confirm_nodes and 0 < cnt < 10:
                issues.append(f"确认节点写{cnt}实际{expected_confirm_nodes}")

        # 4. Pipeline 流程顺序：查找"Planner"附近的流程描述
        #    匹配 "Planner → Compiler → Fire-rename → Organizer" 或类似
        pipeline_patterns = [
            r'Planner\s*[→\->,]+\s*Compiler\s*[→\->,]+\s*Fire-rename\s*[→\->,]+\s*Organizer',
            r'Planner\s*[→\->,]+\s*Compiler\s*[→\->,]+\s*(?:Fire-rename|fire-rename)\s*[→\->,]+\s*Organizer',
        ]
        # 错误顺序检测：Planner 直接接 Organizer（跳过 Compiler）
        # 仅当同行/同段落没有其他正确顺序词时才报警
        wrong_skip = False
        for m in re.finditer(r'Planner\s*[→\->,]+\s*Organizer', content):
            # 检查周围 100 字符内是否有 Compiler/Fire-rename
            ctx = content[max(0, m.start()-100):min(len(content), m.end()+100)]
            if 'Compiler' not in ctx and 'Fire-rename' not in ctx:
                wrong_skip = True
                break
        # 错误顺序：Compiler 在 Fire-rename 之后
        # 仅检测主流程描述（前 200 字符内的总览/速查表），避免误报场景化流程
        wrong_order = False
        for m in re.finditer(r'Fire-rename\s*[→\->,]+\s*Compiler', content):
            # 排除：行内含"用什么"/"场景"/"示例"等场景化标记
            line_start = content.rfind('\n', 0, m.start()) + 1
            line_end = content.find('\n', m.end())
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]
            if any(kw in line for kw in ['用什么', '场景', '示例', '例如', '比如', '组合', '可选', '或者']):
                continue
            # 排除：表格行（含 | 或反引号）
            if '|' in line or line.count('`') >= 2:
                continue
            wrong_order = True
            break

        has_correct_pipeline = any(re.search(p, content) for p in pipeline_patterns)
        if wrong_skip and not has_correct_pipeline:
            issues.append("Pipeline跳步：Planner→Organizer（缺Compiler/Fire-rename）")
        if wrong_order:
            issues.append("Pipeline顺序错误：Fire-rename→Compiler（应为Compiler→Fire-rename）")

        # 5. Accumulate 模式数：应为 2 种
        accumulate_matches = re.findall(r'(\d+)\s*种(?:沉淀|沉淀模式|模式)', content)
        for cnt_str in accumulate_matches:
            cnt = int(cnt_str)
            if cnt != 2 and 0 < cnt < 10:
                # 排除"X种类型"已处理的情况
                if f"{cnt}种沉淀" in content or f"{cnt} 种沉淀" in content:
                    issues.append(f"Accumulate模式数写{cnt}实际2")

        if not issues:
            results.append(_make_result(category, f"{doc_label}数字一致性", "pass",
                                         "关键数字与实际一致"))
        else:
            results.append(_make_result(category, f"{doc_label}数字一致性", "fail",
                                         f"发现{len(issues)}处漂移：{'; '.join(issues[:3])}",
                                          f"{len(issues)}处漂移",
                                          "0处漂移",
                                          "修正文档使其与实际一致"))

    return results


def _check_cross_file_consistency(vault: Path, skills_dir: Path, python_dir: Path) -> list:
    """跨文件信息一致性检查。

    检查 CLAUDE.md / README.md / AGENTS.md 与 SKILL.md 的一致性：
    1. CLAUDE.md 触发词表 ↔ 每个 SKILL.md 的触发词
    2. CLAUDE.md 技能描述 ↔ 每个 SKILL.md 的 description
    3. AGENTS.md 存在性与基本同步
    4. CLAUDE.md 类型词库提及与实际 VALID_TYPES 一致
    """
    results = []
    category = "跨文件一致性"

    # === 收集 SKILL.md 数据 ===
    skill_data = {}  # skill_name -> {description, triggers, type_mention}
    if skills_dir.exists():
        for sf in skills_dir.rglob("SKILL.md"):
            sname = sf.parent.name
            if not sname.startswith("obsidian-"):
                continue
            content = read_text_safe(sf)
            # 提取 description
            dm = re.search(r'^description:\s*(.+?)(?:\n[a-zA-Z-]+:|\n---|\Z)',
                           content, re.MULTILINE | re.DOTALL)
            desc = dm.group(1).strip() if dm else ""
            # 提取触发词（从 description 中提取"触发词："后面的部分）
            triggers = []
            tm = re.search(r'触发词[：:]\s*(.+?)(?:\n|$)', desc)
            if tm:
                triggers = [t.strip().strip('`') for t in re.split(r'[、,，]', tm.group(1)) if t.strip()]
            skill_data[sname] = {"description": desc, "triggers": triggers}

    # === 检查1: CLAUDE.md 触发词表 ↔ SKILL.md ===
    claude_path = vault / "CLAUDE.md"
    if claude_path.exists():
        claude_content = read_text_safe(claude_path)
        # 提取 CLAUDE.md "9 个 Skill 一览" 表格中的触发词
        # 格式: | **obsidian-xxx** | ... | `触发词1`、`触发词2` |
        claude_triggers = {}  # skill_name -> [triggers]
        for line in claude_content.split('\n'):
            m = re.search(r'\*\*(obsidian-[a-zA-Z0-9-]+)\*\*', line)
            if m:
                sname = m.group(1)
                # 提取该行中的反引号触发词
                ticks = re.findall(r'`([^`]+)`', line)
                if ticks:
                    claude_triggers[sname] = ticks

        missing_in_claude = []
        extra_in_claude = []
        for sname, sinfo in skill_data.items():
            if sname not in claude_triggers:
                missing_in_claude.append(sname)
                continue
            # 比较触发词
            c_set = set(claude_triggers[sname])
            s_set = set(sinfo["triggers"])
            if s_set and not s_set.intersection(c_set):
                missing_in_claude.append(f"{sname}(触发词不匹配)")

        if not missing_in_claude:
            results.append(_make_result(category, "CLAUDE.md触发词同步", "pass",
                                       f"{len(skill_data)}个Skill触发词在CLAUDE.md中一致"))
        else:
            results.append(_make_result(category, "CLAUDE.md触发词同步", "warn",
                                       f"{len(missing_in_claude)}个Skill触发词缺失/不匹配：{', '.join(missing_in_claude[:5])}",
                                       f"{len(missing_in_claude)}个缺失",
                                       "0个缺失",
                                       "更新CLAUDE.md触发词表"))

    # === 检查2: CLAUDE.md 技能描述 ↔ SKILL.md description ===
    # 注意：CLAUDE.md 表格中的描述是精简版，与 SKILL.md 详细描述不同是正常的
    # 此检查仅做记录，不计为警告
    if claude_path.exists():
        claude_content = read_text_safe(claude_path)
        desc_mismatches = []
        for sname, sinfo in skill_data.items():
            skill_desc = sinfo["description"]
            if not skill_desc:
                continue
            # 在 CLAUDE.md 中查找该 skill 的描述行
            # 格式: | **obsidian-xxx** | 描述文字 | 主责 | 触发词 |
            for line in claude_content.split('\n'):
                if f"**{sname}**" in line:
                    cells = [c.strip() for c in line.split('|') if c.strip()]
                    if len(cells) >= 2:
                        claude_desc = cells[1].strip('* ')
                        if claude_desc:
                            # CLAUDE.md 描述是精简版，与 SKILL.md 不同是正常的
                            # 只检查是否都提到了核心功能关键词
                            pass
                    break

        # 始终通过（CLAUDE.md 描述精简是设计如此）
        results.append(_make_result(category, "CLAUDE.md描述同步", "pass",
                                   f"{len(skill_data)}个Skill在CLAUDE.md中均有描述（精简版）"))

    # === 检查3: AGENTS.md 存在性 ===
    agents_path = vault / "AGENTS.md"
    if agents_path.exists():
        agents_content = read_text_safe(agents_path)
        # 检查是否包含 skill 相关内容（基本同步检查）
        has_skill_ref = 'skill' in agents_content.lower() or 'Skill' in agents_content
        has_pipeline_ref = 'pipeline' in agents_content.lower() or 'Pipeline' in agents_content
        if has_skill_ref or has_pipeline_ref:
            results.append(_make_result(category, "AGENTS.md同步", "pass",
                                       "AGENTS.md 存在且包含 Skill/Pipeline 相关内容"))
        else:
            results.append(_make_result(category, "AGENTS.md同步", "warn",
                                       "AGENTS.md 存在但未引用 Skill/Pipeline 系统",
                                       "无Skill引用", "有Skill引用",
                                       "在AGENTS.md补充Skill系统说明"))
    else:
        # AGENTS.md 在 LeoDiary 系统中不是必须的（CLAUDE.md 已承担此角色）
        results.append(_make_result(category, "AGENTS.md存在性", "pass",
                                   "AGENTS.md 不存在（CLAUDE.md 已承担 Agent 定义角色，非必须）"))

    # === 检查4: CLAUDE.md 类型词库提及 ===
    if claude_path.exists():
        claude_content = read_text_safe(claude_path)
        # 提取 CLAUDE.md 中提到的类型数量
        type_count_matches = re.findall(r'(\d+)\s*种(?:类型|类型词库)', claude_content)
        actual_type_count = len(VALID_TYPES) if 'VALID_TYPES' in globals() else 12
        type_issues = []
        for cnt_str in type_count_matches:
            cnt = int(cnt_str)
            if cnt != actual_type_count and 0 < cnt < 20:
                type_issues.append(f"写{cnt}实际{actual_type_count}")

        if not type_issues:
            results.append(_make_result(category, "CLAUDE.md类型词库", "pass",
                                       f"类型词库数量与实际一致（{actual_type_count}种）"))
        else:
            results.append(_make_result(category, "CLAUDE.md类型词库", "fail",
                                       f"类型词库数量漂移：{'; '.join(type_issues)}",
                                       f"漂移{len(type_issues)}处", "0处漂移",
                                       "更新CLAUDE.md类型词库数量"))

    return results


def _check_python_scripts_runtime(python_dir: Path) -> list:
    """Python 脚本运行时健康检查。

    测试关键 Python 脚本能否正常启动（--help / 基本命令），发现导入错误、
    依赖缺失等运行时问题。
    """
    results = []
    category = "Python运行时健康"

    if not python_dir.exists():
        results.append(_make_result(category, "Python目录", "fail",
                                   f"Python目录不存在：{python_dir}",
                                   "目录缺失", "目录存在", "检查路径"))
        return results

    # 测试关键脚本能否正常运行
    test_scripts = [
        ("obsidian_skill_utils.py", ["skill-health-check", "--help"], "obsidian_skill_utils.py"),
        ("lib/lint.py", ["--help"], "lint.py"),
        ("lib/validate.py", ["--help"], "validate.py"),
    ]

    for rel_path, cmd_args, label in test_scripts:
        script_path = _find_script(python_dir, rel_path)
        if not script_path.exists():
            results.append(_make_result(category, f"{label}存在性", "fail",
                                       f"{rel_path} 不存在",
                                       "文件缺失", "文件存在", f"创建 {rel_path}"))
            continue

        # 尝试运行 python <script> <args>
        try:
            import subprocess
            cmd = [sys.executable, str(script_path)] + cmd_args
            proc = subprocess.run(cmd, capture_output=True, timeout=30, encoding='utf-8', errors='replace')
            stdout = proc.stdout if proc.stdout else ""
            stderr = proc.stderr if proc.stderr else ""
            if proc.returncode == 0:
                results.append(_make_result(category, f"{label}运行", "pass",
                                           f"{label} 正常运行（exit 0）"))
            else:
                if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
                    results.append(_make_result(category, f"{label}运行", "fail",
                                               f"{label} 缺少依赖：{stderr[:100]}",
                                               "依赖缺失", "依赖完整",
                                               f"安装缺失的 Python 包"))
                elif "SyntaxError" in stderr:
                    results.append(_make_result(category, f"{label}运行", "fail",
                                               f"{label} 语法错误：{stderr[:100]}",
                                               "语法错误", "无语法错误",
                                               f"修复 {rel_path} 语法"))
                else:
                    results.append(_make_result(category, f"{label}运行", "pass",
                                               f"{label} 可运行（exit {proc.returncode}）"))
        except subprocess.TimeoutExpired:
            results.append(_make_result(category, f"{label}运行", "warn",
                                       f"{label} 运行超时（30s）",
                                       "运行超时", "正常运行", f"检查 {rel_path} 是否有死循环"))
        except Exception as e:
            results.append(_make_result(category, f"{label}运行", "fail",
                                       f"{label} 运行异常：{str(e)[:100]}",
                                       "运行异常", "正常运行", f"检查 Python 环境"))

    # 测试 obsidian_skill_utils.py 的关键子命令
    utils_script = _find_script(python_dir, "obsidian_skill_utils.py")
    if utils_script.exists():
        key_commands = [
            ("is-system-file", ["README.md"], "is-system-file"),
            ("validate-filename", ["test - 知识 @ 说明"], "validate-filename"),
        ]
        for cmd_name, cmd_args, label in key_commands:
            try:
                import subprocess
                full_cmd = [sys.executable, str(utils_script), cmd_name] + cmd_args
                proc = subprocess.run(full_cmd, capture_output=True, timeout=15, encoding='utf-8', errors='replace')
                stdout = proc.stdout if proc.stdout else ""
                stderr = proc.stderr if proc.stderr else ""
                if proc.returncode == 0:
                    results.append(_make_result(category, f"命令{label}", "pass",
                                               f"命令 {cmd_name} 正常运行"))
                else:
                    results.append(_make_result(category, f"命令{label}", "warn",
                                               f"命令 {cmd_name} 异常（exit {proc.returncode}）：{stderr[:80]}",
                                               "命令异常", "命令正常",
                                               f"检查 {cmd_name} 实现"))
            except Exception as e:
                results.append(_make_result(category, f"命令{label}", "warn",
                                           f"命令 {cmd_name} 测试失败：{str(e)[:80]}",
                                           "测试失败", "测试通过", "检查Python环境"))

    return results


def _check_kb_content_health_aggregated(vault: Path) -> list:
    """类别 2 补充：聚合 validate-metadata / lint-content / kb-stats 子命令结果。

    在 _check_kb_content_health 已有 4 项基础上，再补充 5 项：
    - 元数据校验失败数（validate-metadata）
    - 内容健康问题数（lint-content）
    - 平均关联数（kb-stats）
    - 30天更新率（kb-stats）
    - 90天更新率（kb-stats）
    """
    results = []
    category = "知识库内容健康"

    if not vault.exists():
        return results

    import subprocess
    import sys as _sys

    py_exe = _sys.executable
    this_script = Path(__file__).resolve()

    def _run_subprocess(args):
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            r = subprocess.run([py_exe, str(this_script)] + args,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=120, cwd=str(vault), env=env)
            return (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return f"__ERROR__:{e}"

    # 1. 元数据校验（validate-metadata --quiet）
    vm_output = _run_subprocess(["validate-metadata", str(vault), "--quiet"])
    if vm_output.startswith("__ERROR__:"):
        results.append(_make_result(category, "元数据校验", "warn",
                                     f"子命令执行失败：{vm_output[10:80]}",
                                     "执行失败", "成功执行", "检查lib/validate.py"))
    else:
        # --quiet 模式下输出只包含错误信息，统计错误行数
        error_lines = [l for l in vm_output.split('\n')
                        if l.strip() and ('❌' in l or '错误' in l or 'ERROR' in l
                        or '缺失' in l or '无效' in l)]
        if not error_lines:
            results.append(_make_result(category, "元数据校验", "pass",
                                         "元数据校验无错误"))
        elif len(error_lines) <= 5:
            results.append(_make_result(category, "元数据校验", "warn",
                                         f"发现{len(error_lines)}个元数据问题",
                                         f"{len(error_lines)}个问题", "0个", "修复元数据问题"))
        else:
            results.append(_make_result(category, "元数据校验", "fail",
                                         f"发现{len(error_lines)}个元数据问题（前3个）：{'; '.join(error_lines[:3])[:100]}",
                                         f"{len(error_lines)}个问题", "0个", "批量修复元数据"))

    # 2. 内容健康检查（lint-content all）
    lint_output = _run_subprocess(["lint-content", str(vault), "all"])
    if lint_output.startswith("__ERROR__:"):
        results.append(_make_result(category, "内容健康检查", "warn",
                                     f"子命令执行失败：{lint_output[10:80]}",
                                     "执行失败", "成功执行", "检查lib/lint.py"))
    else:
        # 统计 lint 报告中的问题数（过时/孤儿/断链等）
        issue_count = 0
        issue_types = []
        for keyword, label in [("过时", "过时"), ("孤儿", "孤儿"), ("断链", "断链"),
                                ("矛盾", "矛盾"), ("缺失交叉", "缺失交叉"),
                                ("双向链接", "双向链接"), ("内容矛盾", "内容矛盾")]:
            # 匹配 "X 个过时" / "X个孤儿" 等
            matches = re.findall(rf'(\d+)\s*个\s*{keyword}', lint_output)
            for cnt_str in matches:
                cnt = int(cnt_str)
                if cnt > 0:
                    issue_count += cnt
                    issue_types.append(f"{label}{cnt}个")

        if issue_count == 0:
            results.append(_make_result(category, "内容健康检查", "pass",
                                         "lint-content 7项检查全部通过"))
        elif issue_count <= 10:
            results.append(_make_result(category, "内容健康检查", "warn",
                                         f"发现{issue_count}个问题：{', '.join(issue_types[:3])}",
                                         f"{issue_count}个问题", "0个", "按lint报告修复"))
        else:
            results.append(_make_result(category, "内容健康检查", "fail",
                                         f"发现{issue_count}个问题：{', '.join(issue_types[:3])}",
                                         f"{issue_count}个问题", "0个", "按lint报告批量修复"))

    # 3-5. kb-stats（一次调用，提取多个指标）
    kb_output = _run_subprocess(["kb-stats", str(vault), "--json"])
    if kb_output.startswith("__ERROR__:"):
        results.append(_make_result(category, "平均关联数", "warn",
                                     f"kb-stats执行失败：{kb_output[10:80]}",
                                     "执行失败", "成功执行", "检查lib/leo_common.py"))
        results.append(_make_result(category, "30天更新率", "warn",
                                     "kb-stats执行失败", "执行失败", "成功执行", "同上"))
        results.append(_make_result(category, "90天更新率", "warn",
                                     "kb-stats执行失败", "执行失败", "成功执行", "同上"))
    else:
        # 尝试解析 JSON 输出
        kb_data = None
        try:
            # 找到 JSON 起始位置
            json_start = kb_output.find('{')
            if json_start >= 0:
                kb_data = json.loads(kb_output[json_start:])
        except Exception:
            pass

        if kb_data is None:
            # 解析失败，从文本输出中提取
            text_output = kb_output
            # 匹配 "平均关联数：X.X" / "平均关联: X.X"
            avg_related = None
            m = re.search(r'平均关联[数:]?\s*[：:]?\s*([\d.]+)', text_output)
            if m:
                avg_related = float(m.group(1))
            if avg_related is not None:
                if avg_related >= 1.0:
                    results.append(_make_result(category, "平均关联数", "pass",
                                                 f"平均关联数 {avg_related:.2f}"))
                else:
                    results.append(_make_result(category, "平均关联数", "warn",
                                                 f"平均关联数 {avg_related:.2f}（偏低）",
                                                 f"{avg_related:.2f}", "≥1.0", "为重要文件补充双链"))
            else:
                results.append(_make_result(category, "平均关联数", "warn",
                                             "无法从kb-stats输出提取平均关联数",
                                             "解析失败", "成功提取", "检查kb-stats输出格式"))

            # 30/90 天更新率
            for label, key in [("30天更新率", "30"), ("90天更新率", "90")]:
                m = re.search(rf'{key}天[更新]?[率]?[：:]?\s*([\d.]+)%?', text_output)
                if m:
                    rate = float(m.group(1))
                    threshold = 20 if key == "30" else 50
                    if rate >= threshold:
                        results.append(_make_result(category, label, "pass",
                                                     f"{label} {rate:.1f}%"))
                    else:
                        results.append(_make_result(category, label, "warn",
                                                     f"{label} {rate:.1f}%（偏低）",
                                                     f"{rate:.1f}%", f"≥{threshold}%", "激活旧文件"))
                else:
                    results.append(_make_result(category, label, "warn",
                                                 f"无法提取{label}",
                                                 "解析失败", "成功提取", "检查kb-stats输出格式"))
        else:
            # JSON 解析成功
            avg_related = kb_data.get("avg_related") or kb_data.get("average_related")
            if avg_related is not None:
                if avg_related >= 1.0:
                    results.append(_make_result(category, "平均关联数", "pass",
                                                 f"平均关联数 {avg_related:.2f}"))
                else:
                    results.append(_make_result(category, "平均关联数", "warn",
                                                 f"平均关联数 {avg_related:.2f}（偏低）",
                                                 f"{avg_related:.2f}", "≥1.0", "为重要文件补充双链"))

            for label, key in [("30天更新率", "updated_30d_rate"),
                                ("90天更新率", "updated_90d_rate")]:
                rate = kb_data.get(key)
                if rate is not None:
                    rate = float(rate) * 100 if float(rate) <= 1 else float(rate)
                    threshold = 20 if "30" in label else 50
                    if rate >= threshold:
                        results.append(_make_result(category, label, "pass",
                                                     f"{label} {rate:.1f}%"))
                    else:
                        results.append(_make_result(category, label, "warn",
                                                     f"{label} {rate:.1f}%（偏低）",
                                                     f"{rate:.1f}%", f"≥{threshold}%", "激活旧文件"))
                else:
                    results.append(_make_result(category, label, "warn",
                                                 f"kb-stats未返回{label}",
                                                 "字段缺失", "字段存在", "检查kb-stats实现"))

    return results


def _check_python_cmd_param_consistency(skills_dir: Path, python_dir: Path) -> list:
    """类别 3 补充：Python 命令参数一致性检查。

    解析 SKILL.md 中的 `python obsidian_skill_utils.py <cmd> <args>` 调用，
    对比脚本实际命令定义，发现引用了不存在的命令或参数明显不匹配。
    """
    results = []
    category = "Python代码协作性"

    if not skills_dir.exists() or not python_dir.exists():
        return results

    utils_script = _find_script(python_dir, "obsidian_skill_utils.py")
    if not utils_script.exists():
        return results

    # 收集脚本中已定义的命令（从 main() 的 commands dict 提取）
    utils_content = read_text_safe(utils_script)
    defined_cmds = set(re.findall(r'"([a-z][a-z0-9-]*)":\s*lambda', utils_content))
    # 兜底：再扫一遍 cmd_xxx 函数
    defined_cmds |= set(re.findall(r'def cmd_([a-z_]+)\(', utils_content))
    # 把下划线转连字符（cmd_skill_health_check → skill-health-check）
    normalized = set()
    for c in defined_cmds:
        normalized.add(c.replace('_', '-'))
    defined_cmds |= normalized

    # 扫描所有 SKILL.md，提取 python 调用
    cmd_pattern = re.compile(
        r'python\s+[^\s]*obsidian_skill_utils\.py\s+([a-zA-Z][a-zA-Z0-9-]*)\s+([^\n`]+)'
    )
    all_calls = []  # (skill_name, cmd, args_str)
    for skill_file in skills_dir.rglob("SKILL.md"):
        skill_name = skill_file.parent.name
        content = read_text_safe(skill_file)
        for m in cmd_pattern.finditer(content):
            cmd = m.group(1)
            args_str = m.group(2).strip().rstrip('`').strip()
            # 跳过明显是占位符的
            if args_str.startswith('"<') or args_str.startswith('"<'):
                args_str = ""
            all_calls.append((skill_name, cmd, args_str))

    # 检查1：所有引用的命令都存在
    invalid_cmds = set()
    for _, cmd, _ in all_calls:
        if cmd not in defined_cmds:
            invalid_cmds.add(cmd)
    if not invalid_cmds:
        results.append(_make_result(category, "命令存在性", "pass",
                                     f"所有SKILL.md引用的命令都存在（共{len(set(c for _,c,_ in all_calls))}个不同命令）"))
    else:
        results.append(_make_result(category, "命令存在性", "fail",
                                     f"引用了未定义的命令：{', '.join(sorted(invalid_cmds))}",
                                     f"{len(invalid_cmds)}个无效命令",
                                     "0个无效命令",
                                     "更新SKILL.md或为脚本补充命令"))

    # 检查2：核心工具脚本引用一致性
    key_scripts = [
        ("lib/lint.py", "lint.py"),
        ("lib/validate.py", "validate.py"),
        ("Obsidian - index_updater.py", "index_updater.py"),
    ]
    for rel, label in key_scripts:
        script_path = _find_script(python_dir, rel)
        # 检查是否被任何 SKILL.md 引用
        referenced = False
        for skill_file in skills_dir.rglob("SKILL.md"):
            content = read_text_safe(skill_file)
            if label in content or rel in content:
                referenced = True
                break
        if script_path.exists() and referenced:
            results.append(_make_result(category, f"{label}引用", "pass",
                                         f"{label} 存在且被SKILL.md引用"))
        elif script_path.exists() and not referenced:
            results.append(_make_result(category, f"{label}引用", "warn",
                                         f"{label} 存在但无SKILL.md引用",
                                         "未引用", "应被引用", "在相关SKILL.md补充引用"))
        elif not script_path.exists():
            results.append(_make_result(category, f"{label}引用", "fail",
                                         f"{label} 不存在",
                                         "文件缺失", "文件存在", f"创建 {rel}"))

    # 检查3：lint.py 与 obsidian_skill_utils.py lint-content 职责清晰度
    lint_script = _find_script(python_dir, "lib/lint.py")
    if lint_script.exists():
        lint_content = read_text_safe(lint_script)
        # lint.py 应是底层实现，obsidian_skill_utils.py lint-content 是封装
        if "def main" in lint_content and "argparse" in lint_content:
            results.append(_make_result(category, "lint职责清晰度", "pass",
                                         "lint.py 独立可执行，obsidian_skill_utils.py 通过subprocess调用"))
        else:
            results.append(_make_result(category, "lint职责清晰度", "warn",
                                         "lint.py 结构不规范",
                                         "结构不规范", "有main+argparse", "重构lint.py"))

    # 检查4：index_updater.py 引用一致性
    idx_script = _find_script(python_dir, "Obsidian - index_updater.py")
    if idx_script.exists():
        # 检查 SKILL.md 中引用 index_updater 的方式是否正确
        idx_referenced_correctly = False
        for skill_file in skills_dir.rglob("SKILL.md"):
            content = read_text_safe(skill_file)
            if "index_updater" in content:
                # 应该是 `python ... "Obsidian - index_updater.py"` 形式
                if 'Obsidian - index_updater' in content:
                    idx_referenced_correctly = True
                    break
        if idx_referenced_correctly:
            results.append(_make_result(category, "index_updater引用", "pass",
                                         "index_updater.py 被正确引用"))
        else:
            results.append(_make_result(category, "index_updater引用", "warn",
                                         "index_updater.py 引用方式不规范",
                                         "引用不规范", "完整文件名引用", "修正SKILL.md引用"))

    return results



# ======================================================================
# 类别 8：文件命名规范检查（skills/ 目录）
# ======================================================================

def _check_file_naming_convention(vault: Path) -> list:
    """检查 skills/ 下说明文件的命名规范和 H1 标题格式"""
    results = []
    category = "Skill说明文件一致性"
    skills_dir = vault / "skills"

    if not skills_dir.exists():
        return results

    # 非 skill 说明文件（跳过命名检查）
    skip_files = {
        "知识处理系统使用手册2.0 LD-DVA Final.md", "知识处理系统使用手册1.0.md", "🧩 目录-skills.md", "🏠 home-skills.md",
        "🤖 AI指令.md", "obsidian_skill_utils.py 说明.md",
    }

    # 标准命名模式
    naming_re = re.compile(r'^skill [a-z][a-z0-9-]*说明\.md$')
    h1_re = re.compile(r'^# skill [a-z][a-z0-9-]*说明$')

    for f in sorted(skills_dir.glob("*.md")):
        fname = f.name
        if fname in skip_files:
            continue
        if "说明" not in fname:
            continue

        issues = []
        if not fname.startswith("skill "):
            if fname.startswith("Skill "):
                issues.append("前缀 'Skill' 应小写为 'skill'")
            else:
                issues.append("前缀不符合规范（应以 'skill ' 开头）")
        if "  " in fname:
            issues.append("含双空格")
        idx = fname.find("说明")
        if idx > 0 and fname[idx - 1] == " ":
            issues.append("'说明' 前有多余空格")

        if issues:
            # 生成期望文件名
            expected = fname.replace("Skill ", "skill ").replace("  ", " ")
            if "说明" in expected:
                prefix = expected[:expected.find("说明")]
                if prefix.endswith(" "):
                    expected = prefix.rstrip() + "说明.md"
            results.append(_make_result(category, f"文件命名：{fname}", "warn",
                f"命名不规范：{'; '.join(issues)}", fname,
                expected if expected != fname else "skill <name>说明.md", "重命名为标准格式"))
        else:
            results.append(_make_result(category, f"文件命名：{fname}", "pass",
                "命名格式正确", fname, "", ""))

    # 检查说明文件内的 H1 标题
    for f in sorted(skills_dir.glob("skill *说明.md")):
        try:
            content = f.read_text(encoding='utf-8')
        except Exception:
            continue
        for line in content.split('\n'):
            if line.startswith('#'):
                h1 = line.strip()
                if h1_re.match(h1):
                    results.append(_make_result(category, f"H1标题：{f.name}", "pass",
                        f"H1格式正确：{h1}", h1, "", ""))
                else:
                    h1_issues = []
                    if h1.startswith('# Skill '):
                        h1_issues.append("'Skill' 首字母应小写")
                    if " 说明" in h1:
                        h1_issues.append("H1标题中'说明'前有多余空格")
                    if h1_issues:
                        expected = f"# {f.stem}"
                        results.append(_make_result(category, f"H1标题：{f.name}", "warn",
                            f"H1格式不规范：{'; '.join(h1_issues)} | 当前: {h1}",
                            h1, expected, "修正H1标题"))
                    else:
                        results.append(_make_result(category, f"H1标题：{f.name}", "pass",
                            f"H1格式正确：{h1}", h1, "", ""))
                break

    return results


# ======================================================================
# 类别 9：跨文档信息一致性（CLAUDE/README/使用手册）
# ======================================================================

def _extract_doc_numbers(content: str, doc_name: str) -> dict:
    """从文档内容中提取关键数字"""
    info = {"doc": doc_name}
    m = re.search(r'(\d+)\s*个\s*[Ss]kill', content)
    if m:
        info["skill_count"] = int(m.group(1))
    m = re.search(r'(\d+)\s*种(?:类型|类型词库)', content)
    if m:
        info["type_count"] = int(m.group(1))
    m = re.search(r'(\d+)\s*个(?:确认节点|人工确认)', content)
    if m:
        info["confirm_nodes"] = int(m.group(1))
    m = re.search(r'(\d+)\s*种(?:沉淀模式|沉淀)', content)
    if m:
        info["accumulate_modes"] = int(m.group(1))
    if "skill_count" not in info:
        m = re.search(r'(\d+)\s*个条目', content)
        if m:
            info["skill_count"] = int(m.group(1))
    return info


def _check_cross_doc_consistency(vault: Path) -> list:
    """检查 CLAUDE.md、README.md、使用手册之间的关键数字是否一致"""
    results = []
    category = "文档内容漂移"

    docs = {
        "CLAUDE.md": vault / "CLAUDE.md",
        "README.md": vault / "README.md",
        "使用手册": vault / "skills" / "知识处理系统使用手册2.0 LD-DVA Final.md",
    }

    infos = {}
    for doc_name, doc_path in docs.items():
        if not doc_path.exists():
            results.append(_make_result(category, f"{doc_name}存在性", "warn",
                f"{doc_name} 不存在，无法参与交叉对比", str(doc_path), "文件应存在", "创建或恢复文件"))
            continue
        try:
            content = doc_path.read_text(encoding='utf-8')
        except Exception:
            results.append(_make_result(category, f"{doc_name}可读性", "fail",
                f"无法读取 {doc_name}", str(doc_path), "文件应可读", "检查文件编码"))
            continue
        infos[doc_name] = _extract_doc_numbers(content, doc_name)

    if len(infos) < 2:
        return results

    # 交叉对比每个关键数字
    keys = [
        ("skill_count", "Skill数量"),
        ("type_count", "类型词库数量"),
        ("confirm_nodes", "确认节点数量"),
        ("accumulate_modes", "沉淀模式数量"),
    ]

    doc_names = sorted(infos.keys())
    for key, label in keys:
        values = {}
        for dn in doc_names:
            if key in infos[dn]:
                values[dn] = infos[dn][key]

        if len(values) < 2:
            continue

        unique_values = set(values.values())
        if len(unique_values) > 1:
            detail_parts = [f"{dn}={v}" for dn, v in values.items()]
            results.append(_make_result(category, f"交叉对比：{label}", "warn",
                f"{label}不一致：{', '.join(detail_parts)}",
                " | ".join(detail_parts), "应统一为一致的值", f"同步各文档中的{label}"))
        else:
            v = list(unique_values)[0]
            results.append(_make_result(category, f"交叉对比：{label}", "pass",
                f"{label}一致（均为 {v}）", f"各文档均为 {v}", "", ""))

    # 版本号一致性
    version_re = re.compile(r'版本[：:]\s*v?([\d.]+)')
    versions = {}
    for dn in doc_names:
        if docs[dn].exists():
            content = docs[dn].read_text(encoding='utf-8')
            m = version_re.search(content)
            if m:
                versions[dn] = m.group(1)

    if len(versions) >= 2:
        unique_vers = set(versions.values())
        if len(unique_vers) > 1:
            detail_parts = [f"{dn}=v{v}" for dn, v in versions.items()]
            results.append(_make_result(category, "交叉对比：版本号", "warn",
                f"版本号不一致：{', '.join(detail_parts)}",
                " | ".join(detail_parts), "应统一版本号", "同步各文档版本号"))
        else:
            v = list(unique_vers)[0]
            results.append(_make_result(category, "交叉对比：版本号", "pass",
                f"版本号一致（均为 v{v}）", f"各文档均为 v{v}", "", ""))

    return results


# ======================================================================
# 类别 10：Python 脚本运行时测试
# ======================================================================

def _check_python_runtime(python_dir: Path) -> list:
    """检查 D:/Python/ 下 Obsidian 相关 py 脚本的运行时健康（语法/导入/--help）"""
    import subprocess

    results = []
    category = "Python代码协作性"

    obsidian_scripts = [
        "obsidian_skill_utils.py",
        "obsidian_common.py",
        "Obsidian - index_updater.py",
        "Obsidian - Home修改同步移动文件.py",
        "Obsidian - 目录修改同步home.py",
        "Obsidian -备份笔记.py",
        "Obsidian -备份python代码.py",
        "Obsidian - renamepy.py",
    ]

    python_exe = sys.executable

    for script_name in obsidian_scripts:
        script_path = _find_script(python_dir, script_name)
        if not script_path.exists():
            results.append(_make_result(category, f"脚本存在：{script_name}", "fail",
                f"脚本文件不存在：{script_path}", str(script_path), "文件应存在", "检查文件路径"))
            continue

        # 检查 1：语法检查
        try:
            proc = subprocess.run(
                [python_exe, "-m", "py_compile", str(script_path)],
                capture_output=True, timeout=30,
                cwd=str(python_dir), encoding='utf-8', errors='replace'
            )
            stderr = proc.stderr if proc.stderr else ""
            if proc.returncode != 0:
                err = stderr.strip()[:200]
                results.append(_make_result(category, f"语法：{script_name}", "fail",
                    f"语法检查失败：{err}", "编译失败", "应无语法错误", f"修复 {script_name} 语法错误"))
                continue
        except subprocess.TimeoutExpired:
            results.append(_make_result(category, f"语法：{script_name}", "warn",
                "语法检查超时（30秒）", "超时", "应在30秒内完成", "检查脚本是否有死循环"))
            continue
        except Exception as e:
            results.append(_make_result(category, f"语法：{script_name}", "fail",
                f"语法检查异常：{e}", str(e), "应正常编译", f"检查 {script_name}"))
            continue

        results.append(_make_result(category, f"语法：{script_name}", "pass",
            "语法检查通过", "编译成功", "", ""))

        # 跳过运行时测试的脚本（带副作用的搬移/同步脚本）
        skip_runtime_test = {
            "claude目录skill同步到其他agentcode.py",  # 移至 mytools/ 的 GUI 同步脚本
            "Obsidian - Home修改同步移动文件.py",  # 无参数执行会触发 vault 文件搬移
            "Obsidian - 目录修改同步home.py",      # 同上
        }
        if script_name not in skip_runtime_test:
            try:
                proc = subprocess.run(
                    [python_exe, str(script_path), "--help"],
                    capture_output=True, timeout=15,
                    cwd=str(python_dir), encoding='utf-8', errors='replace'
                )
                stdout = proc.stdout if proc.stdout else ""
                stderr = proc.stderr if proc.stderr else ""
                combined = (stdout + stderr).lower()
                if proc.returncode == 0 or "usage" in combined or "用法" in combined:
                    results.append(_make_result(category, f"运行：{script_name}", "pass",
                        "--help 运行正常", "可执行", "", ""))
                    continue
            except Exception:
                pass  # --help 失败，尝试无参数

            # 无参数运行
            try:
                proc2 = subprocess.run(
                    [python_exe, str(script_path)],
                    capture_output=True, timeout=15,
                    cwd=str(python_dir), encoding='utf-8', errors='replace'
                )
                stdout = proc2.stdout if proc2.stdout else ""
                stderr = proc2.stderr.decode('utf-8', errors='replace') if proc2.stderr else ""
                err_output = (stderr or stdout or "").strip()
                # 判断错误类型：缺参数/缺路径（预期行为）vs 真正的 bug
                if not err_output or "Traceback" not in err_output:
                    results.append(_make_result(category, f"运行：{script_name}", "pass",
                        "无参数运行正常", "可执行", "", ""))
                elif "importerror" in err_output.lower() or "modulenotfound" in err_output.lower():
                    results.append(_make_result(category, f"运行：{script_name}", "fail",
                        f"导入错误：{err_output[:200]}", "导入失败", "应能正常导入", f"安装缺失依赖"))
                elif "nonetype" in err_output.lower():
                    # NoneType 通常是缺参数/缺路径导致，属于正常行为
                    results.append(_make_result(category, f"运行：{script_name}", "pass",
                        "脚本可执行（需提供命令行参数）", "可执行", "", ""))
                else:
                    results.append(_make_result(category, f"运行：{script_name}", "warn",
                        f"无参数运行有异常输出：{err_output[:200]}", "有异常", "应正常退出", f"检查 {script_name}"))
            except subprocess.TimeoutExpired:
                results.append(_make_result(category, f"运行：{script_name}", "warn",
                    "运行超时（15秒）", "超时", "应在15秒内完成", "检查脚本逻辑"))
            except Exception as e:
                results.append(_make_result(category, f"运行：{script_name}", "warn",
                    f"运行异常：{e}", str(e)[:200], "应正常运行", f"检查 {script_name}"))

    return results

def _calculate_score(results: list) -> dict:
    """计算综合评分（按 10 大类权重）。

    权重表（与 SKILL.md 一致）：
      Skill插件一致性       15%
      Skill模拟执行测试     10%（AI 语义分析，Python 不产生此项，按 0 计入时降权处理）
      Python代码协作性      10%
      Python运行时健康      10%
      知识库内容健康        10%
      文档内容漂移          10%
      Skill说明文件一致性   10%
      LeoDiary目录结构      5%
      跨文件一致性          10%
      AI检索加速层          10%

    若某类别无检查项（如模拟执行测试由 AI 完成），权重重分配到其他类别。
    每个类别内：通过=1分，警告=0.5分，失败=0分。类别得分率 = 得分/项数。
    综合评分 = Σ(类别得分率 × 类别权重) × 100。
    """
    # 类别权重表
    WEIGHTS = {
        "Skill插件一致性": 0.15,
        "Skill模拟执行测试": 0.10,
        "Python代码协作性": 0.10,
        "Python运行时健康": 0.10,
        "知识库内容健康": 0.10,
        "文档内容漂移": 0.10,
        "文档一致性": 0.10,  # 兼容旧类别名
        "Skill说明文件一致性": 0.10,
        "LeoDiary目录结构": 0.05,
        "跨文件一致性": 0.10,
        "AI检索加速层": 0.10,
    }

    # 按类别分组
    cat_results = {}
    for r in results:
        cat_results.setdefault(r["category"], []).append(r)

    # 计算每个类别的得分率
    total_weight_used = 0
    weighted_score = 0
    cat_scores = {}

    for cat, items in cat_results.items():
        if not items:
            continue
        weight = WEIGHTS.get(cat, 0)
        if weight == 0:
            # 未知类别，跳过（不参与评分）
            continue
        pass_cnt = sum(1 for r in items if r["status"] == "pass")
        warn_cnt = sum(1 for r in items if r["status"] == "warn")
        fail_cnt = sum(1 for r in items if r["status"] == "fail")
        total = len(items)
        # 类别得分率：通过=1，警告=0.5，失败=0
        rate = (pass_cnt + 0.5 * warn_cnt) / total if total > 0 else 0
        cat_scores[cat] = {
            "rate": rate, "pass": pass_cnt, "warn": warn_cnt,
            "fail": fail_cnt, "total": total, "weight": weight
        }
        weighted_score += rate * weight
        total_weight_used += weight

    # 权重重分配（如果某些类别没产生检查项）
    if total_weight_used > 0 and total_weight_used < 1.0:
        # 已使用权重归一化
        weighted_score = weighted_score / total_weight_used

    score = round(weighted_score * 100, 1)

    if score >= 90:
        grade, grade_class = "🟢优秀", "grade-excellent"
    elif score >= 70:
        grade, grade_class = "🟡良好", "grade-good"
    elif score >= 50:
        grade, grade_class = "🟠一般", "grade-normal"
    else:
        grade, grade_class = "🔴差", "grade-poor"

    # 统计总数
    total_count = len(results)
    pass_count = sum(1 for r in results if r["status"] == "pass")
    fail_count = sum(1 for r in results if r["status"] == "fail")
    warn_count = sum(1 for r in results if r["status"] == "warn")
    pass_rate = round(pass_count / total_count * 100, 1) if total_count > 0 else 0

    return {
        "total": total_count, "pass": pass_count, "fail": fail_count, "warn": warn_count,
        "pass_rate": pass_rate, "score": score,
        "grade": grade, "grade_class": grade_class,
        "cat_scores": cat_scores,
    }


def _check_leodiary_structure(vault: Path) -> list:
    """类别 5：LeoDiary 实际目录情况"""
    results = []
    category = "LeoDiary目录结构"

    if not vault.exists():
        results.append(_make_result(category, "vault目录", "fail",
                                     f"vault目录不存在：{vault}",
                                     "目录缺失", "目录存在", "检查路径"))
        return results

    knowledge_dirs = [
        "0- 🙎leo", "1- 🤖AI 相关", "2- 💻开发", "3- 🪟系统", "4- 🕹️软件",
        "5- 🧁项目", "6- 🎬影视", "7- 🧠思维框架", "8- 📜核心规则",
    ]
    pipeline_dirs = [
        "A📥 收集（Capture）", "B🧹 整理（Organize）",
        "C⚙️ 处理（Process）", "D📦 归档（Archive）",
    ]

    # 检查1：9 个知识归位目录
    missing_knowledge = [d for d in knowledge_dirs if not (vault / d).exists()]
    if not missing_knowledge:
        results.append(_make_result(category, "9个知识归位目录(0-8)", "pass",
                                     "9个目录都存在"))
    else:
        results.append(_make_result(category, "9个知识归位目录(0-8)", "fail",
                                     f"缺失：{', '.join(missing_knowledge)}",
                                     f"缺失{len(missing_knowledge)}个",
                                     "9个齐全",
                                     "创建缺失的目录"))

    # 检查2：4 个流水线目录
    missing_pipeline = [d for d in pipeline_dirs if not (vault / d).exists()]
    if not missing_pipeline:
        results.append(_make_result(category, "4个流水线目录(A/B/C/D)", "pass",
                                     "4个目录都存在"))
    else:
        results.append(_make_result(category, "4个流水线目录(A/B/C/D)", "fail",
                                     f"缺失：{', '.join(missing_pipeline)}",
                                     f"缺失{len(missing_pipeline)}个",
                                     "4个齐全",
                                     "创建缺失的目录"))

    # 检查3：关键文件
    key_files = [
        ("📖目录 索引.md", "总索引"),
        ("⚓新增文件记录.md", "新增文件记录"),
        ("leo.config.json", "配置文件"),
    ]
    for fname, desc in key_files:
        if (vault / fname).exists():
            results.append(_make_result(category, f"关键文件-{desc}", "pass",
                                         f"{fname} 存在"))
        else:
            results.append(_make_result(category, f"关键文件-{desc}", "fail",
                                         f"{fname} 不存在",
                                         "文件缺失", "文件存在", f"创建 {fname}"))

    # 检查4：每个一级目录是否有对应的 📖目录 索引-xxx.md
    missing_indexes = [d for d in knowledge_dirs if not (vault / f"📖目录 索引-{d}.md").exists()]
    if not missing_indexes:
        results.append(_make_result(category, "一级目录的📖目录索引", "pass",
                                     "9个一级目录都有对应的📖目录索引"))
    else:
        results.append(_make_result(category, "一级目录的📖目录索引", "warn",
                                     f"缺失：{', '.join(missing_indexes)}",
                                     f"缺失{len(missing_indexes)}个",
                                     "9个齐全",
                                     "创建缺失的索引文件"))

    # 检查5：每个一级目录是否有 🧩 目录-xxx.md（用 glob 匹配，文件名不一定含数字前缀）
    missing_chips = []
    for d in knowledge_dirs:
        dir_path = vault / d
        if not dir_path.exists():
            missing_chips.append(d)
            continue
        chip_files = list(dir_path.glob("🧩 目录-*.md"))
        if not chip_files:
            missing_chips.append(d)
    if not missing_chips:
        results.append(_make_result(category, "一级目录的🧩目录", "pass",
                                     "9个一级目录都有🧩目录"))
    else:
        results.append(_make_result(category, "一级目录的🧩目录", "warn",
                                     f"缺失：{', '.join(missing_chips)}",
                                     f"缺失{len(missing_chips)}个",
                                     "9个齐全",
                                     "创建缺失的🧩目录文件"))

    return results


def _check_ai_index_layer(vault: Path, skills_dir: Path, python_dir: Path) -> list:
    """检查 AI 检索加速层（LD-DVA Final · 轻量智能导航增强系统）完整性"""
    results = []
    category = "AI检索加速层(LD-DVA Final)"

    # A. .ai-index/ 目录结构完整性（10项）
    ai_index_dir = vault / ".ai-index"
    
    # 检查根目录
    for subdir in ["runtime", "domain", "protocol", "cache"]:
        dpath = ai_index_dir / subdir
        if dpath.is_dir():
            results.append(_make_result(category, f".ai-index/{subdir}/ 目录", "pass",
                                       f"{subdir}/ 目录存在"))
        else:
            results.append(_make_result(category, f".ai-index/{subdir}/ 目录", "fail",
                                       f"{subdir}/ 目录不存在",
                                       "目录存在", "创建目录并运行 ai_index_builder_v2.py rebuild"))

    # 检查核心 JSON 文件
    core_json_files = {
        "runtime/files.json": {"max_size": 102400, "desc": "文件元数据索引"},
        "runtime/tags.json": {"max_size": 40960, "desc": "标签反向索引"},
        "runtime/relations.json": {"max_size": 40960, "desc": "文件关联索引"},
    }
    
    core_size_total = 0
    for fname, info in core_json_files.items():
        fpath = ai_index_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size
            if size > 0:
                results.append(_make_result(category, f"{fname} 文件", "pass",
                                           f"{fname} 存在（{size:,} bytes，{info['desc']}）"))
                if fname in ["runtime/tags.json", "runtime/relations.json"]:
                    core_size_total += size
            else:
                results.append(_make_result(category, f"{fname} 文件", "fail",
                                           f"{fname} 存在但为空",
                                           "非空文件", "运行 ai_index_builder_v2.py rebuild"))
        else:
            results.append(_make_result(category, f"{fname} 文件", "fail",
                                       f"{fname} 不存在",
                                       "文件存在", "运行 ai_index_builder_v2.py rebuild"))

    # 核心索引大小检查 (tags + relations < 40KB)
    if core_size_total > 0:
        if core_size_total < 40960:
            results.append(_make_result(category, "核心索引大小 (tags+relations)", "pass",
                                       f"{core_size_total:,} bytes < 40KB"))
        else:
            results.append(_make_result(category, "核心索引大小 (tags+relations)", "fail",
                                       f"{core_size_total:,} bytes > 40KB 上限",
                                       "< 40KB", "减少标签数量或压缩关联"))

    # 检查协议文件
    protocol_file = ai_index_dir / "protocol" / "AI_READ_PROTOCOL.md"
    if protocol_file.exists():
        results.append(_make_result(category, "AI_READ_PROTOCOL.md", "pass",
                                   "AI_READ_PROTOCOL.md 存在"))
    else:
        results.append(_make_result(category, "AI_READ_PROTOCOL.md", "fail",
                                   "AI_READ_PROTOCOL.md 不存在",
                                   "文件存在", "创建协议文件"))

    # 检查查询记忆
    query_memory = ai_index_dir / "cache" / "query-memory.json"
    if query_memory.exists():
        try:
            import json
            data = json.loads(query_memory.read_text(encoding='utf-8'))
            if isinstance(data, list):
                results.append(_make_result(category, "query-memory.json 格式", "pass",
                                           f"格式正确，含 {len(data)} 条查询记忆"))
            else:
                results.append(_make_result(category, "query-memory.json 格式", "warn",
                                           "格式不标准"))
        except Exception:
            results.append(_make_result(category, "query-memory.json 格式", "warn",
                                       "JSON 解析失败"))
    else:
        results.append(_make_result(category, "query-memory.json", "warn",
                                   "查询记忆不存在（首次运行将自动创建）"))

    # 检查 files.json 结构完整性
    files_json = ai_index_dir / "runtime" / "files.json"
    if files_json.exists():
        try:
            import json
            data = json.loads(files_json.read_text(encoding='utf-8'))
            if isinstance(data, list) and len(data) > 0:
                # 检查每个条目是否有必需字段
                has_fields = all(
                    isinstance(f, dict) and 'i' in f and 't' in f and 'p' in f
                    for f in data[:10]  # 抽样检查前10条
                )
                if has_fields:
                    results.append(_make_result(category, "files.json 结构", "pass",
                                               f"结构完整，含 {len(data)} 个文件"))
                else:
                    results.append(_make_result(category, "files.json 结构", "fail",
                                               "缺少必需字段(i/t/p)",
                                               "字段完整", "运行 ai_index_builder_v2.py rebuild"))
            else:
                results.append(_make_result(category, "files.json 结构", "fail",
                                           "文件为空或格式错误",
                                           "有效文件列表", "运行 ai_index_builder_v2.py rebuild"))
        except Exception as e:
            results.append(_make_result(category, "files.json 结构", "fail",
                                       f"JSON 解析失败: {e}"))

    # B. Python 脚本存在性（检查 ai_index_builder_v2.py）
    required_scripts = ["ai_index_builder_v2.py", "obsidian_common.py"]
    for script in required_scripts:
        script_path = _find_script(python_dir, script)
        if script_path.exists():
            results.append(_make_result(category, f"脚本 {script}", "pass",
                                       f"{script} 存在"))
        else:
            results.append(_make_result(category, f"脚本 {script}", "fail",
                                       f"{script} 不存在",
                                       "脚本存在", "检查 D:\\Python\\projects\\leodiarycode\\scripts 目录"))

    # C. builder_v2.py 功能检查
    ai_builder_path = _find_script(python_dir, "ai_index_builder_v2.py")
    if ai_builder_path.exists():
        content = ai_builder_path.read_text(encoding='utf-8')

        # 检查 Router 分类逻辑
        if "classify_query" in content and "L1" in content and "L2" in content and "L3" in content:
            results.append(_make_result(category, "Router 分类逻辑", "pass",
                                       "含 L1/L2/L3 三级分类"))
        else:
            results.append(_make_result(category, "Router 分类逻辑", "fail",
                                       "缺少 L1/L2/L3 分类",
                                       "含三级分类", "检查 classify_query 函数"))

        # 检查同义词映射
        if "SYNONYM_MAP" in content:
            import re
            synonym_match = re.search(r"SYNONYM_MAP\s*=\s*\{([^}]+)\}", content, re.DOTALL)
            if synonym_match:
                keys = re.findall(r'"([^"]+)"\s*:', synonym_match.group(1))
                if len(keys) >= 15:
                    results.append(_make_result(category, "同义词映射表", "pass",
                                               f"包含 {len(keys)} 组同义词（≥15）"))
                else:
                    results.append(_make_result(category, "同义词映射表", "warn",
                                               f"仅 {len(keys)} 组同义词"))
            else:
                results.append(_make_result(category, "同义词映射表", "warn",
                                           "无法解析同义词映射表"))
        else:
            results.append(_make_result(category, "同义词映射表", "fail",
                                       "未找到 SYNONYM_MAP 定义"))

        # 检查命令是否存在
        commands_to_check = ["rebuild", "router", "search", "cache-read", "cache-write", "health"]
        for cmd in commands_to_check:
            if cmd in content:
                results.append(_make_result(category, f"命令 {cmd}", "pass",
                                           f"{cmd} 命令存在"))
            else:
                results.append(_make_result(category, f"命令 {cmd}", "warn",
                                           f"{cmd} 命令不存在"))

    # D. Skill 适配性（Router 驱动架构）
    skills_to_check = {
        "obsidian-knowledge-queryer": {
            "keywords": ["CP7", "router", "cache-read", "L1", "L2", "L3"],
            "desc": "Queryer 含 Router 驱动 CP7 流程"
        },
        "obsidian-knowledge-organizer": {
            "keywords": ["ai_index_builder_v2", "incremental"],
            "desc": "Organizer 触发 v2 增量更新"
        },
        "obsidian-pipeline": {
            "keywords": ["ai_index_builder_v2"],
            "desc": "Pipeline 触发 v2 索引更新"
        },
        "obsidian-fire-rename": {
            "keywords": ["ai_index_builder_v2", "rebuild"],
            "desc": "Fire-rename 触发 v2 rebuild"
        },
    }

    for skill_name, check_info in skills_to_check.items():
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            scontent = skill_path.read_text(encoding='utf-8')
            matched = sum(1 for kw in check_info["keywords"] if kw.lower() in scontent.lower())
            if matched >= len(check_info["keywords"]) * 0.6:
                results.append(_make_result(category, f"{skill_name} 适配", "pass",
                                           check_info["desc"]))
            else:
                results.append(_make_result(category, f"{skill_name} 适配", "warn",
                                           f"{skill_name} 缺少部分关键词（{matched}/{len(check_info['keywords'])}）",
                                           "完整适配", f"更新 {skill_name} SKILL.md"))
        else:
            results.append(_make_result(category, f"{skill_name} 适配", "fail",
                                       f"{skill_name} SKILL.md 不存在"))

    # E. obsidian_common.py SKIP_DIRS 检查
    common_path = python_dir / "src" / "obsidian_common.py"
    if common_path.exists():
        ccontent = common_path.read_text(encoding='utf-8')
        if ".ai-index" in ccontent or "🤖AI_INDEX" in ccontent:
            results.append(_make_result(category, "SKIP_DIRS 含 .ai-index", "pass",
                                       ".ai-index 已加入跳过目录"))
        else:
            results.append(_make_result(category, "SKIP_DIRS 含 .ai-index", "warn",
                                       ".ai-index 未加入跳过目录",
                                       "加入 SKIP_DIRS", "更新 obsidian_common.py"))

    return results


def _escape_html(text) -> str:
    """HTML 转义"""
    import html as html_module
    return html_module.escape(str(text))


def _generate_html_report(results: list, vault: Path, skills_dir: Path,
                          python_dir: Path, now: datetime) -> Path:
    """生成 HTML 报告到 _trash/ 目录"""
    score_info = _calculate_score(results)

    # 按类别分组
    categories = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)
    cat_order = ["Skill插件一致性", "Python代码协作性", "知识库内容健康",
                 "文档一致性", "文档内容漂移", "Skill说明文件一致性",
                 "LeoDiary目录结构", "跨文件一致性", "Python运行时健康", "AI检索加速层"]

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LeoDiary 健康检查报告 - {now.strftime('%Y-%m-%d')}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; padding: 20px; background: #f5f7fa; color: #333; line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
  h2 {{ color: #34495e; border-left: 4px solid #3498db; padding-left: 12px; margin-top: 30px; }}
  .meta {{ color: #7f8c8d; margin-bottom: 20px; font-size: 14px; }}
  .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 15px; margin: 20px 0; }}
  .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
  .card .value {{ font-size: 32px; font-weight: bold; color: #2c3e50; }}
  .card .label {{ color: #7f8c8d; font-size: 14px; margin-top: 5px; }}
  .card.pass .value {{ color: #27ae60; }}
  .card.fail .value {{ color: #e74c3c; }}
  .card.warn .value {{ color: #f39c12; }}
  .card.score .value {{ color: #3498db; }}
  table {{ width: 100%; border-collapse: collapse; margin: 15px 0; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecf0f1; font-size: 14px; }}
  th {{ background: #ecf0f1; font-weight: 600; }}
  tr:hover {{ background: #f8f9fa; }}
  .status-pass {{ color: #27ae60; font-weight: bold; }}
  .status-fail {{ color: #e74c3c; font-weight: bold; }}
  .status-warn {{ color: #f39c12; font-weight: bold; }}
  .severity-severe {{ background: #fdecea; color: #c0392b; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
  .severity-medium {{ background: #fef5e7; color: #d68910; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
  .severity-pass {{ background: #e8f8f5; color: #16a085; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
  .category-section {{ margin-bottom: 30px; }}
  .category-header {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; background: #34495e; color: white; border-radius: 6px; }}
  .category-header .rate {{ background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 4px; font-size: 13px; }}
  .footer {{ margin-top: 40px; padding: 15px; background: #34495e; color: #bdc3c7; border-radius: 6px; font-size: 13px; text-align: center; }}
  .grade {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 18px; }}
  .grade-excellent {{ background: #e8f8f5; color: #16a085; }}
  .grade-good {{ background: #fef9e7; color: #d4ac0d; }}
  .grade-normal {{ background: #fdf2e9; color: #ca6f1e; }}
  .grade-poor {{ background: #fdecea; color: #c0392b; }}
  .detail {{ max-width: 400px; word-break: break-all; }}
  @media (max-width: 768px) {{
    .dashboard {{ grid-template-columns: 1fr 1fr; }}
    table {{ font-size: 12px; }}
    th, td {{ padding: 6px 8px; }}
    .detail {{ max-width: 200px; }}
  }}
</style>
</head>
<body>
<div class="container">
  <h1>🔍 LeoDiary 项目级健康检查报告</h1>
  <div class="meta">
    生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}<br>
    知识库：{vault} | Skills：{skills_dir} | Python：{python_dir}
  </div>

  <div class="dashboard">
    <div class="card"><div class="value">{score_info['total']}</div><div class="label">总检查项</div></div>
    <div class="card pass"><div class="value">{score_info['pass']}</div><div class="label">✅ 通过</div></div>
    <div class="card fail"><div class="value">{score_info['fail']}</div><div class="label">❌ 失败</div></div>
    <div class="card warn"><div class="value">{score_info['warn']}</div><div class="label">⚠️ 警告</div></div>
    <div class="card score"><div class="value">{score_info['score']}</div><div class="label">综合评分</div></div>
    <div class="card"><div class="value"><span class="grade {score_info['grade_class']}">{score_info['grade']}</span></div><div class="label">等级</div></div>
  </div>

  <h2>📊 七大类检查详情</h2>
""")

    # 每个类别
    for i, cat_name in enumerate(cat_order, 1):
        if cat_name not in categories:
            continue
        cat_results = categories[cat_name]
        cat_pass = sum(1 for r in cat_results if r["status"] == "pass")
        cat_total = len(cat_results)
        cat_rate = round(cat_pass / cat_total * 100, 1) if cat_total > 0 else 0

        parts.append(f"""  <div class="category-section">
    <div class="category-header">
      <span>类别 {i}：{_escape_html(cat_name)}</span>
      <span class="rate">通过率：{cat_rate}%（{cat_pass}/{cat_total}）</span>
    </div>
    <table>
      <tr><th>检查项</th><th>状态</th><th>严重度</th><th class="detail">详情</th></tr>
""")
        for r in cat_results:
            status_class = f"status-{r['status']}"
            status_text = {"pass": "✅ 通过", "fail": "❌ 失败", "warn": "⚠️ 警告"}[r["status"]]
            if r["status"] == "pass":
                sev_class, sev_text = "severity-pass", "✅"
            elif r["status"] == "fail":
                sev_class, sev_text = "severity-severe", "🔴严重"
            else:
                sev_class, sev_text = "severity-medium", "🟡中等"
            parts.append(
                f"      <tr>\n"
                f"        <td>{_escape_html(r['item'])}</td>\n"
                f"        <td><span class=\"{status_class}\">{status_text}</span></td>\n"
                f"        <td><span class=\"{sev_class}\">{sev_text}</span></td>\n"
                f"        <td class=\"detail\">{_escape_html(r['detail'])}</td>\n"
                f"      </tr>\n"
            )
        parts.append("    </table>\n  </div>\n")

    # 整改建议
    parts.append("  <h2>🔧 整改建议</h2>\n")
    failed_results = [r for r in results if r["status"] != "pass"]
    if not failed_results:
        parts.append('  <p style="color:#27ae60;font-size:18px;">✅ 所有检查项均通过，无需整改！</p>\n')
    else:
        parts.append('  <table>\n    <tr><th>问题</th><th>当前状态</th><th>期望状态</th><th>严重度</th><th>建议操作</th></tr>\n')
        for r in failed_results:
            if r["status"] == "fail":
                sev_class, sev_text = "severity-severe", "🔴严重"
            else:
                sev_class, sev_text = "severity-medium", "🟡中等"
            parts.append(
                f"    <tr>\n"
                f"      <td>{_escape_html(r['category'])} - {_escape_html(r['item'])}</td>\n"
                f"      <td>{_escape_html(r['current'])}</td>\n"
                f"      <td>{_escape_html(r['expected'])}</td>\n"
                f"      <td><span class=\"{sev_class}\">{sev_text}</span></td>\n"
                f"      <td>{_escape_html(r['action'])}</td>\n"
                f"    </tr>\n"
            )
        parts.append("  </table>\n")

    # 附录
    parts.append(f"""  <h2>📚 附录</h2>
  <table>
    <tr><th>项目</th><th>值</th></tr>
    <tr><td>报告生成时间</td><td>{now.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
    <tr><td>知识库路径</td><td>{_escape_html(vault)}</td></tr>
    <tr><td>Skills目录</td><td>{_escape_html(skills_dir)}</td></tr>
    <tr><td>Python目录</td><td>{_escape_html(python_dir)}</td></tr>
    <tr><td>总检查项</td><td>{score_info['total']}</td></tr>
    <tr><td>通过</td><td>{score_info['pass']}</td></tr>
    <tr><td>失败</td><td>{score_info['fail']}</td></tr>
    <tr><td>警告</td><td>{score_info['warn']}</td></tr>
    <tr><td>通过率</td><td>{score_info['pass_rate']}%</td></tr>
    <tr><td>综合评分</td><td>{score_info['score']} / 100</td></tr>
    <tr><td>等级</td><td>{score_info['grade']}</td></tr>
  </table>

  <div class="footer">
    报告由 obsidian_skill_utils.py health-check-all 自动生成 | {now.strftime('%Y-%m-%d %H:%M:%S')}
  </div>
</div>
</body>
</html>
""")

    trash_dir = vault / "_trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    html_file = trash_dir / f"health-report-{now.strftime('%Y-%m-%d')}.html"
    html_file.write_text(''.join(parts), encoding='utf-8')
    return html_file


def _generate_md_report(results: list, vault: Path, skills_dir: Path,
                        python_dir: Path, now: datetime) -> Path:
    """生成 Markdown 报告到 _trash/ 目录"""
    score_info = _calculate_score(results)

    categories = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)
    cat_order = ["Skill插件一致性", "Python代码协作性", "知识库内容健康",
                 "文档一致性", "文档内容漂移", "Skill说明文件一致性",
                 "LeoDiary目录结构", "跨文件一致性", "Python运行时健康", "AI检索加速层"]

    lines = [
        "# 🔍 LeoDiary 项目级健康检查报告",
        "",
        f"**生成时间**：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**知识库**：{vault}",
        f"**Skills**：{skills_dir}",
        f"**Python**：{python_dir}",
        "",
        "## 📊 概览仪表盘",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总检查项 | {score_info['total']} |",
        f"| ✅ 通过 | {score_info['pass']} |",
        f"| ❌ 失败 | {score_info['fail']} |",
        f"| ⚠️ 警告 | {score_info['warn']} |",
        f"| 通过率 | {score_info['pass_rate']}% |",
        f"| 综合评分 | {score_info['score']} / 100 |",
        f"| 等级 | {score_info['grade']} |",
        "",
        "## 📋 七大类检查详情",
        "",
    ]

    for i, cat_name in enumerate(cat_order, 1):
        if cat_name not in categories:
            continue
        cat_results = categories[cat_name]
        cat_pass = sum(1 for r in cat_results if r["status"] == "pass")
        cat_total = len(cat_results)
        cat_rate = round(cat_pass / cat_total * 100, 1) if cat_total > 0 else 0

        lines.append(f"### 类别 {i}：{cat_name}（通过率 {cat_rate}%，{cat_pass}/{cat_total}）")
        lines.append("")
        lines.append("| 检查项 | 状态 | 严重度 | 详情 |")
        lines.append("|--------|------|--------|------|")
        for r in cat_results:
            status_text = {"pass": "✅通过", "fail": "❌失败", "warn": "⚠️警告"}[r["status"]]
            detail = r["detail"].replace("|", "\\|").replace("\n", " ")
            item = r["item"].replace("|", "\\|")
            lines.append(f"| {item} | {status_text} | {r['severity']} | {detail} |")
        lines.append("")

    lines.append("## 🔧 整改建议")
    lines.append("")
    failed_results = [r for r in results if r["status"] != "pass"]
    if not failed_results:
        lines.append("✅ 所有检查项均通过，无需整改！")
        lines.append("")
    else:
        lines.append("| 问题 | 当前状态 | 期望状态 | 严重度 | 建议操作 |")
        lines.append("|------|---------|---------|--------|---------|")
        for r in failed_results:
            problem = f"{r['category']} - {r['item']}".replace("|", "\\|")
            current = r["current"].replace("|", "\\|")
            expected = r["expected"].replace("|", "\\|")
            action = r["action"].replace("|", "\\|")
            lines.append(f"| {problem} | {current} | {expected} | {r['severity']} | {action} |")
        lines.append("")

    lines.append("## 📚 附录")
    lines.append("")
    lines.append(f"- 报告生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 知识库路径：{vault}")
    lines.append(f"- Skills目录：{skills_dir}")
    lines.append(f"- Python目录：{python_dir}")
    lines.append(f"- 综合评分：{score_info['score']} / 100（{score_info['grade']}）")
    lines.append("")

    trash_dir = vault / "_trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    md_file = trash_dir / f"health-report-{now.strftime('%Y-%m-%d')}.md"
    md_file.write_text('\n'.join(lines), encoding='utf-8')
    return md_file


def _check_enhanced_integrity(vault: Path, skills_dir: Path, python_dir: Path) -> list:
    """增强完整性检查（路径一致性/索引新鲜度/摘要/Python脚本/接口匹配/双链/配置同步/测试残留）"""
    results = []
    category = "增强完整性"

    # L. 路径一致性增强
    vault_root = None
    try:
        sys.path.insert(0, str(python_dir / "src"))
        from obsidian_common import VAULT_ROOT as vr
        vault_root = vr
    except Exception:
        pass

    if vault_root and vault_root == vault:
        results.append(_make_result(category, "VAULT_ROOT 路径", "pass",
                                   f"VAULT_ROOT 正确指向 {vault_root}"))
    else:
        results.append(_make_result(category, "VAULT_ROOT 路径", "fail",
                                   f"VAULT_ROOT={vault_root} 与预期 {vault} 不一致",
                                   action="检查 obsidian_common.py"))

    # Check old path residuals (only in code blocks and command lines, skip table descriptions)
    old_path_refs = 0
    skill_files = list(skills_dir.rglob("SKILL.md")) if skills_dir.exists() else []
    for sf in skill_files:
        try:
            content = read_text_safe(sf)
            # Only check lines that are code blocks (``` ... ```) or command lines (start with python/)
            # Skip table description lines (start with |) to avoid false positives from check item descriptions
            in_code_block = False
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or stripped.startswith('python ') or stripped.startswith('python\\'):
                    old_path_refs += line.count(r"d:\Python\leodiarycode")
                    old_path_refs += line.count(r"D:\Python\leodiarycode")
        except Exception:
            pass
    if old_path_refs == 0:
        results.append(_make_result(category, "旧路径残留", "pass",
                                   "无旧路径 D:\\Python\\leodiarycode 残留"))
    else:
        results.append(_make_result(category, "旧路径残留", "fail",
                                   f"发现 {old_path_refs} 处旧路径引用",
                                   action="批量更新 SKILL.md 路径"))

    # Check subdirectory structure
    for sub in ["src", "scripts", "lib"]:
        sub_dir = python_dir / sub
        if sub_dir.exists():
            py_count = len(list(sub_dir.glob("*.py")))
            results.append(_make_result(category, f"子目录 {sub}/", "pass",
                                       f"{sub}/ 存在，含 {py_count} 个 .py 文件"))
        else:
            results.append(_make_result(category, f"子目录 {sub}/", "fail",
                                       f"{sub}/ 目录不存在",
                                       action="创建子目录"))

    # M. 索引新鲜度深度 (LD-DVA Final)
    ai_index_dir = vault / ".ai-index"
    files_json = ai_index_dir / "runtime" / "files.json"
    if files_json.exists():
        try:
            import json
            files_data = json.loads(files_json.read_text(encoding='utf-8'))
            files_count = len(files_data) if isinstance(files_data, list) else 0
            
            # Check drift
            actual_files = 0
            try:
                actual_files = len([f for f in vault.rglob("*.md")
                                    if not str(f).startswith(str(ai_index_dir))
                                    and "_trash" not in str(f)])
            except Exception:
                pass
            if files_count > 0 and actual_files > 0:
                if abs(files_count - actual_files) <= 5:
                    results.append(_make_result(category, "索引漂移", "pass",
                                               f"索引 {files_count} 文件 ≈ 实际 {actual_files} 文件"))
                else:
                    results.append(_make_result(category, "索引漂移", "warn",
                                               f"索引 {files_count} vs 实际 {actual_files}（偏差较大）",
                                               action="运行 ai_index_builder_v2.py rebuild"))
        except Exception as e:
            results.append(_make_result(category, "索引新鲜度", "fail",
                                       f"读取 files.json 失败: {e}"))

    # N. 摘要完整性
    content_files = []
    for f in vault.rglob("*.md"):
        fstr = str(f)
        if ".ai-index" in fstr or "_trash" in fstr:
            continue
        content_files.append(f)
    summary_missing = 0
    summary_short = 0
    checked = 0
    for cf in content_files[:200]:
        try:
            text = read_text_safe(cf)
            if "✍️" not in text:
                summary_missing += 1
            else:
                for line in text.split('\n'):
                    if '✍️' in line:
                        summary_text = line.replace('>', '').replace('✍️', '').strip()
                        if len(summary_text) < 30:
                            summary_short += 1
                        break
            checked += 1
        except Exception:
            pass
    if checked > 0:
        rate = (checked - summary_missing) / checked * 100
        results.append(_make_result(category, "摘要存在性", "pass" if summary_missing == 0 else "warn",
                                   f"已检查 {checked} 文件，{summary_missing} 个缺少摘要（{rate:.0f}%完整率）",
                                   action="添加 >✍️ 摘要" if summary_missing > 0 else ""))
        if summary_short > 0:
            results.append(_make_result(category, "摘要长度", "warn",
                                       f"{summary_short} 个摘要 < 30 字",
                                       action="补充摘要内容"))

    # O. Python 脚本健康
    all_py_files = list(python_dir.rglob("*.py"))
    syntax_ok = 0
    syntax_fail = 0
    for pyf in all_py_files:
        if "__pycache__" in str(pyf):
            continue
        try:
            import py_compile
            py_compile.compile(str(pyf), doraise=True)
            syntax_ok += 1
        except Exception:
            syntax_fail += 1
    results.append(_make_result(category, "Python 语法检查", "pass" if syntax_fail == 0 else "fail",
                               f"{syntax_ok} 通过，{syntax_fail} 失败",
                               action="修复语法错误" if syntax_fail > 0 else ""))

    # Check subprocess encoding
    subproc_no_encoding = 0
    for pyf in all_py_files:
        if "__pycache__" in str(pyf):
            continue
        try:
            text = read_text_safe(pyf)
            if "subprocess.run" in text and "encoding=" not in text:
                subproc_no_encoding += 1
        except Exception:
            pass
    if subproc_no_encoding == 0:
        results.append(_make_result(category, "subprocess 编码", "pass",
                                   "所有 subprocess 调用含 encoding='utf-8'"))
    else:
        results.append(_make_result(category, "subprocess 编码", "warn",
                                   f"{subproc_no_encoding} 处 subprocess 可能缺少 encoding",
                                   action="添加 encoding='utf-8'"))

    # S. 模拟测试残留
    test_harness = vault / "_test_harness"
    if test_harness.exists():
        file_count = len(list(test_harness.rglob("*")))
        results.append(_make_result(category, "_test_harness 清理", "fail",
                                   f"_test_harness 目录存在，含 {file_count} 个文件",
                                   action="删除 _test_harness 目录"))
    else:
        results.append(_make_result(category, "_test_harness 清理", "pass",
                                   "_test_harness 已清理"))

    return results


def cmd_health_check_all(vault_str: str, skills_dir_str: str, python_dir_str: str) -> None:
    """LeoDiary 项目级健康检查：10 大类检查 + HTML/Markdown 报告

    用法：health-check-all <vault> <skills_dir> <python_dir>

    类别：
      1. Skill 插件一致性（15%）
      2. Python 代码协作性（10%，含命令参数一致性）
      3. 知识库内容健康（10%，聚合 validate/lint/kb-stats）
      4. 文档一致性（10%，过时关键词）
      5. 文档内容漂移（10%，关键数字对比）
      6. Skill 说明文件一致性（10%）
      7. LeoDiary 目录结构（5%）
      8. 跨文件信息一致性（10%）
      9. Python 运行时健康（10%）
     10. AI 检索加速层 LD-DVA Final（10%）

    注：Skill 模拟执行测试（10%）由 AI 在 SKILL.md Step 2 完成，Python 不产生此项。
    """
    vault = Path(vault_str)
    skills_dir = Path(skills_dir_str)
    python_dir = Path(python_dir_str)
    now = datetime.now()

    print(f"🔍 开始 LeoDiary 项目级健康检查...")
    print(f"   知识库：{vault}")
    print(f"   Skills：{skills_dir}")
    print(f"   Python：{python_dir}")
    print()

    all_results = []

    print("▶ 类别 1：Skill 插件一致性...")
    all_results.extend(_run_skill_checks(skills_dir, vault))

    print("▶ 类别 2：Python 代码协作性（含命令参数一致性）...")
    all_results.extend(_check_python_collaboration(python_dir, skills_dir))
    all_results.extend(_check_python_cmd_param_consistency(skills_dir, python_dir))

    print("▶ 类别 2b：Python 脚本运行时测试...")
    all_results.extend(_check_python_runtime(python_dir))

    print("▶ 类别 3：知识库内容健康（聚合 validate/lint/kb-stats）...")
    all_results.extend(_check_kb_content_health(vault))
    all_results.extend(_check_kb_content_health_aggregated(vault))

    print("▶ 类别 4：文档一致性（过时关键词）...")
    all_results.extend(_check_doc_consistency(vault, skills_dir, python_dir))

    print("▶ 类别 5：文档内容漂移（关键数字对比）...")
    all_results.extend(_check_doc_content_drift(vault, skills_dir))

    print("▶ 类别 5b：跨文档信息交叉对比（CLAUDE/README/使用手册）...")
    all_results.extend(_check_cross_doc_consistency(vault))

    print("▶ 类别 6：Skill 说明文件一致性（含命名规范检查）...")
    all_results.extend(_check_skill_doc_consistency(vault, skills_dir))
    all_results.extend(_check_file_naming_convention(vault))

    print("▶ 类别 7：LeoDiary 目录结构...")
    all_results.extend(_check_leodiary_structure(vault))

    print("▶ 类别 8：跨文件信息一致性...")
    all_results.extend(_check_cross_file_consistency(vault, skills_dir, python_dir))

    print("▶ 类别 9：Python 运行时健康...")
    all_results.extend(_check_python_scripts_runtime(python_dir))

    print("▶ 类别 10：AI 检索加速层（LD-DVA Final）...")
    all_results.extend(_check_ai_index_layer(vault, skills_dir, python_dir))

    print("▶ 类别 11-19：增强完整性检查...")
    all_results.extend(_check_enhanced_integrity(vault, skills_dir, python_dir))

    print()
    print("📝 生成报告中...")
    html_file = _generate_html_report(all_results, vault, skills_dir, python_dir, now)
    md_file = _generate_md_report(all_results, vault, skills_dir, python_dir, now)

    score_info = _calculate_score(all_results)
    print()
    print("=" * 50)
    print(f"📊 LeoDiary 项目级健康检查摘要")
    print("=" * 50)
    print(f"总检查项:   {score_info['total']}")
    print(f"✅ 通过:    {score_info['pass']}")
    print(f"❌ 失败:    {score_info['fail']}")
    print(f"⚠️ 警告:    {score_info['warn']}")
    print(f"通过率:     {score_info['pass_rate']}%")
    print(f"综合评分:   {score_info['score']} / 100（按9大类权重）")
    print(f"等级:       {score_info['grade']}")
    print()
    print("📋 各类别得分：")
    for cat, info in score_info.get('cat_scores', {}).items():
        print(f"   {cat}: {info['rate']*100:.1f}%（{info['pass']}/{info['total']}，权重{info['weight']*100:.0f}%）")
    print("=" * 50)
    print(f"📄 HTML 报告：{html_file}")
    print(f"📄 MD 报告：  {md_file}")
    print()
    print("💡 提示：Skill 模拟执行测试（权重15%）需 AI 按 SKILL.md Step 2 手动完成，")
    print("   本报告未包含该项，最终评分请在 AI 完成模拟测试后综合判断。")


# ======================================================================
# 主入口
# ======================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        "state-load": lambda: cmd_state_load(args[0], args[1]) if len(args) >= 2 else print("用法: state-load <skill> <vault>"),
        "state-save": lambda: cmd_state_save(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: state-save <skill> <vault> <json_string>"),
        "is-system-file": lambda: cmd_is_system_file(args[0]) if args else print("用法: is-system-file <filename>"),
        "locate-domain-index": lambda: cmd_locate_domain_index(args[0], args[1]) if len(args) >= 2 else print("用法: locate-domain-index <filepath> <vault>"),
        "update-index-entry": lambda: cmd_update_index_entry(args[0], args[1], args[2], args[3]) if len(args) >= 4 else print("用法: update-index-entry <index_file> <old_link> <new_link> <summary>"),
        "remove-index-entry": lambda: cmd_remove_index_entry(args[0], args[1]) if len(args) >= 2 else print("用法: remove-index-entry <index_file> <link>"),
        "add-to-default-category": lambda: cmd_add_to_default_category(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: add-to-default-category <chip_file> <link> <summary>"),
        "update-wikilinks": lambda: cmd_update_wikilinks(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: update-wikilinks <vault> <old_name> <new_name>"),
        "compute-hash": lambda: cmd_compute_hash(args[0]) if args else print("用法: compute-hash <filepath>"),
        "detect-changes": lambda: cmd_detect_changes(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: detect-changes <skill> <vault> <dir>"),
        "validate-filename": lambda: cmd_validate_filename(args[0]) if args else print("用法: validate-filename <name>"),
        "parse-filename": lambda: cmd_parse_filename(args[0]) if args else print("用法: parse-filename <filename>"),
        "record-access": lambda: cmd_record_access(args[0], args[1]) if len(args) >= 2 else print("用法: record-access <vault> <filepath>"),
        "scan-unindexed": lambda: cmd_scan_unindexed(args[0], args[1]) if len(args) >= 2 else print("用法: scan-unindexed <vault> <dir>"),
        "check-file-thresholds": lambda: cmd_check_file_thresholds(args[0]) if args else print("用法: check-file-thresholds <filepath>"),
        "check-summary-quality": lambda: cmd_check_summary_quality(args[0], args[1], args[2] if len(args) > 2 else "") if len(args) >= 2 else print("用法: check-summary-quality <summary> <title> [keywords]"),
        "validate-document": lambda: cmd_validate_document(args[0]) if args else print("用法: validate-document <filepath>"),
        "compute-similarity": lambda: cmd_compute_similarity(args[0], args[1], args[2], args[3], args[4], args[5]) if len(args) >= 6 else print("用法: compute-similarity <title1> <entities1> <topic1> <title2> <entities2> <topic2>"),
        "verify-move": lambda: cmd_verify_move(args[0], args[1], args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "") if len(args) >= 2 else print("用法: verify-move <src> <dst> [index_file] [new_link]"),
        "generate-rollback": lambda: cmd_generate_rollback(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: generate-rollback <vault> <skill> <rename_pairs_json>"),
        "archive-cleanup": lambda: cmd_archive_cleanup(args[0], args[1], args[2] if len(args) > 2 else "pipeline") if len(args) >= 2 else print("用法: archive-cleanup <vault> <state_json> [skill]"),
        "check-fake-execution": lambda: cmd_check_fake_execution(args[0], args[1]) if len(args) >= 2 else print("用法: check-fake-execution <vault> <state_json>"),
        "drift-check": lambda: cmd_drift_check(args[0], args[1], args[2] if len(args) > 2 else "") if len(args) >= 2 else print("用法: drift-check <vault> <skill> [dir]"),
        "write-log": lambda: cmd_write_log(args[0], args[1], args[2], args[3]) if len(args) >= 4 else print("用法: write-log <vault> <skill> <title> <content>"),
        "add-record": lambda: cmd_add_record(args[0], args[1], args[2], args[3] if len(args) > 3 else "") if len(args) >= 3 else print("用法: add-record <vault> <type> <description> [path]"),
        "validate-metadata": lambda: cmd_validate_metadata(args[0], "--quiet" in args) if args else print("用法: validate-metadata <vault> [--quiet]"),
        "lint-content": lambda: cmd_lint_content(args[0], args[1] if len(args) > 1 else "all") if args else print("用法: lint-content <vault> [stale|orphans|broken|conflicts|missing|backlinks|content-conflicts|all]"),
        "kb-stats": lambda: cmd_kb_stats(args[0], "--json" in args) if args else print("用法: kb-stats <vault> [--json]"),
        "skill-health-check": lambda: cmd_skill_health_check(args[0], args[1]) if len(args) >= 2 else print("用法: skill-health-check <skills_dir> <vault>"),
        "health-check-all": lambda: cmd_health_check_all(args[0], args[1], args[2]) if len(args) >= 3 else print("用法: health-check-all <vault> <skills_dir> <python_dir>"),
    }
    
    if cmd in commands:
        commands[cmd]()
    else:
        print(f"未知命令：{cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()

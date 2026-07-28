#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量统一所有 🧩 目录-xxx.md 文件的分类标题格式
规则：
  - 分类标题统一为 `##### 图标 分类名` 格式
  - 图标从图标库按语义匹配，同一文件内不能重复
  - 已有分类（##/###/tab缩进）→ 转换格式并分配图标
  - 无分类 → 按文件路径/文件名做基础归类
  - 已有 ✍️ 摘要保留，没有的留空（后续 skill 补）
"""

import sys
import re
import random
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from obsidian_common import VAULT_ROOT, should_skip_dir

TODAY = date.today().isoformat()

# ===== 图标库（与 skill 对齐） =====
ICON_LIBRARY = {
    "流程/阶段": ["🔄", "🔁", "🔀", "🚦"],
    "小区/物业/建筑": ["🏢", "🏠", "🏘️", "🏗️", "🏛️"],
    "会议/记录": ["📝", "📋", "📄", "📑", "🗒️"],
    "沟通/消息": ["💬", "🗨️", "📢", "📨", "📱"],
    "系统文件/配置": ["🔧", "⚙️", "🔩", "🛠️", "🖥️"],
    "人员/招募": ["👥", "👤", "🙋", "🤝", "🎯"],
    "法律/规则": ["⚖️", "📜", "📚", "🔨"],
    "数据/统计": ["📊", "📈", "📉", "🔢", "📐"],
    "文档/材料": ["📦", "📁", "🗂️", "📌", "🗃️"],
    "AI/技术": ["🤖", "💡", "🧠", "⚡", "🔌"],
    "工具/软件": ["🛠️", "🔩", "⚙️", "💻", "📟"],
    "学习/知识": ["📖", "🎓", "🔍", "📚"],
    "影视/娱乐": ["🎬", "🎥", "🎵", "🎮", "🎨"],
    "账号/密码": ["🔑", "🔐", "🔒", "🎫"],
    "其他/兜底": ["📦", "🎁", "🎪", "🌟", "⭐"],
}

GENERIC_ICONS = ["📦", "🎁", "🎪", "🌟", "⭐", "🎯", "✨", "🔖", "🏷️", "💎", "🌈", "🎨"]

# 分类名 → 语义类别 匹配规则
CATEGORY_KEYWORDS = {
    "流程/阶段": ["流程", "阶段", "步骤", "过程", "基础", "前期", "进行中", "已完成", "进度"],
    "小区/物业/建筑": ["小区", "物业", "楼栋", "建筑", "社区", "街道", "住建", "房产", "小区信息"],
    "会议/记录": ["会议", "开会", "记录", "纪要", "签到", "出席", "总结会"],
    "沟通/消息": ["消息", "群", "聊天", "沟通", "通知", "公告", "反馈", "私聊"],
    "系统文件/配置": ["系统", "配置", "设置", "AI指令", "机器人", "插件", "工具", "脚本"],
    "人员/招募": ["人员", "招募", "招聘", "发起人", "推荐", "筹备组", "业主", "代表", "楼长"],
    "法律/规则": ["法律", "法规", "规则", "规约", "咨询", "起诉", "答辩", "证据", "法院", "判决"],
    "数据/统计": ["统计", "数据", "查询", "分析", "报告", "对比", "备案"],
    "文档/材料": ["材料", "文档", "资料", "附件", "归档", "整理", "收集", "基础资料", "筹备材料"],
    "AI/技术": ["AI", "模型", "API", "人工智能", "大模型", "prompt", "agent", "skill", "插件"],
    "工具/软件": ["工具", "软件", "安装", "配置", "部署", "教程", "命令", "CLI", "下载"],
    "学习/知识": ["学习", "知识", "教程", "指南", "速查", "笔记", "总结", "路线", "对比"],
    "影视/娱乐": ["影视", "电影", "电视", "音乐", "游戏", "作品", "导演", "演员"],
    "账号/密码": ["账号", "账户", "密码", "登录", "密钥", "token", "订阅", "注册"],
}


def match_icon(category_name: str, used_icons: set) -> str:
    """根据分类名匹配图标，返回未使用过的图标"""
    # 先找语义类别
    matched_category = None
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in category_name:
                matched_category = cat
                break
        if matched_category:
            break

    # 从匹配的类别图标中选一个未用过的
    if matched_category:
        for icon in ICON_LIBRARY.get(matched_category, []):
            if icon not in used_icons:
                return icon

    # 从通用图标池选
    for icon in GENERIC_ICONS:
        if icon not in used_icons:
            return icon

    # 兜底：随机选一个（极端情况）
    all_icons = [i for icons in ICON_LIBRARY.values() for i in icons] + GENERIC_ICONS
    for icon in all_icons:
        if icon not in used_icons:
            return icon
    # 实在没有了
    return "📦"


def extract_link_line(line: str) -> str:
    """从一行中提取 [[链接]] 和后面的 ✍️ 摘要"""
    stripped = line.strip()
    # 去掉开头的 - 或 tab
    stripped = re.sub(r'^[-*]\s+', '', stripped)
    stripped = stripped.lstrip('\t ')
    return stripped if '[[' in stripped else None


def parse_existing_classifications(content: str) -> list:
    """解析现有分类结构，返回 [(分类名, [链接行])]"""
    lines = content.splitlines()
    result = []
    current_cat = None
    current_links = []
    in_frontmatter = False
    fm_count = 0

    in_body = False  # 是否过了标题和一句话总结

    for line in lines:
        # 跳过 frontmatter
        if line.strip() == '---':
            fm_count += 1
            if fm_count <= 2:
                in_frontmatter = fm_count == 1
            continue
        if in_frontmatter:
            continue

        # 跳过标题行和一句话总结
        if line.startswith('# ') or '一句话总结' in line:
            in_body = True
            if current_cat and current_links:
                result.append((current_cat, current_links))
                current_cat = None
                current_links = []
            continue

        if not in_body:
            # 标题前的空行等
            continue

        # 检测分类标题
        # 格式1: ## xxx / ### xxx / ##### xxx
        heading_match = re.match(r'^#{2,5}\s+(.+?)\s*$', line)
        if heading_match and '[[' not in line:
            title = heading_match.group(1).strip()
            # 去掉开头的 emoji
            title = re.sub(r'^[\U00010000-\U0010ffff\u2600-\u27bf\U0001f300-\U0001faff\u2300-\u23ff]+', '', title).strip()
            if current_cat and current_links:
                result.append((current_cat, current_links))
            current_cat = title
            current_links = []
            continue

        # 格式2: tab缩进或 - 开头的链接行
        link = extract_link_line(line)
        if link:
            # 如果没有当前分类，可能是纯链接列表（无分类）
            if current_cat is None:
                current_cat = "未分类"
            current_links.append(link)
            continue

        # 空行或其他内容：不影响
        if line.strip() == '':
            continue

        # home 链接等底部内容 → 停止
        if '[[' in line and 'home' in line.lower():
            break

    if current_cat and current_links:
        result.append((current_cat, current_links))

    return result


def collect_all_links(content: str) -> list:
    """收集文件中所有 [[链接]] 行（用于无分类的文件）"""
    lines = content.splitlines()
    links = []
    in_frontmatter = False
    fm_count = 0
    for line in lines:
        if line.strip() == '---':
            fm_count += 1
            if fm_count <= 2:
                in_frontmatter = fm_count == 1
            continue
        if in_frontmatter:
            continue
        link = extract_link_line(line)
        if link:
            links.append(link)
    return links


def auto_classify_links(links: list, dir_name: str, dir_path: Path) -> list:
    """无分类时，根据文件名和目录特征做基础归类

    返回 [(分类名, [链接行])]
    """
    if not links:
        return []

    categories = {}
    others = []

    # 根据父目录名决定分类策略
    dir_lower = dir_name.lower()

    # 通用分类规则：按文件名中的前缀/特征分组
    for link in links:
        # 提取文件名
        m = re.search(r'\[\[(.+?)(?:\||\]\])', link)
        if not m:
            others.append(link)
            continue
        filename = m.group(1)

        # 判断分类
        cat = None
        # 含"咨询/问答/问题" → 咨询问答
        if any(kw in filename for kw in ['咨询', '问答', '问题', 'Q&A', 'qna']):
            cat = "❓ 咨询问答"
        # 含"教程/指南/速查/配置/安装" → 教程配置
        elif any(kw in filename for kw in ['教程', '指南', '速查', '配置', '安装', '部署', '使用']):
            cat = "📚 教程配置"
        # 含"记录/纪要/签到/会议" → 会议记录
        elif any(kw in filename for kw in ['记录', '纪要', '签到', '会议', '开会']):
            cat = "📝 会议记录"
        # 含"账号/密码/登录/密钥" → 账号管理
        elif any(kw in filename for kw in ['账号', '账户', '密码', '登录', '密钥', 'token']):
            cat = "🔑 账号管理"
        # 含"方案/设计/需求" → 方案设计
        elif any(kw in filename for kw in ['方案', '设计', '需求', '规划']):
            cat = "📋 方案设计"
        # 含"AI/模型/API/skill" → AI相关
        elif any(kw in filename.lower() for kw in ['ai', '模型', 'api', 'skill', 'agent', 'prompt']):
            cat = "🤖 AI相关"
        else:
            others.append(link)

        if cat:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(link)

    # 如果所有文件都分到了 others，或者分类数太少，用父目录名做一个总分类
    if not categories or (len(categories) == 1 and len(others) > 0):
        # 按路径一级目录分类
        pass  # 保持现有分类

    result = list(categories.items())
    if others:
        # others 放最后
        result.append(("📦 其他", others))

    # 按分类名排序
    result.sort(key=lambda x: x[0])

    return result


def rebuild_directory_file(content: str, dir_path: Path) -> tuple:
    """重建目录文件，返回 (新内容, 处理说明)"""
    lines = content.splitlines()

    # 提取 frontmatter
    fm_start = -1
    fm_end = -1
    fm_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            fm_count += 1
            if fm_count == 1:
                fm_start = i
            elif fm_count == 2:
                fm_end = i
                break

    fm_text = ''
    body_start = 0
    if fm_start >= 0 and fm_end > fm_start:
        fm_text = '\n'.join(lines[fm_start:fm_end+1]) + '\n'
        body_start = fm_end + 1
    else:
        fm_text = f"---\ncreated: {TODAY}\nmodified: {TODAY}\n---\n"

    # 提取标题和一句话总结
    title_line = ''
    summary_lines = []
    in_summary = False
    cls_start_line = -1

    for i in range(body_start, len(lines)):
        line = lines[i]
        if line.startswith('# ') and not title_line:
            title_line = line
            continue
        if '一句话总结' in line:
            in_summary = True
            summary_lines.append(line)
            continue
        if in_summary:
            # 总结内容（直到下一个 ## 或空行后有内容）
            if line.strip() == '':
                summary_lines.append(line)
                # 看看下一行是否是总结内容
                if i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith('#'):
                    continue
                else:
                    cls_start_line = i + 1
                    break
            elif not line.startswith('#'):
                summary_lines.append(line)
            else:
                cls_start_line = i
                break
            continue
        if line.startswith('## ') and '一句话总结' not in line:
            cls_start_line = i
            break
        if title_line and not in_summary and line.strip() and not line.startswith('>'):
            # 正文开始但还没找到总结，可能没有一句话总结
            cls_start_line = i
            break

    # 提取分类（或全部链接）
    cls = parse_existing_classifications(content)

    if not cls:
        # 没有分类，自动归类
        all_links = collect_all_links(content)
        dir_name = dir_path.parent.name
        cls = auto_classify_links(all_links, dir_name, dir_path)

    if not cls:
        return content, "无需修改（空目录）"

    # 分配图标
    used_icons = set()
    final_cls = []
    for cat_name, cat_links in cls:
        # 去掉分类名中已有的emoji前缀
        clean_name = re.sub(r'^[\U00010000-\U0010ffff\u2600-\u27bf\U0001f300-\U0001faff\u2300-\u23ff]+', '', cat_name).strip()
        icon = match_icon(clean_name, used_icons)
        used_icons.add(icon)
        final_cls.append((icon, clean_name, cat_links))

    # 重建正文
    new_body = []
    if title_line:
        new_body.append(title_line)
    new_body.append('')

    if summary_lines:
        # 去掉末尾的空行
        while summary_lines and summary_lines[-1].strip() == '':
            summary_lines.pop()
        new_body.extend(summary_lines)
        new_body.append('')

    # 添加分类
    for icon, cat_name, links in final_cls:
        new_body.append(f"##### {icon} {cat_name}")
        for link in links:
            new_body.append(f"- {link}")
        new_body.append('')

    # 检查是否有底部的 home 链接
    home_link = None
    for line in reversed(lines):
        if '[[' in line and 'home' in line.lower() and 'home-' in line:
            home_link = line.strip()
            break

    if home_link:
        new_body.append(home_link)
        new_body.append('')

    new_content = fm_text + '\n' + '\n'.join(new_body)
    # 确保末尾有一个空行
    if not new_content.endswith('\n'):
        new_content += '\n'

    return new_content, f"重建分类 ({len(final_cls)} 个分类)"


def process_file(path: Path) -> str:
    """处理单个文件"""
    try:
        content = path.read_text(encoding='utf-8-sig')
    except Exception as e:
        return f"读取失败: {e}"

    new_content, status = rebuild_directory_file(content, path)

    if new_content == content:
        return "无需修改"

    try:
        path.write_text(new_content, encoding='utf-8')
        return status
    except Exception as e:
        return f"写入失败: {e}"


def main():
    stats = {'processed': 0, 'skipped': 0, 'no_change': 0, 'failed': 0}
    results = []

    for path in sorted(VAULT_ROOT.rglob("🧩 目录-*.md")):
        rel = path.relative_to(VAULT_ROOT)
        skip = False
        for part in rel.parts[:-1]:
            if should_skip_dir(part):
                skip = True
                break
        if skip:
            stats['skipped'] += 1
            continue

        status = process_file(path)
        results.append((str(rel), status))

        if '失败' in status or '错误' in status:
            stats['failed'] += 1
        elif '无需修改' in status:
            stats['no_change'] += 1
        else:
            stats['processed'] += 1

    total = stats['processed'] + stats['no_change'] + stats['failed']
    print(f"\n{'='*60}")
    print(f"批量统一 🧩 目录-xxx.md 分类格式 完成")
    print(f"{'='*60}")
    print(f"总文件数: {total + stats['skipped']}")
    print(f"已处理:   {stats['processed']}")
    print(f"无需修改: {stats['no_change']}")
    print(f"已跳过:   {stats['skipped']}（隐藏/排除目录）")
    print(f"失败:     {stats['failed']}")
    print(f"{'='*60}\n")

    print("处理详情（前 40 条）:")
    for path_str, status in results[:40]:
        print(f"  [{status}] {path_str}")
    if len(results) > 40:
        print(f"  ... 还有 {len(results) - 40} 条")

    # 统计分类数量分布
    print(f"\n分类数量分布:")
    cat_counts = {}
    for path_str, status in results:
        if '重建分类' in status:
            m = re.search(r'(\d+) 个分类', status)
            if m:
                n = int(m.group(1))
                cat_counts[n] = cat_counts.get(n, 0) + 1
    for n in sorted(cat_counts.keys()):
        print(f"  {n} 个分类: {cat_counts[n]} 个文件")


if __name__ == '__main__':
    main()

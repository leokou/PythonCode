#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 笔记工具 - 共享配置模块
=================================
所有 Obsidian Python 脚本共用的配置、常量、工具函数。
统一管理，避免各脚本配置不一致。
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ======================================================================
# 核心路径
# ======================================================================

VAULT_ROOT = Path(r"D:\Obsidian\LeoDiary")

# ======================================================================
# 跳过目录（精确匹配）
# ======================================================================

SKIP_DIRS = {
    # 隐藏/系统目录
    ".obsidian", ".git", ".trash", ".claude", ".claudian",
    ".smart-env", ".workbuddy", "__pycache__", "node_modules",
    ".qoderworkcn",
    # Obsidian 特殊目录
    "templates", "Journals",
    "assets", "Canvas", "Clippings", "Excalidraw", "obsidian-index",
    # 日志目录（Skill状态文件，不参与结构维护）
    "logs",
    # 回收站
    "_trash",
    # AI 检索加速层（系统生成，非知识内容）
    "🤖AI_INDEX", ".ai-index",
    # LeoDiary 工具/文档目录（非知识内容）
    "script", "skills",
}

# ======================================================================
# 跳过目录（前缀匹配）
# ======================================================================

SKIP_DIR_PREFIXES = (
    'processed-',  # 归档子目录：processed-YYYY-MM-DD
)

# ======================================================================
# 跳过文件
# ======================================================================

# 跳过的文件前缀（索引类文件）
SKIP_FILES_PREFIX = ("🧩 目录-", "🏠 home-")

# 跳过的文件（精确匹配）
SKIP_FILES_EXACT = {"🤖 AI指令.md"}

# 跳过的扩展名
SKIP_EXTENSIONS = {".pyc", ".pyo"}

# ======================================================================
# PARA 文件夹列表
# ======================================================================

PARA_DIRS = {
    'A📥 收集（Capture）',
    'B🧹 整理（Organize）',
    'C⚙️ 处理（Process）',
    'D📦 归档（Archive）',
}

# ======================================================================
# 工具函数
# ======================================================================


def should_skip_dir(dir_name: str) -> bool:
    """判断目录是否应该被跳过（名称精确匹配 + 前缀匹配 + 点开头）"""
    if dir_name in SKIP_DIRS:
        return True
    if dir_name.startswith("."):
        return True
    for prefix in SKIP_DIR_PREFIXES:
        if dir_name.startswith(prefix):
            return True
    return False


def should_skip_file(file_name: str) -> bool:
    """判断文件是否应该被跳过（前缀匹配 + 精确匹配）"""
    if file_name in SKIP_FILES_EXACT:
        return True
    for prefix in SKIP_FILES_PREFIX:
        if file_name.startswith(prefix):
            return True
    return False


def is_markdown_file(file_name: str) -> bool:
    """判断是否为 .md 文件"""
    return file_name.lower().endswith(".md")


# ======================================================================
# 标题修正（统一实现，避免各脚本不一致）
# ======================================================================

def read_text_safe(file_path: Path) -> str:
    """安全读取文件，自动去除BOM"""
    try:
        content = file_path.read_text(encoding='utf-8-sig')
        return content
    except Exception:
        try:
            return file_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return ""


def has_frontmatter(content: str) -> bool:
    """判断文件是否有YAML frontmatter（--- 开头）"""
    stripped = content.lstrip()
    return stripped.startswith('---')


def ensure_title_header(file_path: Path) -> bool:
    """
    确保 .md 文件第一行是 "# 文件名"。
    安全处理：
    - BOM文件：自动去除BOM后判断
    - frontmatter文件：跳过标题修正（frontmatter必须在最前面）
    - 已有正确标题：跳过
    - 重复标题：去重
    返回是否修改了文件。
    """
    expected = f"# {file_path.stem}"
    content = read_text_safe(file_path)
    if not content.strip():
        try:
            file_path.write_text(expected + "\n", encoding='utf-8')
            return True
        except Exception:
            return False

    # 有frontmatter的文件，不修改标题（frontmatter必须在前）
    if has_frontmatter(content):
        return False

    lines = content.splitlines(keepends=True)
    first_line = lines[0].rstrip("\r\n") if lines else ""

    # 第一行已经是正确标题
    if first_line.strip() == expected:
        # 检查是否有重复标题（第3行也是相同标题）
        if len(lines) >= 3:
            third_line = lines[2].rstrip("\r\n").lstrip('\ufeff').strip()
            if third_line == expected:
                # 去除重复标题：保留第一行，删除第2-3行（空行+重复标题）
                del lines[2]
                if lines and lines[1].strip() == '':
                    del lines[1]
                try:
                    file_path.write_text("".join(lines), encoding='utf-8')
                    return True
                except Exception:
                    return False
        return False

    # 第一行是#开头但标题不对，替换
    if first_line.startswith("# "):
        nl = "\n" if ("\n" in lines[0] or "\r" in lines[0]) else ""
        lines[0] = expected + nl
        try:
            file_path.write_text("".join(lines), encoding='utf-8')
            return True
        except Exception:
            return False

    # 第一行不是#开头，在前面加标题
    new_content = expected + "\n\n" + content
    try:
        file_path.write_text(new_content, encoding='utf-8')
        return True
    except Exception:
        return False


def strip_frontmatter(content: str) -> str:
    """去除YAML frontmatter，返回正文内容。
    支持frontmatter不在第一行的情况（前面可有#标题、>✍️摘要、空行）。
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return content

    # 找第一个 --- 行（跳过前面的#标题、>✍️、空行）
    fm_start = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '---':
            fm_start = i
            break
        # 跳过：空行、#标题行、>✍️行
        if stripped == '' or stripped.startswith('#') or stripped.startswith('>✍️'):
            continue
        # 遇到其他内容，说明没有frontmatter
        return content

    if fm_start == -1:
        return content

    # 找第二个 ---
    fm_end = -1
    for i in range(fm_start + 1, len(lines)):
        if lines[i].strip() == '---':
            fm_end = i
            break

    if fm_end == -1:
        return content  # 没有闭合的frontmatter，原样返回

    # 返回frontmatter之后的内容
    result = "".join(lines[fm_end + 1:])
    return result.lstrip('\n')

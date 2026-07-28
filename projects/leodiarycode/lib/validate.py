"""LeoDiary 知识库校验脚本（LeoDiary 轻量标准）

与 LEO OS 的区别：
    - 不检查 id/owner/domain/status/description 等冗余字段
    - 按 LeoDiary 事实标准：type/tags/created/modified + ✍️ 摘要
    - type 用中文：知识/工具/项目文档/踩坑/FAQ/教程/清单/账号/会议
    - 检查 ✍️ 摘要是否存在（H1 下方）

仅依赖 Python 标准库，无需安装 PyYAML。

用法：
    python validate.py <vault_path>            # 检查全部
    python validate.py <vault_path> --quiet    # 只打印错误，不打印 OK

检查项：
    1. front matter 存在且可解析
    2. 必填字段齐全（type/tags/created/modified）
    3. type 字段在合法 9 种中文类型内
    4. tags 是数组且不少于 1 个
    5. 日期字段格式 YYYY-MM-DD（created/modified）
    6. ✍️ 摘要存在（H1 标题下方）
    7. 正文中的双链目标文件是否存在
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leo_common import (  # noqa: E402
    set_root,
    get_root,
    SKIP_DIRS,
    WIKI_LINK_RE,
    parse_front_matter,
    find_md_files,
    build_filename_index,
    resolve_wiki_link,
)

VALID_TYPES = {
    "知识", "工具", "项目文档", "踩坑", "FAQ", "教程", "清单", "账号", "会议",
    "决策", "规范", "记录",
}

REQUIRED_FIELDS = {"type", "tags", "created", "modified"}

DATE_FIELDS = {"created", "modified", "last_review"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

HEADING1_RE = re.compile(r"^# (.+)$", re.MULTILINE)
SUMMARY_RE = re.compile(r"^>✍️\s*\S+", re.MULTILINE)

SKIP_VALIDATION_PREFIXES = (
    "🧩 ",
    "📖",
    "🏠 ",
    "🤖 ",
    "⚓",
    "🍕 ",
)

SKIP_VALIDATION_FILES = {"CLAUDE.md", "README.md"}


def is_skippable_file(path: Path, root: Path) -> bool:
    """判断是否跳过校验（目录文件、索引文件等特殊文件）。"""
    name = path.name
    if name.startswith(SKIP_VALIDATION_PREFIXES):
        return True
    if name in SKIP_VALIDATION_FILES:
        return True
    rel = path.relative_to(root).as_posix()
    if rel.startswith("logs/"):
        return True
    return False


def validate_file(path: Path, filename_index: dict[str, list[Path]]) -> list[str]:
    """返回该文件的错误列表（空列表表示通过）。"""
    errors: list[str] = []
    root = get_root()
    text = path.read_text(encoding="utf-8")

    if is_skippable_file(path, root):
        return errors

    fields, err = parse_front_matter(text)
    if fields is None:
        errors.append(f"[frontmatter] {err}")
        return errors

    ftype = fields.get("type")
    if ftype is None:
        errors.append("[required] 缺失必填字段：type")
    elif ftype not in VALID_TYPES:
        errors.append(f"[type] 非法 type 值：{ftype!r}，合法值：{sorted(VALID_TYPES)}")

    missing = [k for k in REQUIRED_FIELDS if k not in fields or fields.get(k) in (None, "", [])]
    if missing:
        errors.append(f"[required] 缺失必填字段：{missing}")

    tags = fields.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors.append("[tags] 不是数组格式")
        elif len(tags) < 1:
            errors.append("[tags] 至少需要 1 个标签")

    for key in DATE_FIELDS:
        if key in fields:
            val = fields[key]
            if isinstance(val, str) and not DATE_RE.match(val):
                errors.append(f"[date] {key}={val!r} 不符合 YYYY-MM-DD 格式")

    h1_match = HEADING1_RE.search(text)
    if not h1_match:
        errors.append("[heading] 缺少 H1 标题")
    else:
        after_h1 = text[h1_match.end():]
        next_heading = re.search(r"^#{1,6} ", after_h1, re.MULTILINE)
        summary_area = after_h1[:next_heading.start()] if next_heading else after_h1[:500]
        if not SUMMARY_RE.search(summary_area):
            errors.append("[summary] H1 下方缺少 ✍️ 摘要")

    cleaned_text = re.sub(r"```.*?```", "", text, flags=re.S)
    cleaned_text = re.sub(r"`[^`]*`", "", cleaned_text)
    seen_links: set[str] = set()
    for link in WIKI_LINK_RE.findall(cleaned_text):
        if link in seen_links:
            continue
        seen_links.add(link)
        name = link.split("|")[0].split("#")[0].strip()
        if not name:
            continue
        if resolve_wiki_link(link, path, filename_index) is None:
            errors.append(f"[wikilink] 双链目标不存在：[[{link}]]")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="LeoDiary 知识库校验（轻量标准）")
    parser.add_argument("vault", help="知识库路径")
    parser.add_argument("--quiet", action="store_true", help="只打印错误，不打印 OK 的文件")
    args = parser.parse_args()

    set_root(args.vault)
    root = get_root()

    md_files = find_md_files(root)
    if not md_files:
        print("未找到任何 .md 文件", file=sys.stderr)
        return 1

    all_md_files = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        all_md_files.append(path)
    full_filename_index = build_filename_index(all_md_files, root)

    total = 0
    failed = 0
    for path in md_files:
        if is_skippable_file(path, root):
            continue
        total += 1
        rel = path.relative_to(root).as_posix()
        errors = validate_file(path, full_filename_index)
        if errors:
            failed += 1
            try:
                print(f"[FAIL] {rel}")
            except UnicodeEncodeError:
                print(f"[FAIL] {rel.encode('ascii', errors='replace').decode('ascii')}")
            for e in errors:
                print(f"    {e}")
        else:
            if not args.quiet:
                try:
                    print(f"[PASS] {rel}")
                except UnicodeEncodeError:
                    print(f"[PASS] {rel.encode('ascii', errors='replace').decode('ascii')}")

    print()
    print(f"总计 {total} 个文件，{failed} 个有问题，{total - failed} 个通过")

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

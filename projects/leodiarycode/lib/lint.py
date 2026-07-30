"""LeoDiary 知识库内容健康检查（lint）

与 validate.py 分工：
    validate.py 管元数据（front matter 格式、必填字段、id 前缀、双链存在性、版本一致性）
    lint.py 管内容健康（过时、孤儿、断链、矛盾标记、缺失交叉引用、双向链接完整性、内容矛盾）

借鉴 Karpathy LLM Wiki 的 lint 操作：检查矛盾、过时、孤儿、缺失页、缺失交叉引用。

用法：
    python lint.py <vault_path>            # 全量检查
    python lint.py <vault_path> --quiet    # 只打印有问题的项
    python lint.py <vault_path> --stale     # 只检查过时文件
    python lint.py <vault_path> --orphans   # 只检查孤儿文件
    python lint.py <vault_path> --broken    # 只检查断链
    python lint.py <vault_path> --conflicts # 只检查矛盾标记
    python lint.py <vault_path> --missing   # 只检查缺失交叉引用
    python lint.py <vault_path> --backlinks # 只检查双向链接完整性
    python lint.py <vault_path> --content-conflicts  # 只检查内容矛盾

退出码：
    0 — 无问题
    1 — 有问题（注意：孤儿和缺失交叉引用只警告，不算失败）
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leo_common import (  # noqa: E402
    set_root,
    get_root,
    SKIP_DIRS,
    SKIP_FILENAMES,
    WIKI_LINK_RE,
    parse_front_matter,
    find_md_files,
    build_filename_index,
    resolve_wiki_link,
)


STALE_THRESHOLD_DAYS = 180


def check_stale(md_files: list[Path]) -> list[str]:
    """检查 updated 字段距今超过 6 个月的文件。"""
    root = get_root()
    today = date.today()
    threshold = today - timedelta(days=STALE_THRESHOLD_DAYS)
    warnings: list[str] = []

    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is None:
            continue
        updated = fields.get("updated")
        if not isinstance(updated, str):
            continue
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", updated)
        if not m:
            continue
        try:
            updated_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if updated_date < threshold:
            days_ago = (today - updated_date).days
            warnings.append(
                f"[stale] {rel} updated={updated}（距今 {days_ago} 天，超过 {STALE_THRESHOLD_DAYS} 天阈值）"
            )
    return warnings


ORPHAN_SKIP_TYPES = {"core"}


def check_orphans(md_files: list[Path], filename_index: dict[str, list[Path]]) -> list[str]:
    """检测无任何反向引用的知识库/思维框架文件。"""
    root = get_root()
    referenced: set[str] = set()
    all_md_files = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name == "README.md":
            continue
        all_md_files.append(path)

    all_index = build_filename_index(all_md_files, root)

    for path in all_md_files:
        text = path.read_text(encoding="utf-8")
        cleaned = re.sub(r"```.*?```", "", text, flags=re.S)
        cleaned = re.sub(r"`[^`]*`", "", cleaned)
        for match in WIKI_LINK_RE.finditer(cleaned):
            link = match.group(1)
            target = resolve_wiki_link(link, path, all_index)
            if target:
                referenced.add(target.resolve().as_posix())

    warnings: list[str] = []
    for path in md_files:
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        # 跳过已归档文件（processed-* 目录下的文件无反向引用是正常的）
        if "D📦 归档（Archive）/processed-" in rel_posix:
            continue
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is None:
            continue
        ftype = str(fields.get("type", ""))
        if ftype in ORPHAN_SKIP_TYPES:
            continue
        resolved = path.resolve().as_posix()
        if resolved not in referenced:
            warnings.append(f"[orphan] 无反向引用：{rel_posix}")
    return warnings


def check_broken_links(md_files: list[Path], filename_index: dict[str, list[Path]]) -> list[str]:
    """检测 [[双链]] 目标文件不存在的情况。"""
    root = get_root()
    errors: list[str] = []
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        cleaned = re.sub(r"```.*?```", "", text, flags=re.S)
        seen_in_file: set[str] = set()
        for match in WIKI_LINK_RE.finditer(cleaned):
            link = match.group(1)
            name = link.split("|")[0].split("#")[0].strip()
            if not name:
                continue
            if name in seen_in_file:
                continue
            seen_in_file.add(name)
            # 跳过模板/示例链接
            if name in {"xxx", "yyy", "zzz", "...", "文件名", "UNIVERSAL", "wikilink"}:
                continue
            if name.startswith("home-xxx") or "home-xxx" in name:
                continue
            target = resolve_wiki_link(link, path, filename_index)
            if target is None:
                errors.append(f"[broken] {rel}: [[{link}]] 目标不存在")
    return errors


CONFLICT_MARK_RE = re.compile(r"⚠\s*矛盾提示[：:]")
TEMPLATE_PLACEHOLDER_RE = re.compile(r"\[\[新条目\]\]|\{简述差异\}|\{类型\}")
CODE_FENCE_RE = re.compile(r"^```")


def check_conflicts(md_files: list[Path]) -> list[str]:
    """检测文件中已有的矛盾标记。"""
    root = get_root()
    warnings: list[str] = []
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if not CONFLICT_MARK_RE.search(text):
            continue
        in_code_block = False
        for line in text.splitlines():
            if CODE_FENCE_RE.match(line.strip()):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if not CONFLICT_MARK_RE.search(line):
                continue
            if TEMPLATE_PLACEHOLDER_RE.search(line):
                continue
            warnings.append(f"[conflict] {rel}: {line.strip()[:120]}")
    return warnings


TAG_OVERLAP_THRESHOLD = 2


def _parse_tags(fields: dict[str, Any]) -> set[str]:
    tags = fields.get("tags")
    if tags is None:
        return set()
    if isinstance(tags, list):
        return {str(t).strip() for t in tags if str(t).strip()}
    if isinstance(tags, str):
        return {t.strip() for t in tags.split(",") if t.strip()}
    return set()


def _parse_related_stems(fields: dict[str, Any]) -> set[str]:
    related = fields.get("related")
    if related is None:
        return set()
    if isinstance(related, list):
        items = related
    elif isinstance(related, str):
        items = [related]
    else:
        return set()
    stems: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        for link in WIKI_LINK_RE.findall(item):
            name = link.split("|")[0].split("#")[0].strip()
            if "/" in name or "\\" in name:
                name = name.replace("\\", "/").split("/")[-1]
            stem = name[:-3] if name.endswith(".md") else name
            stems.add(stem)
    return stems


def check_backlinks(md_files: list[Path]) -> list[str]:
    """检测双向链接是否完整：A 链接 B，但 B 没有反向链接 A。"""
    root = get_root()
    stem_to_path: dict[str, Path] = {}
    stem_to_related: dict[str, set[str]] = {}

    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is None:
            continue
        ftype = str(fields.get("type", ""))
        if ftype == "core":
            continue
        stem = path.stem
        stem_to_path[stem] = path
        stem_to_related[stem] = _parse_related_stems(fields)

    warnings: list[str] = []
    for stem, path in stem_to_path.items():
        rel = path.relative_to(root).as_posix()
        for target_stem in stem_to_related.get(stem, set()):
            if target_stem not in stem_to_path:
                continue
            target_path = stem_to_path[target_stem]
            target_rel = target_path.relative_to(root).as_posix()
            if stem not in stem_to_related.get(target_stem, set()):
                warnings.append(
                    f"[missing-backlink] {rel} → {target_rel}（{target_rel} 的 related 字段缺少 [[{stem}]]）"
                )
    return warnings


CONFLICT_KEYWORDS = {
    ("违约金过高", "违约金合理"),
    ("支持原告", "驳回原告诉请"),
    ("适用", "不适用"),
    ("有效", "无效"),
    ("应当", "不应"),
    ("必须", "无需"),
    ("属于", "不属于"),
    ("符合", "不符合"),
}


def check_content_conflicts(md_files: list[Path]) -> list[str]:
    """检测内容层面的新矛盾。"""
    root = get_root()
    verified_files: set[str] = set()
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is not None and fields.get("verified_conflicts") is True:
            verified_files.add(rel)

    concept_groups: dict[str, list[tuple[Path, str, dict[str, Any]]]] = {}

    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is None:
            continue
        ftype = str(fields.get("type", ""))
        if ftype not in {"case", "pattern", "faq", "glossary", "best-practice", "knowledge"}:
            continue
        title = str(fields.get("title", path.stem))
        for keyword in ["违约金", "租赁合同", "维修义务", "解除", "违约", "赔偿"]:
            if keyword in title:
                concept_groups.setdefault(keyword, []).append((path, rel, fields))
                break
        else:
            first_char = title[0] if title else ""
            concept_groups.setdefault(first_char, []).append((path, rel, fields))

    warnings: list[str] = []

    for keyword, files in concept_groups.items():
        if len(files) < 2:
            continue
        contents = []
        for path, rel, fields in files:
            text = path.read_text(encoding="utf-8")
            contents.append((rel, text))
        for i, (rel1, text1) in enumerate(contents):
            for j in range(i + 1, len(contents)):
                rel2, text2 = contents[j]
                if rel1 in verified_files and rel2 in verified_files:
                    continue
                for positive, negative in CONFLICT_KEYWORDS:
                    has_positive = positive in text1 and negative in text2
                    has_negative = negative in text1 and positive in text2
                    if has_positive or has_negative:
                        warnings.append(
                            f"[content-conflict] {rel1} 与 {rel2} 可能存在冲突（'{positive}' vs '{negative}'），建议复核"
                        )

    for keyword, files in concept_groups.items():
        if len(files) < 2:
            continue
        dates = []
        for path, rel, fields in files:
            updated = fields.get("updated")
            if isinstance(updated, str):
                m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", updated)
                if m:
                    try:
                        dates.append((rel, int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3))))
                    except ValueError:
                        pass
        if len(dates) >= 2:
            dates.sort(key=lambda x: x[1])
            oldest, newest = dates[0], dates[-1]
            if newest[1] - oldest[1] > 100:
                warnings.append(
                    f"[date-gap] {oldest[0]}（{oldest[1]}）与 {newest[0]}（{newest[1]}）日期差距较大，可能存在信息过时，建议复核"
                )

    return warnings


def check_missing_crossrefs(md_files: list[Path]) -> list[str]:
    """检测 tags 高度重合但 related 字段未互相引用的文件对。"""
    root = get_root()
    file_info: list[dict[str, Any]] = []
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_front_matter(text)
        if fields is None:
            continue
        ftype = str(fields.get("type", ""))
        if ftype not in {"case", "pattern", "faq", "glossary", "best-practice", "knowledge"}:
            continue
        tags = _parse_tags(fields)
        if not tags:
            continue
        file_info.append({
            "path": path,
            "rel": rel,
            "stem": path.stem,
            "tags": tags,
            "related_stems": _parse_related_stems(fields),
        })

    warnings: list[str] = []
    for i, a in enumerate(file_info):
        for b in file_info[i + 1:]:
            common = a["tags"] & b["tags"]
            if len(common) < TAG_OVERLAP_THRESHOLD:
                continue
            a_refs_b = b["stem"] in a["related_stems"]
            b_refs_a = a["stem"] in b["related_stems"]
            if a_refs_b and b_refs_a:
                continue
            if a_refs_b or b_refs_a:
                continue
            warnings.append(
                f"[missing-xref] {a['rel']} ↔ {b['rel']}（共享 tags: {sorted(common)}，建议互相添加 related 链接）"
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="LeoDiary 知识库内容健康检查")
    parser.add_argument("vault", help="知识库路径")
    parser.add_argument("--quiet", action="store_true", help="只打印有问题的项，不打印通过项")
    parser.add_argument("--stale", action="store_true", help="只检查过时文件")
    parser.add_argument("--orphans", action="store_true", help="只检查孤儿文件")
    parser.add_argument("--broken", action="store_true", help="只检查断链")
    parser.add_argument("--conflicts", action="store_true", help="只检查矛盾标记")
    parser.add_argument("--missing", action="store_true", help="只检查缺失交叉引用")
    parser.add_argument("--backlinks", action="store_true", help="只检查双向链接完整性")
    parser.add_argument("--content-conflicts", action="store_true", help="只检查内容矛盾")
    args = parser.parse_args()

    set_root(args.vault)
    root = get_root()

    single_mode = args.stale or args.orphans or args.broken or args.conflicts or args.missing or args.backlinks or args.content_conflicts

    md_files = find_md_files(root)

    all_md_files = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        all_md_files.append(path)
    full_filename_index = build_filename_index(all_md_files, root)

    total_issues = 0
    errors_count = 0
    warnings_count = 0

    def run_check(name: str, fn, *args_list) -> None:
        nonlocal total_issues, errors_count, warnings_count
        results = fn(*args_list)
        if not results:
            if not args.quiet and not single_mode:
                print(f"[PASS] {name}")
            return
        total_issues += len(results)
        if name in ("断链检测", "矛盾标记检测"):
            errors_count += len(results)
        else:
            warnings_count += len(results)
        print(f"\n{name}（{len(results)} 项）：")
        for msg in results:
            print(f"  {msg}")

    print(f"扫描 {len(md_files)} 个 .md 文件\n")

    if not single_mode or args.stale:
        run_check("过时检测", check_stale, md_files)
    if not single_mode or args.orphans:
        run_check("孤儿页检测", check_orphans, md_files, full_filename_index)
    if not single_mode or args.broken:
        run_check("断链检测", check_broken_links, md_files, full_filename_index)
    if not single_mode or args.conflicts:
        run_check("矛盾标记检测", check_conflicts, md_files)
    if not single_mode or args.missing:
        run_check("缺失交叉引用检测", check_missing_crossrefs, md_files)
    if not single_mode or args.backlinks:
        run_check("双向链接完整性检测", check_backlinks, md_files)
    if not single_mode or args.content_conflicts:
        run_check("内容矛盾检测", check_content_conflicts, md_files)

    print()
    print(f"总计：{total_issues} 项问题（{errors_count} 错误 / {warnings_count} 警告）")
    print(f"  - 断链和矛盾标记算错误（exit 1）")
    print(f"  - 过时/孤儿/缺失交叉引用/双向链接/内容矛盾只警告（不计失败）")

    if not single_mode and not args.quiet:
        print()
        print("AI 补充检查（需 AI 主动判断，脚本无法自动检测）：")
        print("  - 重要概念被多次提到但缺少自己的页面？→ 建议创建概念页")
        print("  - 有可以通过 web search 填补的数据空白？→ 建议外部搜索补全")
        print("  - 建议新的问题和新的源（LLM 擅长发现知识空白）")

    if errors_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

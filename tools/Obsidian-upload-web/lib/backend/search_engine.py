# -*- coding: utf-8 -*-
"""工作区内容搜索：遍历工作区文件 + 增量匹配（V1.1）。

职责：
- search(roots, keyword, cfg, limit=100)：在工作区范围内搜索关键字
- 逐文件逐行匹配（不整文件载入内存），超过 MAX_FILE_SIZE 的文件跳过内容搜索
- 扩展名过滤：config.json 的 search_exts（默认 .md/.txt/.py/.js/.json/.yaml/.yml）
- 文件名命中也作为结果（kind="filename"，line_no=0）
- 内容命中返回 行号 + 匹配行内容（kind="content"）
- 搜索选项（V1.1 新增，均默认关闭保持旧行为）：
  - match_case=True：区分字母大小写（默认不区分）
  - regex=True：keyword 作为正则表达式匹配（非法正则返回 ("error", 消息)）
  - whole_word=True：只匹配完整单词（\b 边界，对文件名 base 同样生效）
- 结果按遍历顺序返回

结果项：
{path, name, line_no, line, kind}

错误返回约定：
search() 返回 (结果列表, None)；正则编译失败返回 (None, 错误消息)。
"""
import os
import re

from lib.modules import file_tree

DEFAULT_LIMIT = 100
MAX_LINE_PREVIEW = 200


def _compile(kw, match_case, regex, whole_word):
    """构造匹配用正则。返回 (pattern, err)；err 非 None 表示编译失败。"""
    flags = 0 if match_case else re.IGNORECASE
    try:
        if regex:
            source = kw
        else:
            source = re.escape(kw)
        if whole_word:
            source = r"\b(?:%s)\b" % source
        return re.compile(source, flags), None
    except re.error as e:
        return None, "正则表达式无效：%s" % e


def search(roots, keyword, cfg, limit=DEFAULT_LIMIT,
           match_case=False, regex=False, whole_word=False):
    """在 roots（工作区文件夹列表）内搜索 keyword。

    roots 为空或 keyword 为空时返回空列表。
    返回 (results, None) 或 (None, err_msg)。
    """
    kw = (keyword or "").strip()
    if not kw or not roots:
        return [], None
    if limit is None or limit <= 0:
        limit = DEFAULT_LIMIT
    pattern, err = _compile(kw, match_case, regex, whole_word)
    if err is not None:
        return None, err
    results = []
    count = 0
    # 搜索范围 = search_exts ∪ explorer_exts，保证资源管理器中可见的文件都可被搜索到
    exts = set(file_tree.search_exts(cfg)) | set(file_tree.explorer_exts(cfg))
    for path in file_tree.iter_files(roots, cfg, exts=exts):
        name = os.path.basename(path)
        base = os.path.splitext(name)[0]
        # 1) 文件名命中
        if pattern.search(base):
            results.append({
                "path": path, "name": name,
                "line_no": 0, "line": "", "kind": "filename",
            })
            count += 1
            if count >= limit:
                return results, None
        # 2) 内容命中（逐行增量匹配，不整文件载入内存）
        try:
            if os.path.getsize(path) > file_tree.MAX_FILE_SIZE:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, ln in enumerate(f, 1):
                    if pattern.search(ln):
                        results.append({
                            "path": path, "name": name,
                            "line_no": i,
                            "line": ln.rstrip("\n")[:MAX_LINE_PREVIEW],
                            "kind": "content",
                        })
                        count += 1
                        if count >= limit:
                            return results, None
        except Exception:
            continue
    return results, None


def search_folder(root, keyword, cfg, limit=DEFAULT_LIMIT,
                  match_case=False, regex=False, whole_word=False):
    """对单个文件夹搜索（roots 包装）。"""
    return search([root], keyword, cfg, limit,
                  match_case=match_case, regex=regex, whole_word=whole_word)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    kw = sys.argv[2] if len(sys.argv) > 2 else "TODO"
    results, err = search([root], kw, {})
    if err:
        print("ERROR:", err)
    else:
        for r in results:
            print("%s:%s  %s" % (r["name"], r["line_no"], r["line"][:60]))


def search_folder(root, keyword, cfg, limit=DEFAULT_LIMIT):
    """对单个文件夹搜索（roots 包装）。"""
    return search([root], keyword, cfg, limit)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    kw = sys.argv[2] if len(sys.argv) > 2 else "TODO"
    for r in search([root], kw, {}):
        print("%s:%s  %s" % (r["name"], r["line_no"], r["line"][:60]))

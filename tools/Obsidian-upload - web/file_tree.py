# -*- coding: utf-8 -*-
"""文件树：目录懒加载扫描 + 隐藏规则过滤（V1.0）。

职责：
- scan_dir(path, cfg)：返回指定目录的直接子项（不递归，前端展开目录时再扫描）
- iter_files(roots, cfg)：递归遍历工作区文件（供搜索模块使用，逐文件 yield）
- 隐藏目录规则：config.json 的 workspace_hidden_dirs（内置默认见 DEFAULT_HIDDEN_DIRS）
- 搜索扩展名过滤：config.json 的 search_exts（内置默认见 DEFAULT_SEARCH_EXTS）

设计原则：
- 懒加载：一次只扫描一层目录，避免把整个工作区一次性载入内存
- 不依赖 UI / 网络，可独立测试
"""
import os

DEFAULT_HIDDEN_DIRS = [".git", "node_modules", "__pycache__", "dist", ".obsidian", ".trash"]
DEFAULT_SEARCH_EXTS = [".md", ".txt", ".py", ".js", ".json", ".yaml", ".yml"]
DEFAULT_EXPLORER_EXTS = [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"]

MAX_FILE_SIZE = 2 * 1024 * 1024   # 2MB 以上文件不参与内容搜索


def _cfg_list(cfg, key, default):
    if isinstance(cfg, dict):
        v = cfg.get(key)
        if isinstance(v, list):
            return [str(x) for x in v if x]
    return list(default)


def hidden_dirs(cfg):
    """返回隐藏目录名列表（小写）。"""
    return [d.strip().lower() for d in _cfg_list(cfg, "workspace_hidden_dirs", DEFAULT_HIDDEN_DIRS)
            if d and d.strip()]


def search_exts(cfg):
    """返回参与内容搜索的扩展名列表（小写，含点）。"""
    exts = []
    for e in _cfg_list(cfg, "search_exts", DEFAULT_SEARCH_EXTS):
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        exts.append(e)
    return exts


def explorer_exts(cfg):
    """返回资源管理器文件树显示的扩展名列表（小写，含点）。"""
    exts = []
    for e in _cfg_list(cfg, "explorer_exts", DEFAULT_EXPLORER_EXTS):
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        exts.append(e)
    return exts


def is_hidden_dir(name, cfg):
    name = name.strip()
    return bool(name) and name.lower() in set(hidden_dirs(cfg))


def scan_dir(path, cfg, sort="name"):
    """扫描目录 path 的直接子项。

    返回 [{name, path, type, ext, mtime}]，目录在前，均跳过隐藏目录。
    文件按 config.json 的 explorer_exts 过滤（只显示支持的文件类型，默认见
    DEFAULT_EXPLORER_EXTS：.md/.txt/.ini/.json/.yaml/.yml/.tsc）。
    type: "dir" | "file"
    ext: 小写无点扩展名（目录为 ""）。
    mtime: 最近修改时间（os.path.getmtime，读取失败为 0）。

    sort:
      "name"  名称排序（目录在前，目录/文件各自按名 A-Z）——兼容旧行为
      "time"  最近修改时间倒序（目录/文件各自，最新在前）——资源管理器默认
    """
    if not path or not os.path.isdir(path):
        return []
    dirs, files = [], []
    exts = set(explorer_exts(cfg))
    try:
        entries = os.listdir(path)
    except Exception:
        return []
    for name in entries:
        full = os.path.join(path, name)
        try:
            is_dir = os.path.isdir(full)
        except Exception:
            continue
        try:
            mtime = os.path.getmtime(full)
        except Exception:
            mtime = 0.0
        if is_dir:
            if not is_hidden_dir(name, cfg):
                dirs.append({"name": name, "path": full, "type": "dir", "ext": "", "mtime": mtime})
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in exts:
            continue
        files.append({
            "name": name,
            "path": full,
            "type": "file",
            "ext": ext.lstrip("."),
            "mtime": mtime,
        })
    if sort == "time":
        dirs.sort(key=lambda x: x["mtime"], reverse=True)
        files.sort(key=lambda x: x["mtime"], reverse=True)
    else:
        dirs.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())
    return dirs + files


def iter_files(roots, cfg, limit=None, exts=None):
    """递归遍历工作区文件，逐个 yield 文件路径。

    跳过隐藏目录；扩展名过滤默认使用 search_exts，也可由调用方传入 exts。
    limit 限制遍历文件总数。
    """
    if exts is None:
        exts = set(search_exts(cfg))
    else:
        exts = set(exts)
    count = 0
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not is_hidden_dir(d, cfg)]
            dirnames.sort(key=str.lower)
            for name in sorted(filenames, key=str.lower):
                ext = os.path.splitext(name)[1].lower()
                if ext not in exts:
                    continue
                full = os.path.join(dirpath, name)
                count += 1
                if limit is not None and count > limit:
                    return
                yield full


def iter_dirs(roots, cfg):
    """递归遍历工作区目录（跳过隐藏目录），逐个 yield 目录绝对路径（去重）。"""
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, _ in os.walk(root):
            dirnames[:] = [d for d in dirnames if not is_hidden_dir(d, cfg)]
            dirnames.sort(key=str.lower)
            key = os.path.normcase(os.path.normpath(dirpath))
            if key in seen:
                continue
            seen.add(key)
            yield dirpath


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "."
    for it in scan_dir(p, {}):
        print(it["type"], it["name"])

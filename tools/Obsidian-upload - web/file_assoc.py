# -*- coding: utf-8 -*-
"""文件关联：支持通过 Windows 文件关联直接打开常见文本文件（V1.0）。

职责（单一职责，不含 UI / 窗口 / 保存逻辑）：
- 受支持扩展名统一配置：config.json 的 associated_exts（缺省用内置默认）
- 启动参数过滤：从 sys.argv 中提取存在且扩展名受支持的文件绝对路径
- 跨进程待打开文件传递（pending_open.txt）：新实例带文件参数启动时，
  若旧实例已在运行，先把文件写入 pending 队列，由旧实例轮询消费打开
- 读取文件内容并计算页签标题：第一行非空用第一行，否则用文件名

后续扩展新文本格式只需改 config.json 的 associated_exts，无需改本模块。
"""
import os
import threading

APP_DIR = "Obsidian-upload"

# 内置默认受支持扩展名（config.json 的 associated_exts 可覆盖/扩展）
DEFAULT_EXTS = [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"]

_lock = threading.Lock()


def supported_exts(cfg=None):
    """返回受支持扩展名列表（统一小写、含点）。"""
    raw = (cfg or {}).get("associated_exts") or DEFAULT_EXTS
    normalized = []
    for e in raw:
        s = str(e).strip().lower()
        if not s:
            continue
        if not s.startswith("."):
            s = "." + s
        if s not in normalized:
            normalized.append(s)
    return normalized or list(DEFAULT_EXTS)


def is_supported(path, cfg=None):
    """判断文件扩展名是否受支持。"""
    return os.path.splitext(path)[1].lower() in supported_exts(cfg)


def filter_file_args(args, cfg=None):
    """从启动参数中提取存在且受支持的文本文件绝对路径列表（跳过 - 开头参数）。"""
    exts = supported_exts(cfg)
    out = []
    for a in args or []:
        s = str(a).strip()
        if not s or s.startswith("-"):
            continue
        p = os.path.abspath(s)
        if os.path.isfile(p) and os.path.splitext(p)[1].lower() in exts:
            out.append(p)
    return out


def pending_path():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        APP_DIR, "pending_open.txt")


def _read_lines():
    if not os.path.exists(pending_path()):
        return []
    try:
        with open(pending_path(), "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


def _atomic_write(lines):
    """先写唯一 tmp 文件再 os.replace，保证跨进程读写不会出现半截内容。"""
    tmp = "%s.%d.tmp" % (pending_path(), os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, pending_path())


def enqueue_pending(paths):
    """把待打开文件路径追加到 pending 队列（去重），供运行中的实例消费。"""
    with _lock:
        try:
            combined = _read_lines() + [p for p in paths or [] if p]
            seen, unique = set(), []
            for p in combined:
                if p not in seen:
                    seen.add(p)
                    unique.append(p)
            os.makedirs(os.path.dirname(pending_path()), exist_ok=True)
            _atomic_write(unique)
            return True
        except Exception:
            return False


def take_pending_files():
    """读取并清空 pending 队列，返回待打开文件路径列表。"""
    with _lock:
        try:
            if not os.path.exists(pending_path()):
                return []
            paths = _read_lines()
            _atomic_write([])
            return paths
        except Exception:
            return []


def read_external_files(paths):
    """读取文件内容，返回 [{path, title, content}]（读取失败项跳过）。"""
    results = []
    for p in paths or []:
        try:
            if not os.path.isfile(p):
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            results.append({"path": p, "title": title_for_file(p, content),
                            "content": content})
        except Exception:
            continue
    return results


def title_for_file(path, content):
    """页签标题：第一行非空用第一行（截断到 80 字符），否则用文件名。"""
    first = ""
    for line in (content or "").splitlines():
        if line.strip():
            first = line.strip()
            break
    if first:
        return first[:80]
    base = os.path.basename(path)
    return os.path.splitext(base)[0] or base

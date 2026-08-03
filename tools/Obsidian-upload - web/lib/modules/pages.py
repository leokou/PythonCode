# -*- coding: utf-8 -*-
"""页面持久化：pages.json 元数据 + 每个 Tab 独立 Markdown 文件管理。

pages.json 位于 %APPDATA%\\Obsidian-upload\\pages.json，记录每个页面（Tab）的
id / 窗口类型 / 标题 / 文件路径 / 创建更新时间 / 保存状态，用于启动恢复与关闭保护。

自动保存为「覆盖写入」（不追加），与 storage.py 的聚合追加逻辑互不干扰：
- Tab 文件：实时编辑缓存、防丢失文件（覆盖写）。
- 聚合文件（My-Inbox.md / FlashNote.md / 日志）：历史记录日志（追加）。

性能优化（V1.1）：内存缓存 + 延迟写盘
- _db 内存缓存：首次访问时加载，后续 find_page/load_pages 直接读缓存（零 IO）
- update_page 延迟写盘（2 秒 debounce）：频繁的元数据更新合并写盘
- add_page/remove_page 立即写盘：页面数量变化是关键操作，不允许丢失
- flush()：退出时立即落盘（main.py exit_app 调用）
"""
import json
import os
import re
import threading
from datetime import datetime

APP_DIR = "Obsidian-upload"

# 多窗口（inbox/flash/log）的自动保存线程会并发读写 pages.json，
# 必须用同一把锁串行化「读-改-写」，否则互相覆盖导致页面记录丢失。
_lock = threading.RLock()

# 内存缓存：None = 未加载；list = 已加载
_db = None
_dirty = False
_timer = None           # debounce 写盘 timer
WRITE_DEBOUNCE = 2.0    # 元数据更新后延迟写盘秒数


def appdata_dir():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), APP_DIR)


def pages_path():
    return os.path.join(appdata_dir(), "pages.json")


def _ensure_loaded():
    """首次访问时从磁盘加载缓存（后续不再读盘）。"""
    global _db
    if _db is None:
        _load()


def _load():
    """从磁盘加载 pages.json 到内存缓存。"""
    global _db
    _db = []
    try:
        with open(pages_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        pages = data.get("pages") if isinstance(data, dict) else data
        if isinstance(pages, list):
            _db = pages
    except Exception:
        _db = []


def _persist():
    """把内存缓存立即写入磁盘（原子写：临时文件 + 替换）。"""
    try:
        os.makedirs(appdata_dir(), exist_ok=True)
        tmp = pages_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pages": list(_db)}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, pages_path())
        return True
    except Exception:
        return False


def _schedule_save():
    """调度延迟写盘（2 秒 debounce），合并频繁的元数据更新。"""
    global _dirty, _timer
    _dirty = True
    if _timer is None:
        _timer = threading.Timer(WRITE_DEBOUNCE, _save_now)
        _timer.daemon = True
        _timer.start()


def _save_now():
    """debounce 触发：把脏数据落盘。"""
    global _dirty, _timer
    with _lock:
        _timer = None
        if not _dirty:
            return
        _dirty = False
        _persist()


def flush():
    """立即落盘并取消未执行的 debounce（程序退出时调用）。"""
    global _timer
    with _lock:
        if _timer is not None:
            try:
                _timer.cancel()
            except Exception:
                pass
            _timer = None
        if _dirty:
            _dirty = False
            _persist()


def load_pages():
    """读取 pages.json，返回页面列表（副本，从内存缓存读取）。

    首次调用时从磁盘加载到 _db 缓存，后续直接返回缓存副本（零磁盘 IO）。
    """
    with _lock:
        _ensure_loaded()
        return [dict(p) for p in _db]


def save_pages(pages):
    """整体写入 pages.json（更新缓存 + 立即落盘），返回是否成功。

    原子写：先写临时文件再替换，避免并发/崩溃时留下半截 JSON。
    """
    with _lock:
        _ensure_loaded()
        _db[:] = list(pages)
        return _persist()


def add_page(page):
    """原子追加一条页面记录并立即落盘（页面数量变化是关键操作）。"""
    with _lock:
        _ensure_loaded()
        _db[:] = [p for p in _db if p.get("id") != page.get("id")]
        _db.append(dict(page))
        _persist()


def find_page(page_id):
    """从内存缓存查找页面，返回副本（零磁盘 IO）。"""
    with _lock:
        _ensure_loaded()
        for p in _db:
            if p.get("id") == page_id:
                return dict(p)
        return None


def update_page(page_id, **kwargs):
    """更新单条页面字段，延迟写盘（2 秒 debounce，合并频繁元数据更新）。

    Tab 文件内容不受此函数影响——write_page_file 会立即写 Tab 文件，
    此处只更新 pages.json 中的元数据（时间戳/状态），允许短暂延迟。
    """
    with _lock:
        _ensure_loaded()
        for p in _db:
            if p.get("id") == page_id:
                p.update(kwargs)
                break
        _schedule_save()


def remove_page(page_id):
    """从 pages.json 移除一条页面并立即落盘（页面数量变化是关键操作）。"""
    with _lock:
        _ensure_loaded()
        _db[:] = [p for p in _db if p.get("id") != page_id]
        _persist()


# 窗口类型 -> Tab 文件存放子目录
# （capture 的 Tab 目录特殊：与聚合文件同在 A📥 收集（Capture），由 main.py _tab_dir 单独解析）
WINDOW_DIRS = {"inbox": "Inbox", "flash": "FlashNote", "log": "Log"}


def tab_subdir(window_type):
    return WINDOW_DIRS.get(window_type, "Inbox")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def untitled_name():
    return "Untitled-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def sanitize_filename(title):
    """把标题清洗为 Windows 合法文件名（去非法字符、收尾点空格、限长）。

    保留中文/emoji/空格，非法字符替换为空，Windows 保留名加前缀 _。
    """
    s = (title or "").strip()
    if not s:
        return ""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if not s:
        return ""
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved |= {"COM%d" % i for i in range(1, 10)}
    reserved |= {"LPT%d" % i for i in range(1, 10)}
    if s.split(".")[0].upper() in reserved:
        s = "_" + s
    return s[:80]


def unique_file(dirpath, base, ext=".md"):
    """返回不冲突的文件路径：已存在则在名称后追加 (n)。"""
    path = os.path.join(dirpath, base + ext)
    if not os.path.exists(path):
        return path
    n = 2
    while True:
        cand = os.path.join(dirpath, "%s (%d)%s" % (base, n, ext))
        if not os.path.exists(cand):
            return cand
        n += 1


def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False


def write_page_file(page_id, content):
    """按 page_id 覆盖写入 Tab 文件内容（自动建目录）。

    更新 pages.json 的 updated / status 并返回文件路径；页面不存在返回 None。
    """
    with _lock:
        page = find_page(page_id)
        if not page:
            return None
        path = page.get("file", "")
        if not path:
            return None
        ensure_dir(os.path.dirname(path))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            update_page(page_id, updated=now_str(), status="saved")
            return path
        except Exception:
            return None


def migrate_page(page_id, new_dir):
    """把页面文件迁移到新目录（默认保存路径变更后），并更新 pages.json。

    返回迁移后的新文件路径；页面不存在返回 None；已在新目录则原样返回当前路径。
    """
    with _lock:
        page = find_page(page_id)
        if not page:
            return None
        old = page.get("file", "")
        if old and os.path.dirname(old) == os.path.normpath(new_dir):
            return old
        ensure_dir(new_dir)
        base = page.get("title") or os.path.splitext(os.path.basename(old))[0]
        base = sanitize_filename(base) or untitled_name()
        new = unique_file(new_dir, base)
        try:
            if old and os.path.exists(old):
                os.replace(old, new)
            else:
                open(new, "w", encoding="utf-8").close()
        except Exception:
            new = old  # 迁移失败则保持原路径
        update_page(page_id, file=new, updated=now_str(), status="saved")
        page["file"] = new
        return new

# -*- coding: utf-8 -*-
"""历史记录持久化：最近编辑/打开的文件记录。

数据文件：%APPDATA%/Obsidian-upload/history.json
结构：{"history": [{"name","path","type","created","last_edited","last_opened"}]}

职责：
- record_open(path)：打开文件时更新最近打开时间（不存在则创建）
- record_edit(path)：编辑/保存时更新最后编辑时间（不存在则创建）
- rename(old_path, new_path)：文件重命名后同步记录（迁移路径）
- remove(path)：文件删除后移除记录
- query(limit) / search(keyword, limit)：按最后编辑时间倒序返回
- 更新 debounce 合并写盘（默认 2 秒），flush() 立即落盘（退出时调用）
- 磁盘保留上限 MAX_SAVED(500)，查询默认返回最近 DEFAULT_LIMIT(100) 条
- 线程安全：多窗口自动保存线程并发调用，用 RLock 串行化

不依赖 UI / 网络，可独立测试。
"""
import json
import os
import threading
from datetime import datetime

APP_DIR = "Obsidian-upload"
MAX_SAVED = 500        # 磁盘保留上限
DEFAULT_LIMIT = 100    # 查询/搜索默认返回条数
WRITE_DEBOUNCE = 2.0   # 更新后延迟写盘秒数

_lock = threading.RLock()
_db = None               # normcase(path) -> record dict（None 表示未加载）
_dirty = False
_timer = None            # 单例 debounce 写盘 timer
_seq = 0                 # 单调序号：保证同一秒内后编辑的排前面


def appdata_dir():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), APP_DIR)


def history_path():
    return os.path.join(appdata_dir(), "history.json")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _key(path):
    return os.path.normcase(os.path.normpath(str(path or "")))


def _name_of(path):
    return os.path.basename(str(path or ""))


def _type_of(path):
    ext = os.path.splitext(str(path or ""))[1].lower().lstrip(".")
    return ext or "file"


def _new_record(path):
    ts = now_str()
    return {
        "name": _name_of(path),
        "path": os.path.normpath(str(path)),
        "type": _type_of(path),
        "created": ts,
        "last_edited": ts,
        "last_opened": ts,
        "seq": _next_seq(),
    }


def _next_seq():
    global _seq
    _seq += 1
    return _seq


def _load():
    """从磁盘加载历史记录（模块首次使用时执行）。"""
    global _db, _seq
    _db = {}
    max_seq = 0
    try:
        with open(history_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("history") if isinstance(data, dict) else data
        if isinstance(items, list):
            for rec in items:
                if isinstance(rec, dict) and rec.get("path"):
                    _db[_key(rec["path"])] = rec
                    try:
                        max_seq = max(max_seq, int(rec.get("seq", 0)))
                    except Exception:
                        pass
    except Exception:
        pass
    _seq = max_seq


def _ensure_loaded():
    if _db is None:
        _load()


def _mark_dirty():
    global _dirty, _timer
    _dirty = True
    if _timer is None:
        _timer = threading.Timer(WRITE_DEBOUNCE, _save_now)
        _timer.daemon = True
        _timer.start()


def _save_now():
    """把内存记录落盘（含裁剪到 MAX_SAVED）。"""
    global _dirty, _timer
    with _lock:
        _timer = None
        if not _dirty:
            return
        _dirty = False
        items = _sorted_records()[:MAX_SAVED]
        try:
            os.makedirs(appdata_dir(), exist_ok=True)
            tmp = history_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"history": items}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, history_path())
        except Exception:
            _dirty = True  # 写盘失败保留脏标记，等待下次


def flush():
    """立即落盘（程序退出时调用），并取消未执行的 debounce。"""
    global _timer
    with _lock:
        if _timer is not None:
            try:
                _timer.cancel()
            except Exception:
                pass
            _timer = None
        if _dirty:
            _save_now()


def record_open(path):
    """打开文件：更新最近打开时间（不存在则创建记录）。"""
    if not path:
        return
    _ensure_loaded()
    k = _key(path)
    with _lock:
        rec = _db.get(k)
        if rec is None:
            _db[k] = _new_record(path)
        else:
            rec["last_opened"] = now_str()
            rec["seq"] = _next_seq()
        _mark_dirty()


def record_edit(path):
    """编辑/保存文件：更新最后编辑时间（不存在则创建记录）。"""
    if not path:
        return
    _ensure_loaded()
    k = _key(path)
    with _lock:
        rec = _db.get(k)
        if rec is None:
            _db[k] = _new_record(path)
        else:
            rec["last_edited"] = now_str()
            rec["seq"] = _next_seq()
        _mark_dirty()


def _sorted_records():
    # 主排序：最后编辑时间倒序（同一时间分组内最新编辑的文件在最上）
    # 次排序：seq 单调递增（同秒内后编辑在前）；磁盘旧数据无 seq 时回退 last_opened
    return sorted(_db.values(),
                  key=lambda r: (r.get("last_edited", ""),
                                 r.get("seq", -1),
                                 r.get("last_opened", "")),
                  reverse=True)


def query(limit=None):
    """最近记录，按最后编辑时间倒序（其次最近打开时间）。"""
    _ensure_loaded()
    limit = DEFAULT_LIMIT if limit is None else int(limit or 0)
    with _lock:
        items = _sorted_records()
        return items[:limit] if limit > 0 else items


def search(keyword, limit=None):
    """按文件名称模糊搜索（不区分大小写），同样按时间倒序。"""
    _ensure_loaded()
    limit = DEFAULT_LIMIT if limit is None else int(limit or 0)
    kw = (keyword or "").strip().lower()
    with _lock:
        if not kw:
            return query(limit)
        items = [r for r in _sorted_records()
                 if kw in r.get("name", "").lower()]
        return items[:limit] if limit > 0 else items


def rename(old_path, new_path):
    """文件/文件夹重命名后同步历史记录：旧路径（含子路径）记录迁移到新路径。"""
    return move_path(old_path, new_path)


def remove(path):
    """删除文件后同步历史记录：移除该路径的记录。"""
    if not path:
        return
    _ensure_loaded()
    k = _key(path)
    with _lock:
        if _db.pop(k, None) is not None:
            _mark_dirty()


def remove_tree(path):
    """删除文件/文件夹后同步历史记录：移除该路径及其所有子路径的记录。"""
    if not path:
        return
    _ensure_loaded()
    k = _key(path)
    with _lock:
        keys = [pk for pk in _db if pk == k or pk.startswith(k + os.sep)]
        if not keys:
            return
        for pk in keys:
            _db.pop(pk, None)
        _mark_dirty()


def move_path(old_path, new_path):
    """文件/文件夹移动后同步历史记录：把 old_path 下（含自身）的所有记录
    迁移到 new_path 对应位置（更新 name / path / type / seq）。"""
    if not old_path or not new_path:
        return
    _ensure_loaded()
    old_n = os.path.normpath(old_path)
    new_n = os.path.normpath(new_path)
    if os.path.normcase(old_n) == os.path.normcase(new_n):
        return
    old_key = os.path.normcase(old_n)
    with _lock:
        moved = []
        for k, rec in list(_db.items()):
            p = str(rec.get("path") or "")
            if not p:
                continue
            pn = os.path.normpath(p)
            pk = os.path.normcase(pn)
            if pk == old_key or pk.startswith(old_key + os.sep):
                rel = os.path.relpath(pn, old_n)
                newp = os.path.normpath(os.path.join(new_n, rel))
                rec["name"] = _name_of(newp)
                rec["path"] = newp
                rec["type"] = _type_of(newp)
                rec["seq"] = _next_seq()
                _db[_key(newp)] = rec
                moved.append(k)
        for k in moved:
            _db.pop(k, None)
        if moved:
            _mark_dirty()


def clear():
    """清空全部内存记录（测试用），并立即落盘。"""
    global _dirty
    _ensure_loaded()
    with _lock:
        _db.clear()
        _dirty = True
        _save_now()

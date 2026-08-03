# -*- coding: utf-8 -*-
"""收藏夹管理：收藏文件列表 + favorites.json 持久化（V1.0）。

数据文件：%APPDATA%/Obsidian-upload/favorites.json
结构：{"items": [{"path", "name", "favorited_at", "order"}, ...]}
排序：order 越小越靠前；新收藏 order = 当前最小 order - 1（最新收藏排最前）。

职责：
- get_list()：返回收藏列表（按 order 排序）
- add(path)：添加收藏（去重，新收藏排最前）
- remove(path)：移除收藏
- move(path, direction)：上移/下移（direction: "up" / "down"，交换相邻 order）
- is_favorite(path)：判断是否已收藏
- clear()：清空（测试用）

线程安全：RLock。不依赖 UI / 网络，可独立测试。
"""
import json
import os
import threading
import time

APP_DIR = "Obsidian-upload"

_lock = threading.RLock()
_items = None   # None 表示未加载


def favorites_path():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        APP_DIR, "favorites.json")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load():
    global _items
    if _items is not None:
        return
    _items = []
    try:
        with open(favorites_path(), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        raw = data.get("items") if isinstance(data, dict) else None
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict) or not item.get("path"):
                    continue
                _items.append({
                    "path": str(item["path"]),
                    "name": str(item.get("name", "") or os.path.basename(item["path"].rstrip("\\/")) or item["path"]),
                    "favorited_at": str(item.get("favorited_at", "") or ""),
                    "order": int(item.get("order", 0) or 0),
                })
    except Exception:
        import sys
        print("favorites: 读取失败 %s" % (favorites_path()), file=sys.stderr)
        _items = []


def _save():
    try:
        path = favorites_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {"items": [dict(x) for x in _items]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _norm(path):
    return os.path.normcase(os.path.normpath(path))


def _find_index(path):
    n = _norm(path)
    for i, item in enumerate(_items):
        if _norm(item["path"]) == n:
            return i
    return -1


def get_list():
    """返回收藏列表（按 order 排序，最新收藏在前）。"""
    with _lock:
        _load()
        return sorted((dict(x) for x in _items), key=lambda x: x["order"])


def is_favorite(path):
    with _lock:
        _load()
        return _find_index(path) >= 0


def add(path):
    """添加收藏。返回 (ok, msg)。"""
    with _lock:
        _load()
        path = str(path or "").strip().strip('"')
        if not path:
            return False, "路径不能为空"
        if _find_index(path) >= 0:
            return True, "已在收藏夹中"
        min_order = min((x["order"] for x in _items), default=1)
        _items.append({
            "path": path,
            "name": os.path.basename(path.rstrip("\\/")) or path,
            "favorited_at": _now(),
            "order": min_order - 1,
        })
        _save()
        return True, "已收藏"


def remove(path):
    """移除收藏。返回 (ok, msg)。"""
    with _lock:
        _load()
        i = _find_index(path)
        if i < 0:
            return False, "不在收藏夹中"
        _items.pop(i)
        _save()
        return True, "已取消收藏"


def move(path, direction):
    """上移/下移收藏项（交换相邻 order）。direction: "up" | "down"。

    以显示顺序（order 升序）为准定位相邻项；首项上移循环到末尾，
    末项下移循环到开头。
    """
    with _lock:
        _load()
        if len(_items) < 2:
            return False, "收藏项不足，无法移动"
        i = _find_index(path)
        if i < 0:
            return False, "不在收藏夹中"
        ordered = sorted(range(len(_items)), key=lambda k: _items[k]["order"])
        pos = ordered.index(i)
        n = len(ordered)
        if direction == "up":
            j_pos = pos - 1 if pos > 0 else n - 1
        elif direction == "down":
            j_pos = pos + 1 if pos < n - 1 else 0
        else:
            return False, "未知方向"
        j = ordered[j_pos]
        _items[i]["order"], _items[j]["order"] = _items[j]["order"], _items[i]["order"]
        _save()
        return True, "已移动"


def clear():
    """清空收藏（测试用）。"""
    with _lock:
        global _items
        _items = []


if __name__ == "__main__":
    import sys
    print("favorites:", get_list())

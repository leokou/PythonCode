# -*- coding: utf-8 -*-
"""工作区管理：工作区文件夹列表 + workspace.json 持久化（V1.0）。

数据文件：%APPDATA%/Obsidian-upload/workspace.json
结构：{"folders": [{"name", "path"}, ...]}

职责：
- folders()：返回当前工作区文件夹列表
- add_folder(path)：添加工作区文件夹（名称取目录名，去重、跳过不存在/重复）
- remove_folder(path)：移除工作区文件夹
- load()：启动时加载（文件不存在返回空列表，不自动建文件）

线程安全：RLock（多窗口 js_api 实例可能并发调用）。
不依赖 UI / 网络，可独立测试。
"""
import json
import os
import threading

APP_DIR = "Obsidian-upload"

_lock = threading.RLock()
_folders = None   # None 表示未加载


def workspace_path():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        APP_DIR, "workspace.json")


def _load():
    global _folders
    if _folders is not None:
        return
    _folders = []
    try:
        with open(workspace_path(), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        raw = data.get("folders") if isinstance(data, dict) else None
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                p = str(item.get("path", "") or "").strip()
                if not p:
                    continue
                _folders.append({
                    "name": str(item.get("name", "") or os.path.basename(p.rstrip("\\/")) or p),
                    "path": p,
                })
    except Exception:
        _folders = []


def _save():
    try:
        path = workspace_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {"folders": [dict(f) for f in _folders]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def folders():
    """返回当前工作区文件夹列表（副本）。"""
    with _lock:
        _load()
        return [dict(f) for f in _folders]


def add_folder(path):
    """添加工作区文件夹。返回 (ok, msg, folders)。

    规则：目录必须存在；路径去重（大小写不敏感）；名称取目录名。
    """
    with _lock:
        _load()
        path = str(path or "").strip().strip('"')
        if not path:
            return False, "路径不能为空", []
        if not os.path.isdir(path):
            return False, "目录不存在：%s" % path, []
        norm = os.path.normcase(os.path.normpath(path))
        for f in _folders:
            if os.path.normcase(os.path.normpath(f["path"])) == norm:
                return True, "已在工作区中", [dict(x) for x in _folders]
        name = os.path.basename(path.rstrip("\\/")) or path
        _folders.append({"name": name, "path": os.path.normpath(path)})
        _save()
        return True, "已添加工作区文件夹", [dict(x) for x in _folders]


def remove_folder(path):
    """移除工作区文件夹。返回 (ok, msg, folders)。"""
    with _lock:
        _load()
        path = str(path or "").strip().strip('"')
        norm = os.path.normcase(os.path.normpath(path)) if path else None
        before = len(_folders)
        _folders[:] = [f for f in _folders
                       if not (norm and os.path.normcase(os.path.normpath(f["path"])) == norm)]
        if len(_folders) == before:
            return False, "未找到该文件夹", [dict(x) for x in _folders]
        _save()
        return True, "已移除工作区文件夹", [dict(x) for x in _folders]


def move_folder(path, direction):
    """上移/下移工作区文件夹（顺序即显示顺序）。direction: "up" | "down"。

    边界：首项上移 / 末项下移时保持原位并提示。返回 (ok, msg, folders)。
    """
    with _lock:
        _load()
        path = str(path or "").strip().strip('"')
        norm = os.path.normcase(os.path.normpath(path)) if path else None
        n = len(_folders)
        if n < 2:
            return False, "文件夹不足，无法移动", [dict(x) for x in _folders]
        idx = -1
        for i, f in enumerate(_folders):
            if norm and os.path.normcase(os.path.normpath(f["path"])) == norm:
                idx = i
                break
        if idx < 0:
            return False, "未找到该文件夹", [dict(x) for x in _folders]
        if direction == "up":
            if idx == 0:
                return True, "已在最上方", [dict(x) for x in _folders]
            _folders[idx], _folders[idx - 1] = _folders[idx - 1], _folders[idx]
        elif direction == "down":
            if idx == n - 1:
                return True, "已在最下方", [dict(x) for x in _folders]
            _folders[idx], _folders[idx + 1] = _folders[idx + 1], _folders[idx]
        else:
            return False, "未知方向", [dict(x) for x in _folders]
        _save()
        return True, "已移动", [dict(x) for x in _folders]


def clear():
    """清空工作区（测试用）。"""
    with _lock:
        global _folders
        _folders = []


if __name__ == "__main__":
    import sys
    print("folders:", folders())

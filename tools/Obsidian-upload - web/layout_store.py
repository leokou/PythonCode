# -*- coding: utf-8 -*-
"""三栏布局记忆：编辑/预览/目录宽度比例 + 目录可见性。

读写位置（用户可写优先，避免写入打包内置只读资源）：
- 读：EXE/脚本旁 config.json 的 layout 字段
      -> %APPDATA%\\Obsidian-upload\\layout.json
      -> 打包内置 config.json -> 内置默认
- 写：优先写 EXE/脚本旁 config.json（存在则合并 layout 写回、保留其它字段），
      否则写 %APPDATA%\\Obsidian-upload\\layout.json
"""
import json
import os
import sys

DEFAULT_LAYOUT = {
    "editor_width": 60,
    "preview_width": 30,
    "outline_width": 10,
    "outline_visible": True,
    "pane_mode": "outline",
    "workspace_visible": False,
    "workspace_width": 220,
    "explorer_sort": "time",
}

APP_DIR = "Obsidian-upload"


def _user_config_path():
    """EXE/脚本旁的 config.json（用户可写）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "config.json")
    return p if os.path.exists(p) else None


def _builtin_config_path():
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, "config.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _layout_json_path():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), APP_DIR, "layout.json")


def _read_config_layout(path):
    """读 config.json 里的 layout 字段，不存在返回 None。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data.get("layout") if isinstance(data, dict) else None
    except Exception:
        return None


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_string(key, value, default):
    """字符串字段白名单校验，非法值回退默认。"""
    allowed = {
        "pane_mode": ("outline", "history"),
        "explorer_sort": ("time", "name"),
    }.get(key)
    if allowed is None:
        return default
    return value if value in allowed else default


def _normalize(layout):
    """补齐缺键并转换为合法类型。"""
    out = dict(DEFAULT_LAYOUT)
    if isinstance(layout, dict):
        for k, default in DEFAULT_LAYOUT.items():
            if isinstance(default, bool):
                out[k] = bool(layout.get(k, default))
            elif isinstance(default, int):
                out[k] = int(layout.get(k, default))
            else:
                out[k] = _normalize_string(k, layout.get(k, default), default)
    if not 160 <= out["workspace_width"] <= 400:
        out["workspace_width"] = DEFAULT_LAYOUT["workspace_width"]
    return out


def load_layout():
    """按优先级读取布局配置，返回标准化 dict。"""
    user_cfg = _user_config_path()
    if user_cfg:
        l = _read_config_layout(user_cfg)
        if l is not None:
            return _normalize(l)
    lj = _read_json(_layout_json_path()).get("layout")
    if lj is not None:
        return _normalize(lj)
    builtin = _read_config_layout(_builtin_config_path())
    if builtin is not None:
        return _normalize(builtin)
    return dict(DEFAULT_LAYOUT)


def save_layout(layout):
    """保存布局。优先写 EXE/脚本旁 config.json，否则写 APPDATA layout.json。"""
    layout = _normalize(layout)
    user_cfg = _user_config_path()
    if user_cfg:
        try:
            with open(user_cfg, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data["layout"] = layout
            with open(user_cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            pass
    try:
        path = _layout_json_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = _read_json(path)
        data["layout"] = layout
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

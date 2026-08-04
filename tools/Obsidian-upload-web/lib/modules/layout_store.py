# -*- coding: utf-8 -*-
"""三栏布局记忆 + 窗口尺寸记忆（四个窗口独立保存）。

读写位置（用户可写优先，避免写入打包内置只读资源）：
- 读：EXE/脚本旁 config.json 的 layout_<type> / window_geometry 字段
      -> %APPDATA%\\Obsidian-upload\\layout.json
      -> 打包内置 config.json -> 内置默认
- 写：优先写 EXE/脚本旁 config.json（存在则合并写回、保留其它字段），
      否则写 %APPDATA%\\Obsidian-upload\\layout.json

四个窗口独立保存布局配置：
  - FlashNote / Inbox / 日志：默认只显示编辑和预览区域
  - A📥 收集（Capture）：默认显示资源管理区、编辑和预览区域
"""
import json
import os
import sys
import time

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

# Per-window type defaults
DEFAULT_LAYOUT_BY_TYPE = {
    "inbox": {**DEFAULT_LAYOUT, "outline_visible": False, "workspace_visible": False},
    "flash": {**DEFAULT_LAYOUT, "outline_visible": False, "workspace_visible": False},
    "log": {**DEFAULT_LAYOUT, "outline_visible": False, "workspace_visible": False},
    "capture": {**DEFAULT_LAYOUT, "outline_visible": False, "workspace_visible": True},
}

VALID_WINDOW_TYPES = frozenset(DEFAULT_LAYOUT_BY_TYPE.keys())


def _layout_key(window_type):
    """返回 per-window 布局在 config.json 中的键名."""
    return "layout_" + window_type if window_type in VALID_WINDOW_TYPES else "layout"

DEFAULT_WINDOW_GEOMETRY = {
    "width": 1600,
    "height": 950,
    "x": None,   # None = 居中
    "y": None,
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


def _read_config_layout(path, window_type=None):
    """读 config.json 里的 per-window layout 字段，不存在返回 None。
    优先读 layout_<type>，不再回退到旧 layout 字段（各窗口独立默认值）。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        key = _layout_key(window_type)
        if key in data:
            return data[key]
        return None
    except Exception:
        return None


def _read_config_window_geometry(path):
    """读 config.json 里的 window_geometry 字段，不存在返回 None。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data.get("window_geometry") if isinstance(data, dict) else None
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


def _normalize(layout, default=None):
    """补齐缺键并转换为合法类型。"""
    default = default if isinstance(default, dict) else DEFAULT_LAYOUT
    out = dict(default)
    if isinstance(layout, dict):
        for k, dflt_val in default.items():
            if isinstance(dflt_val, bool):
                out[k] = bool(layout.get(k, dflt_val))
            elif isinstance(dflt_val, int):
                out[k] = int(layout.get(k, dflt_val))
            else:
                out[k] = _normalize_string(k, layout.get(k, dflt_val), dflt_val)
    if not 160 <= out["workspace_width"] <= 400:
        out["workspace_width"] = DEFAULT_LAYOUT["workspace_width"]
    return out


def _normalize_window_geometry(wg):
    """校验窗口尺寸/位置，非法值回退默认。"""
    out = dict(DEFAULT_WINDOW_GEOMETRY)
    if isinstance(wg, dict):
        w = int(wg.get("width", out["width"]))
        h = int(wg.get("height", out["height"]))
        # 合理范围：最小 800x600，最大 3840x2160
        if 800 <= w <= 3840:
            out["width"] = w
        if 600 <= h <= 2160:
            out["height"] = h
        # 位置可以为 None（居中）或合法整数
        x = wg.get("x")
        y = wg.get("y")
        if x is not None:
            try:
                out["x"] = int(x)
            except (ValueError, TypeError):
                pass
        if y is not None:
            try:
                out["y"] = int(y)
            except (ValueError, TypeError):
                pass
    return out


def load_layout(window_type=None):
    """按优先级读取布局配置，返回标准化 dict。
    window_type 为 "inbox"/"flash"/"log"/"capture" 时读取对应窗口布局，
    不存在则直接使用 per-window 默认值（不再回退到旧 layout 字段）。"""
    default = DEFAULT_LAYOUT_BY_TYPE.get(window_type, DEFAULT_LAYOUT)
    user_cfg = _user_config_path()
    if user_cfg:
        l = _read_config_layout(user_cfg, window_type)
        if l is not None:
            return _normalize(l, default)
    lj = _read_json(_layout_json_path()).get(_layout_key(window_type))
    if lj is not None:
        return _normalize(lj, default)
    builtin = _read_config_layout(_builtin_config_path(), window_type)
    if builtin is not None:
        return _normalize(builtin, default)
    return dict(default)


def save_layout(layout, window_type=None):
    """保存布局。优先写 EXE/脚本旁 config.json，否则写 APPDATA layout.json。
    window_type 为 "inbox"/"flash"/"log"/"capture" 时保存到对应窗口字段。"""
    default = DEFAULT_LAYOUT_BY_TYPE.get(window_type, DEFAULT_LAYOUT)
    layout = _normalize(layout, default)
    key = _layout_key(window_type)
    user_cfg = _user_config_path()
    if user_cfg:
        try:
            with open(user_cfg, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data[key] = layout
            with open(user_cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            pass
    try:
        path = _layout_json_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = _read_json(path)
        data[key] = layout
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_window_geometry():
    """加载窗口尺寸/位置。优先读 config.json，再读 layout.json。"""
    user_cfg = _user_config_path()
    if user_cfg:
        wg = _read_config_window_geometry(user_cfg)
        if wg is not None:
            return _normalize_window_geometry(wg)
    lj = _read_json(_layout_json_path()).get("window_geometry")
    if lj is not None:
        return _normalize_window_geometry(lj)
    builtin = _read_config_window_geometry(_builtin_config_path())
    if builtin is not None:
        return _normalize_window_geometry(builtin)
    return dict(DEFAULT_WINDOW_GEOMETRY)


def save_window_geometry(width, height, x=None, y=None):
    """保存窗口尺寸/位置。节流版（2s 内只写一次），避免拖拽窗口时高频写盘。"""
    # 节流：2 秒内只允许一次写盘
    now = time.time()
    last_save = getattr(save_window_geometry, "_last_save", 0)
    if now - last_save < 2.0:
        return True  # 静默接受，不报错
    save_window_geometry._last_save = now

    wg = {"width": int(width), "height": int(height)}
    if x is not None:
        wg["x"] = int(x)
    if y is not None:
        wg["y"] = int(y)
    wg = _normalize_window_geometry(wg)

    user_cfg = _user_config_path()
    if user_cfg:
        try:
            with open(user_cfg, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data["window_geometry"] = wg
            with open(user_cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            pass
    try:
        path = _layout_json_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = _read_json(path)
        data["window_geometry"] = wg
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

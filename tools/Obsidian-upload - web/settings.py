# -*- coding: utf-8 -*-
"""用户设置：settings.json 位于 %APPDATA%\\Obsidian-upload\\settings.json。

只保存「文件默认保存地址」default_save_path，程序启动时读取，重启保持。
"""
import json
import os

DEFAULT_SAVE_PATH = r"D:\Obsidian\LeoDiary"

APP_DIR = "Obsidian-upload"


def settings_path():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        APP_DIR, "settings.json")


def load_settings():
    """读取设置字典，文件不存在或损坏返回空字典。"""
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(default_save_path):
    """写入 default_save_path 到 settings.json，返回是否成功。"""
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump({"default_save_path": default_save_path},
                      f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_default_save_path(cfg=None):
    """取默认保存地址：settings.json 优先，其次配置文件，最后内置默认。"""
    s = load_settings().get("default_save_path")
    if s:
        return s
    if cfg and cfg.get("default_save_path"):
        return cfg["default_save_path"]
    return DEFAULT_SAVE_PATH

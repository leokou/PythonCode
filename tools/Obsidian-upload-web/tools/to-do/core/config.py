"""配置加载：读取模块根目录下的 config.json，并把相对路径解析为绝对路径。

设计原则：禁止硬编码路径。用户可复制 config.json 到模块根目录自定义。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

# 模块根目录（config.py 所在目录的上上级）
MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DEFAULTS: Dict[str, Any] = {
    "app_name": "Leo Todo",
    "data_dir": "data",
    "db_file": "data/todo.db",
    "attachments_dir": "data/attachments",
    "log_file": "data/todo.log",
    "image_exts": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
    "default_project": "",
    "microsoft": {
        "enabled": True,
        "client_id": "",
        "tenant": "consumers",
        "scopes": ["Tasks.ReadWrite", "offline_access"],
        "redirect_uri": "http://localhost",
        "timeout": 30,
        "token_cache_file": "data/token_cache.json",
        "max_attachment_mb": 10,
    },
    "sync": {
        "auto_sync_on_start": True,
        "attachment_limit_per_task": 50,
    },
}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """递归合并，override 覆盖 base；保留 base 中 override 没有的键。"""
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path: Optional[str] = None) -> Dict:
    """加载配置。config.json 不存在时使用内置默认值。"""
    path = config_path or os.path.join(MODULE_ROOT, "config.json")
    config = json.loads(json.dumps(_DEFAULTS))  # 深拷贝默认值
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            if isinstance(user_cfg, dict):
                _deep_merge(config, user_cfg)
        except (OSError, ValueError) as exc:
            raise ConfigError(f"配置文件解析失败：{path}：{exc}") from exc

    # 相对路径统一解析到模块根目录
    for key in ("data_dir", "db_file", "attachments_dir", "log_file"):
        if key in config and config[key]:
            config[key] = _resolve(path or config_path, config[key])
    ms = config.get("microsoft") or {}
    if ms.get("token_cache_file"):
        ms["token_cache_file"] = _resolve(path or config_path, ms["token_cache_file"])
    return config


def _resolve(config_path: str, value: str) -> str:
    if os.path.isabs(value):
        return value
    base = os.path.dirname(os.path.abspath(config_path or os.path.join(MODULE_ROOT, "config.json")))
    return os.path.abspath(os.path.join(base, value))


class ConfigError(Exception):
    """配置错误。"""

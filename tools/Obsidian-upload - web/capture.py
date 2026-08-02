# -*- coding: utf-8 -*-
"""Capture 快速收集窗口：窗口配置元数据 + 聚合保存路径与逻辑。

职责：
- Capture 窗口元数据（key / 标题 / 热键 / 保存标签 / 热键提示），供 main.py 复用
- Capture 聚合保存路径：config.json 的 capture_file，缺省用内置默认
- Capture 聚合保存：复用 storage.save_note 的标准格式追加
  （#### yyyy-MM-dd HH:mm:ss + 正文 + ---），目录不存在自动创建

复用：storage.py（聚合保存）；历史记录由 main.py 调用方统一 record_edit。
"""
import os

import storage

# Capture 窗口定义：key / 标题 / 热键 / 前端文案
# 标题同时用于 Win32 窗口标题、浏览器 <title>、左上角品牌名（js_api.get_config 下发）
WINDOW_DEF = {
    "key": "capture",
    "title": "📥 Capture",
    "hotkey": "alt+d",
    "saveLabel": "保存 Capture",
    "hotkeyHint": "Alt+D 呼出窗口",
}

DEFAULT_CAPTURE_FILE = r"D:\Obsidian\LeoDiary\A📥 收集（Capture）\Capture.md"


def capture_file_path(cfg=None):
    """取 Capture 聚合保存文件路径：config.json 的 capture_file 优先，缺省内置默认。

    目录不存在时由 storage.save_note 自动创建。
    """
    if cfg and cfg.get("capture_file"):
        return cfg["capture_file"]
    return DEFAULT_CAPTURE_FILE


def save_capture(cfg, content):
    """把内容以标准格式追加保存到 Capture.md，返回 (ok, msg, ts, path)。

    复用 storage.save_note 保证与 Inbox/FlashNote 格式统一；
    失败返回 (False, 错误信息, None, None)。
    """
    if not content or not content.strip():
        return False, "没有内容可保存", None, None
    try:
        path = capture_file_path(cfg)
        ts = storage.save_note(path, content)
        return True, "已保存到 %s · %s" % (os.path.basename(path), ts), ts, path
    except Exception as e:
        return False, "保存失败：%s" % e, None, None

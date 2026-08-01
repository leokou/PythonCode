# -*- coding: utf-8 -*-
"""Markdown 保存 / Obsidian 打开 / 调试日志。

保存格式：
    #### yyyy-MM-dd HH:mm:ss

    正文内容
    图片Markdown

    ---
"""
import os
import subprocess
import urllib.parse
from datetime import datetime


def append_note(path, content):
    """把内容以「#### 时间戳 + 正文 + ---」格式追加到指定 md 文件"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = "#### %s\n\n%s\n\n---\n" % (ts, content.strip())
    with open(path, "a", encoding="utf-8") as f:
        f.write(block)
    return ts


def open_obsidian_file(filename, vault="LeoDiary"):
    """用 obsidian:// URI 在 Obsidian 中打开文件（不阻塞）"""
    quoted = urllib.parse.quote(filename)
    uri = "obsidian://open?vault=%s&file=%s" % (vault, quoted)
    try:
        subprocess.Popen(["cmd", "/c", "start", "", uri],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        os.startfile(uri)


def log_debug(msg, log_dir):
    """追加写调试日志：%APPDATA%\\Obsidian-upload\\upload_debug.log"""
    base = log_dir or os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "Obsidian-upload")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "upload_debug.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(msg + "\n\n")

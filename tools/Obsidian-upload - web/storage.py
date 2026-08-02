# -*- coding: utf-8 -*-
"""文件保存与日志存储：负责 Markdown 笔记写入与每日日志文件管理。

复用 markdown.append_note 的保存格式（#### 时间戳 + 正文 + ---，追加不覆盖）。
"""
import os
from datetime import datetime

from markdown import append_note


def ensure_dir(path):
    """确保 path 的父目录存在。返回是否成功。"""
    parent = os.path.dirname(path)
    try:
        if parent:
            os.makedirs(parent, exist_ok=True)
        return True
    except Exception:
        return False


def save_note(path, content):
    """把内容以标准格式追加保存到指定 md 文件，返回时间戳。

    目录不存在时自动创建；异常向上抛出由调用方处理。
    """
    ensure_dir(path)
    return append_note(path, content)


def daily_log_path(log_dir):
    """生成每日日志文件路径：log_dir\\yyyy-MM-dd 周X.md（按系统日期计算星期）"""
    now = datetime.now()
    weekday = "周" + "一二三四五六日"[now.weekday()]
    name = "%s %s.md" % (now.strftime("%Y-%m-%d"), weekday)
    return os.path.join(log_dir, name)


def save_daily_log(log_dir, content):
    """追加保存到当日日志文件，返回 (时间戳, 文件绝对路径)。

    目录不存在自动创建，当天文件不存在则创建，已存在则追加。
    """
    path = daily_log_path(log_dir)
    ts = save_note(path, content)
    return ts, path

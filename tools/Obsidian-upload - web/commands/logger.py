# -*- coding: utf-8 -*-
"""结构化日志模块：写入 %APPDATA%/Obsidian-upload/app.log

使用方式：
    from commands.logger import log_info, log_warn, log_error, log_debug
    log_info("程序启动")
    log_info("快捷键 Alt+S 触发")
"""
import os
import threading
from datetime import datetime

_LOG_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Obsidian-upload",
)
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_lock = threading.Lock()


def _ensure_dir():
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        pass


def _write(level, msg):
    _ensure_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = "[%s] [%s] %s\n" % (ts, level, msg)
    with _lock:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def log_info(msg):
    _write("INFO", msg)


def log_warn(msg):
    _write("WARN", msg)


def log_error(msg):
    _write("ERROR", msg)


def log_debug(msg):
    _write("DEBUG", msg)


def log_exception(msg, exc=None):
    """记录异常，附带 traceback"""
    import traceback
    full = msg
    if exc is not None:
        full += "\n" + traceback.format_exc()
    _write("ERROR", full)
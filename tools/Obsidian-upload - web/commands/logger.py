# -*- coding: utf-8 -*-
"""结构化日志模块：写入 %APPDATA%/Obsidian-upload/app.log

使用方式：
    from commands.logger import log_info, log_warn, log_error, log_debug
    log_info("程序启动")
    log_info("快捷键 Alt+S 触发")

性能优化（V1.1）：持久文件句柄 + 目录检查缓存
- _fh 持久文件句柄：首次写入时打开，后续复用，消除 open/close 系统调用开销
- _dir_ensured 缓存：目录创建后跳过 makedirs 系统调用
- flush()：退出时刷新缓冲区并关闭句柄（main.py exit_app 调用）
- 每次写入后 flush 保证崩溃安全（与原 close 行为一致）
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

_dir_ensured = False   # 目录已确认存在
_fh = None             # 持久文件句柄（append 模式）


def _ensure_dir():
    """确保日志目录存在（首次调用后跳过，减少系统调用）。"""
    global _dir_ensured
    if _dir_ensured:
        return
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _dir_ensured = True
    except Exception:
        pass


def _get_fh():
    """获取持久文件句柄（懒加载，失败返回 None）。"""
    global _fh
    if _fh is not None:
        return _fh
    _ensure_dir()
    try:
        _fh = open(_LOG_FILE, "a", encoding="utf-8")
        return _fh
    except Exception:
        return None


def _write(level, msg):
    """写入一行日志（复用持久文件句柄，写后 flush 保证崩溃安全）。"""
    global _fh
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = "[%s] [%s] %s\n" % (ts, level, msg)
    with _lock:
        fh = _get_fh()
        if fh is None:
            return
        try:
            fh.write(line)
            fh.flush()
        except Exception:
            # 句柄失效（如文件被外部删除），重置后下次重试
            _fh = None


def flush():
    """刷新缓冲区并关闭文件句柄（程序退出时调用）。"""
    global _fh
    with _lock:
        if _fh is not None:
            try:
                _fh.flush()
                _fh.close()
            except Exception:
                pass
            _fh = None


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

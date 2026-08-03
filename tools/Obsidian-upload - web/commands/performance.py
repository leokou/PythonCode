# -*- coding: utf-8 -*-
"""性能监控：记录启动时间、模块加载时间、文件扫描时间、保存耗时等。

日志文件：%APPDATA%/Obsidian-upload/performance.log
格式示例：
  [2026-08-02 10:30:00] [启动] main_start -> startup_complete: 1234.5 ms
  [2026-08-02 10:30:00] [启动] main_start -> config_loaded: 12.3 ms
  [2026-08-02 10:30:00] [启动] config_loaded -> windows_created: 456.7 ms
  [2026-08-02 10:30:05] [文件扫描] scan_dir: 23.4 ms
  [2026-08-02 10:30:10] [保存] autosave_page: 5.6 ms

使用方式：
    from commands.performance import mark, measure, log
    mark("start")
    # ... 执行操作 ...
    mark("end")
    measure("start", "end", "启动")
"""
import os
import time
from datetime import datetime

_LOG_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Obsidian-upload",
)
_LOG_FILE = os.path.join(_LOG_DIR, "performance.log")

_marks = {}  # name -> perf_counter timestamp


def mark(name):
    """记录一个时间标记（perf_counter 高精度计时）。"""
    _marks[name] = time.perf_counter()


def measure(start, end, category="性能"):
    """测量两个标记之间的耗时并记录到日志。

    如果标记不存在则静默跳过（不抛异常）。
    """
    t0 = _marks.get(start)
    t1 = _marks.get(end)
    if t0 is None or t1 is None:
        return
    ms = (t1 - t0) * 1000
    log(category, "%s -> %s" % (start, end), ms)


def log(category, name, ms):
    """写入一条性能日志到 performance.log。"""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "[%s] [%s] %s: %.1f ms\n" % (ts, category, name, ms)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def reset():
    """清除所有标记（重新计时用）。"""
    _marks.clear()


def time_call(func, category="性能", name=None, *args, **kwargs):
    """计时执行一个函数调用并记录耗时，返回函数返回值。

    示例：result = time_call(scan_dir, "文件扫描", "scan_dir", path, cfg)
    """
    fname = name or getattr(func, "__name__", "unknown")
    t0 = time.perf_counter()
    try:
        return func(*args, **kwargs)
    finally:
        ms = (time.perf_counter() - t0) * 1000
        log(category, fname, ms)

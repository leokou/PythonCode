# -*- coding: utf-8 -*-
"""LeoDiary Capture —— 多窗口、多标签页 Markdown 快速记录工具。

技术栈：Python + HTML/CSS/JS + Edge WebView2（pywebview 6.x）
窗口：四个独立窗口（Inbox Capture / FlashNote Capture / Daily Log / Capture），可同时存在、互不干扰
热键：Alt+S 打开 Inbox / Alt+E 打开 FlashNote / Alt+J 打开每日日志 / Alt+D 打开 Capture（HotkeyManager 看门狗守护）
功能：Markdown 编辑 + 实时预览 + 多标签页 + 图片上传（PicGo → Cloudflare R2）
托盘：pystray 常驻，点 X 隐藏窗口到托盘
日志：app.log（全链路）+ shortcut_error.log（热键异常）

打包：
    pyinstaller --onefile --windowed --add-data "frontend;frontend" \
        --add-data "config/config.json;config" --add-data "commands;commands" \
        --add-data "tools;tools" --add-data "app.ico;." lib/core/main.py
"""
import ctypes
import json
import os
import sys
import threading
import time

# 注册自身到 sys.modules：以 __main__ 运行时（python main.py / PyInstaller 打包入口）
# 子模块 api.py 通过 `from lib.core import main` 才能获取本模块对象。
sys.modules.setdefault('lib.core.main', sys.modules[__name__])

from commands.app_utils import (
    get_center_position,
    show_error_box,
)
from commands.hotkey_manager import HotkeyManager
from commands.logger import log_info, log_error, log_warn
from commands.performance import mark as _perf_mark, measure as _perf_measure

import webview

from lib.core.api import Api, SettingsApi, ToolApi
from lib.core import settings as settings_store
from lib.core import window_manager
from lib.backend import storage, capture as capture_store, search_engine
from lib.modules import (
    pages as page_store,
    file_assoc,
    layout_store,
    history as history_store,
    workspace as workspace_store,
    file_explorer,
    file_ops,
    theme_manager as theme_store,
    favorites as favorites_store,
    canvas_server,
)

APP_TITLE = "LeoDiary Capture"
DEFAULT_CONFIG = {
    "picgo_api": "http://127.0.0.1:36677/upload",
    "cloudflare_domain": "",
    "inbox_file": r"D:\Obsidian\LeoDiary\My-Inbox.md",
    "flashnote_file": r"D:\Obsidian\LeoDiary\🧠 FlashNote.md",
    "log_dir": r"D:\Obsidian\LeoDiary\Journals",
    "capture_file": r"D:\Obsidian\LeoDiary\A📥 收集（Capture）\Capture.md",
    "vault_name": "LeoDiary",
    "window_size": [1600, 950],
    "default_save_path": r"D:\Obsidian\LeoDiary",
    "associated_exts": [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"],
    "workspace_hidden_dirs": [".git", "node_modules", "__pycache__", "dist", ".obsidian", ".trash"],
    "search_exts": [".md", ".txt", ".py", ".js", ".json", ".yaml", ".yml"],
    "explorer_exts": [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"],
}

# 四个窗口的定义：key / 窗口标题 / 触发热键
# 标题同时用于：Win32 窗口标题、浏览器 <title>、左上角品牌名（js_api.get_config 下发）
# 热键：Alt+E=FlashNote / Alt+S=My-Inbox / Alt+J=日志 / Alt+D=Capture
WINDOW_DEFS = [
    {"key": "inbox", "title": "📥 My-Inbox", "hotkey": "alt+s"},
    {"key": "flash", "title": "🧠 FlashNote", "hotkey": "alt+e"},
    {"key": "log", "title": "📅 日志记录", "hotkey": "alt+j"},
    capture_store.WINDOW_DEF,
]

WINDOW_TITLES = {d["key"]: d["title"] for d in WINDOW_DEFS}

TOOLS_TITLE = "LeoDiary Tools"
SETTINGS_TITLE = "LeoDiary 设置"

_exit_lock = threading.Lock()
_state = {"quitting": False}
_windows = {}           # key -> window（四个独立窗口引用）
_tools_window = None    # 工具箱窗口引用
_settings_window = None  # 设置窗口引用
_canvas_window = None    # 画布窗口引用
_canvas_server = None    # 画布本地 HTTP 服务（Drawnix 需 HTTP 加载 ES Module）
_last_active = "flash"  # 最近激活的编辑窗口 key（工具箱工具派发目标）
_hotkeys = None         # HotkeyManager 实例
_stop_watchdog = threading.Event()
_MUTEX_NAME = "Local\\LeoDiaryCapture_SingleInstance"
_mutex_handle = None
_page_seq = 0


def _set_last_active(key):
    """记录最近激活的编辑窗口（热键/托盘/shown 事件时更新）"""
    global _last_active
    if key in WINDOW_TITLES:
        _last_active = key


def _check_single_instance(file_args=None):
    """单实例检查：如果已有实例运行，激活窗口后返回 False。
    文件关联启动（file_args 非空）不激活窗口，由运行中实例的后台线程处理。"""
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    _mutex_handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if not _mutex_handle:
        return True
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        if not file_args:
            # 非文件关联：激活所有窗口
            for title in WINDOW_TITLES.values():
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
        # 文件关联：不激活窗口，由后台 _pending_file_watcher 处理（避免 Win32 ShowWindow 导致 WebView 白屏）
        log_info("已有实例运行，%s" % ("文件已交给运行中的实例打开" if file_args else "已激活现有窗口"))
        return False
    log_info("单实例检查通过")
    return True


def _pending_file_watcher():
    """后台监控 pending 文件队列，检测到文件后显示 capture 窗口。

    职责（仅显示窗口，不消费文件、不调用 evaluate_js）：
    - peek 检测 pending 队列是否有文件（不清空，留给前端 get_pending_files 消费）
    - 有文件时用 pywebview win.show() 显示 capture 窗口（避免 Win32 ShowWindow 白屏）
    - 前端 script.js 定期轮询 get_pending_files API 拉取并打开文件

    不用 evaluate_js 的原因：pywebview 6.x edgechromium 后台线程调用 evaluate_js
    不阻塞等待返回值（返回 None），无法判断前端 __injectExternalFiles 是否就绪，
    导致 && 短路静默丢弃文件。改由前端主动拉取更稳健。
    """
    last_count = 0
    while not _state.get("quitting"):
        try:
            time.sleep(1.0)
            paths = file_assoc.peek_pending_files()
            if not paths:
                last_count = 0
                continue
            _set_last_active("capture")
            win = _windows.get("capture")
            if win is None:
                continue
            if len(paths) != last_count:
                log_info("后台检测到 pending 文件 %d 个，显示 capture 窗口" % len(paths))
                last_count = len(paths)
            _safe_show_window(win)
        except Exception as e:
            log_error("pending 文件监控异常: %s" % e)
            time.sleep(2.0)


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        # 源码运行：main.py 位于 lib/core/，上三级即项目根
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


def load_config():
    """优先读取 EXE/脚本旁 config.json，缺省用内置默认值并补全缺键。"""
    cfg = dict(DEFAULT_CONFIG)
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "config.json"))
    candidates.append(resource_path(os.path.join("config", "config.json")))
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                cfg.update(loaded)
            except Exception:
                pass
            break
    return cfg


def log_dir():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "Obsidian-upload")


def _safe_show_window(win):
    """安全显示窗口：处理隐藏/最小化状态，不抛异常"""
    try:
        if hasattr(win, 'is_visible') and not win.is_visible():
            win.show()
        elif hasattr(win, 'get_state'):
            state = win.get_state()
            if state == 'minimized':
                win.restore()
            win.show()
        else:
            win.show()
        return True
    except Exception:
        try:
            win.show()
            return True
        except Exception:
            return False


def make_tray_icon():
    """优先从 app.ico 加载托盘图标，找不到时回退到程序内绘制。"""
    from PIL import Image
    try:
        icon_path = resource_path("app.ico")
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
            img.load()
            return img
    except Exception:
        pass
    from PIL import ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(52, 120, 246, 255))
    d.polygon(
        [(32, 14), (20, 30), (27, 30), (27, 46), (37, 46), (37, 30), (44, 30)],
        fill="white")
    return img


def _health_check_watchdog():
    """健康检查看门狗：每 30 秒检查窗口与热键状态"""
    log_info("健康检查看门狗已启动（30秒周期）")
    checks = 0
    while not _stop_watchdog.is_set():
        time.sleep(30)
        if _stop_watchdog.is_set():
            break
        checks += 1
        for key, w in list(_windows.items()):
            try:
                _ = w
            except Exception as e:
                log_error("健康检查失败: 窗口 %s 异常 %s" % (key, e))
        try:
            if _hotkeys is not None:
                st = _hotkeys.status()
                lost = [k for k, ok in st.items() if not ok]
                if lost and checks % 2 == 0:
                    log_warn("健康检查: 热键状态异常 %s" % lost)
        except Exception as e:
            log_error("健康检查: 热键状态检测异常 %s" % e)


def _flush_all_windows():
    """退出前把每个窗口的 Tab 内容强制写盘（异常保护，避免最后几秒内容丢失）。"""
    for key, w in list(_windows.items()):
        try:
            raw = w.evaluate_js("window.__flushAll ? window.__flushAll() : null")
            if isinstance(raw, str) and raw:
                import json as _json
                items = _json.loads(raw)
                for it in items or []:
                    if it.get("ext_path"):
                        try:
                            with open(it["ext_path"], "w", encoding="utf-8",
                                      errors="replace") as f:
                                f.write(it.get("content", "") or "")
                        except Exception as e:
                            log_error("退出刷新外部文件失败(%s): %s"
                                      % (it["ext_path"], e))
                    elif it.get("page_id"):
                        page_store.write_page_file(it.get("page_id"), it.get("content", ""))
            log_info("退出刷新完成: %s" % key)
        except Exception as e:
            log_error("退出刷新失败(%s): %s" % (key, e))


def main():
    global _windows, _hotkeys, _tools_window, _settings_window, _canvas_window, _canvas_server

    _perf_mark("main_start")
    cfg = load_config()
    _perf_mark("config_loaded")

    # ---- 文件关联：提取启动参数中的文件路径（带参数启动 / Windows 文件关联） ----
    # 无论是否已有实例，先把文件写入 pending 队列：旧实例轮询消费打开，
    # 新实例（本进程）启动后由前端轮询同一队列打开。
    file_args = file_assoc.filter_file_args(sys.argv[1:], cfg)
    if file_args:
        file_assoc.enqueue_pending(file_args)
        log_info("启动参数待打开文件 %d 个: %s"
                 % (len(file_args), "; ".join(file_args)))

    # ---- 单实例检查 ----
    if not _check_single_instance(file_args):
        if file_args:
            # 带文件参数：文件已写入 pending，交给运行中的实例打开，不打扰用户
            log_info("已有实例运行，外部文件已交给运行中的实例打开")
        else:
            show_error_box(APP_TITLE, "程序已在运行中，已为你激活现有窗口。")
        return 0

    log_info("=" * 50)
    log_info("程序启动（多窗口模式）")
    log_info("=" * 50)

    index_path = os.path.abspath(resource_path(os.path.join("frontend", "editor.html")))
    if not os.path.exists(index_path):
        log_error("找不到界面文件: %s" % index_path)
        show_error_box(APP_TITLE, "找不到界面文件：%s\n请重新打包（--add-data \"frontend;frontend\"）。" % index_path)
        return 1

    # 加载记忆的窗口尺寸/位置
    saved_geo = layout_store.load_window_geometry()
    ww = saved_geo["width"]
    wh = saved_geo["height"]
    saved_x = saved_geo.get("x")
    saved_y = saved_geo.get("y")
    if saved_x is not None and saved_y is not None:
        # 安全检查：如果记忆位置超出主屏范围，回退到居中
        try:
            user32 = ctypes.windll.user32
            sm_cxscreen = user32.GetSystemMetrics(0)   # 主屏宽度
            sm_cyscreen = user32.GetSystemMetrics(1)   # 主屏高度
            # 允许 ±200px 浮动（多显示器场景），超出则居中
            if (-200 <= saved_x <= sm_cxscreen + 200
                    and -200 <= saved_y <= sm_cyscreen + 200):
                wx, wy = saved_x, saved_y
                log_info("窗口尺寸 %dx%d, 记忆位置(%d,%d)" % (ww, wh, wx, wy))
            else:
                wx, wy = get_center_position(ww, wh)
                log_info("窗口尺寸 %dx%d, 记忆位置超出屏幕，已回退居中" % (ww, wh))
        except Exception:
            wx, wy = get_center_position(ww, wh)
    else:
        wx, wy = get_center_position(ww, wh)
        log_info("窗口尺寸 %dx%d, 居中位置(%d,%d)" % (ww, wh, wx, wy))

    # ---- 创建四个独立窗口（全部隐藏，由热键/托盘呼出） ----
    def make_on_closing(key):
        def on_closing(*_args):
            if _state["quitting"]:
                return True
            try:
                _windows[key].hide()
                log_info("窗口已隐藏（X按钮）: %s" % key)
            except Exception as e:
                log_error("隐藏窗口异常: %s" % e)
            return False
        return on_closing

    def make_on_shown(key):
        def on_shown(*_args):
            _set_last_active(key)
            # Capture 窗口显示时立即触发前端轮询 pending 文件（解决隐藏时浏览器节流定时器导致延迟）
            if key == "capture":
                try:
                    _windows[key].evaluate_js(
                        "window.pollPendingFilesNow && window.pollPendingFilesNow()")
                except Exception:
                    pass
        return on_shown

    def make_save_geometry(key):
        """窗口尺寸/位置变化时保存到记忆（节流由 layout_store 内部处理）。"""
        def on_geometry_changed(*_args):
            w = _windows.get(key)
            if w is None:
                return
            try:
                size = w.get_size()
                pos = w.get_position()
                if size and pos:
                    layout_store.save_window_geometry(
                        size[0], size[1], pos[0], pos[1])
            except Exception:
                pass
        return on_geometry_changed

    try:
        for d in WINDOW_DEFS:
            api = Api(cfg, d["key"])
            win = webview.create_window(
                d["title"],
                url=index_path,
                js_api=api,
                width=ww,
                height=wh,
                x=wx,
                y=wy,
                min_size=(1280, 720),
                hidden=True,
            )
            win.events.closing += make_on_closing(d["key"])
            win.events.shown += make_on_shown(d["key"])
            win.events.resized += make_save_geometry(d["key"])
            win.events.moved += make_save_geometry(d["key"])
            _windows[d["key"]] = win
            log_info("窗口创建成功: %s (%s)" % (d["key"], d["title"]))
    except Exception as e:
        log_error("创建窗口失败: %s" % e)
        show_error_box(APP_TITLE, "创建窗口失败（需要 Edge WebView2 Runtime）：\n%s" % e)
        return 1

    # ---- 工具箱窗口（独立 1000x600，hidden 预创建） ----
    try:
        tools_html = os.path.abspath(resource_path(os.path.join("frontend", "tools.html")))
        if not os.path.exists(tools_html):
            log_error("找不到工具箱界面: %s" % tools_html)
        tx, ty = get_center_position(1000, 600)
        tools_win = webview.create_window(
            TOOLS_TITLE,
            url=tools_html,
            js_api=ToolApi(),
            width=1000,
            height=600,
            x=tx,
            y=ty,
            min_size=(800, 500),
            hidden=True,
        )

        def on_tools_closing(*_args):
            if _state["quitting"]:
                return True
            try:
                _tools_window.hide()
                log_info("工具箱窗口已隐藏（X按钮）")
            except Exception as e:
                log_error("隐藏工具箱窗口异常: %s" % e)
            return False

        tools_win.events.closing += on_tools_closing
        _tools_window = tools_win
        log_info("工具箱窗口创建成功: %s" % TOOLS_TITLE)
    except Exception as e:
        log_error("创建工具箱窗口失败: %s" % e)
        show_error_box(APP_TITLE, "创建工具箱窗口失败：\n%s" % e)
        return 1

    # ---- 设置窗口（独立窗口，hidden 预创建） ----
    try:
        settings_html = os.path.abspath(resource_path(os.path.join("frontend", "settings.html")))
        if not os.path.exists(settings_html):
            log_error("找不到设置界面: %s" % settings_html)
        stx, sty = get_center_position(620, 500)
        settings_win = webview.create_window(
            SETTINGS_TITLE,
            url=settings_html,
            js_api=SettingsApi(cfg),
            width=620,
            height=500,
            x=stx,
            y=sty,
            min_size=(520, 400),
            hidden=True,
        )

        def on_settings_closing(*_args):
            if _state["quitting"]:
                return True
            try:
                _settings_window.hide()
                log_info("设置窗口已隐藏（X按钮）")
            except Exception as e:
                log_error("隐藏设置窗口异常: %s" % e)
            return False

        settings_win.events.closing += on_settings_closing
        _settings_window = settings_win
        log_info("设置窗口创建成功: %s" % SETTINGS_TITLE)
    except Exception as e:
        log_error("创建设置窗口失败: %s" % e)
        show_error_box(APP_TITLE, "创建设置窗口失败：\n%s" % e)
        return 1

    # ---- 画布窗口（Drawnix 白板，hidden 预创建） ----
    # Drawnix 是 Vite/React 构建的 ES Module 应用，file:// 直开会被浏览器 CORS
    # 拦截白屏，必须先启动本地 HTTP 服务（lib/modules/canvas_server.py）承载构建产物。
    # 同时放开浏览器下载（默认 False 会拦截 Drawnix 的导出 PNG/JSON）。
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception as e:
        log_warn("设置允许下载失败: %s" % e)
    try:
        canvas_root = os.path.abspath(resource_path(os.path.join("tools", "drawnix")))
        if not os.path.isdir(canvas_root):
            log_error("找不到画布构建产物: %s" % canvas_root)
            raise OSError("找不到画布构建产物: %s" % canvas_root)
        _canvas_server = canvas_server.CanvasServer(canvas_root)
        canvas_url = _canvas_server.start()
        cwx, cwy = get_center_position(1400, 900)
        canvas_win = webview.create_window(
            "Drawnix 画布",
            url=canvas_url,
            width=1400,
            height=900,
            x=cwx,
            y=cwy,
            min_size=(800, 600),
            hidden=True,
        )

        def on_canvas_closing(*_args):
            if _state["quitting"]:
                return True
            try:
                _canvas_window.hide()
                log_info("画布窗口已隐藏（X按钮）")
            except Exception as e:
                log_error("隐藏画布窗口异常: %s" % e)
            return False

        canvas_win.events.closing += on_canvas_closing
        _canvas_window = canvas_win
        log_info("画布窗口创建成功")
    except Exception as e:
        log_error("创建画布窗口失败: %s" % e)
        # 画布创建失败不阻塞主流程

    # ---- 热键回调：呼出对应窗口并置顶 + 聚焦编辑器 ----
    _perf_mark("windows_created")
    def make_summon(key):
        def summon():
            log_info("热键触发: %s" % key)
            w = _windows.get(key)
            if w is None:
                log_error("窗口引用为空: %s" % key)
                return
            try:
                _set_last_active(key)
                shown = window_manager.show_capture_window(w, WINDOW_TITLES[key])
                if shown:
                    log_info("窗口已激活并置顶: %s" % key)
                else:
                    log_warn("窗口激活未完全生效（未找到句柄）: %s" % key)
                # 窗口显示后聚焦编辑器（WebView2 聚焦稍慢，延时一次）
                time.sleep(0.2)
                try:
                    w.evaluate_js("view && view.focus()")
                except Exception:
                    pass
            except Exception as e:
                log_error("唤醒窗口异常: %s" % e)
        return summon

    _hotkeys = HotkeyManager()
    for d in WINDOW_DEFS:
        _hotkeys.add_hotkey(d["key"], d["hotkey"], make_summon(d["key"]))
    if not _hotkeys.start():
        log_warn("热键注册失败，程序仍可正常使用，但快捷键不可用")

    # ---- 托盘常驻 ----
    def tray_run():
        try:
            import pystray
        except ImportError:
            log_error("pystray 未安装")
            return
        menu = pystray.Menu(
            pystray.MenuItem(
                "打开 Inbox",
                lambda i, it: (_set_last_active("inbox"),
                               _safe_show_window(_windows["inbox"]))[1]),
            pystray.MenuItem(
                "打开 FlashNote",
                lambda i, it: (_set_last_active("flash"),
                               _safe_show_window(_windows["flash"]))[1]),
            pystray.MenuItem(
                "打开日志",
                lambda i, it: (_set_last_active("log"),
                               _safe_show_window(_windows["log"]))[1]),
            pystray.MenuItem(
                "打开 Capture",
                lambda i, it: (_set_last_active("capture"),
                               _safe_show_window(_windows["capture"]))[1],
                default=True),
            pystray.MenuItem(
                "工具箱",
                lambda i, it: _safe_show_window(_tools_window)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出程序", lambda i, it: exit_app()),
        )
        icon = pystray.Icon("obsidian-upload", make_tray_icon(), APP_TITLE, menu)
        log_info("托盘图标已启动")
        icon.run()

    def _kill_other_instances():
        """杀掉所有其他 Obsidian-upload.exe 同名进程，确保退出后无残留（不杀自身）。"""
        try:
            import subprocess
            script = (
                "Get-Process -Name 'Obsidian-upload' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.Id -ne %d } | Stop-Process -Force" % os.getpid()
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, timeout=3,
            )
        except Exception as e:
            log_error("清理其他实例失败: %s" % e)

    def exit_app():
        with _exit_lock:
            if _state["quitting"]:
                return
            _state["quitting"] = True
        log_info("程序退出中...")
        _stop_watchdog.set()
        if _hotkeys is not None:
            _hotkeys.stop()
        # 保存当前窗口尺寸/位置
        try:
            for key, w in _windows.items():
                try:
                    size = w.get_size()
                    pos = w.get_position()
                    if size and pos:
                        layout_store.save_window_geometry(
                            size[0], size[1], pos[0], pos[1])
                        log_info("保存窗口几何: %s %dx%d (%d,%d)"
                                 % (key, size[0], size[1], pos[0], pos[1]))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            _flush_all_windows()
        except Exception:
            pass
        try:
            history_store.flush()
        except Exception:
            pass
        try:
            page_store.flush()
        except Exception:
            pass
        try:
            log_info("程序退出完成")
            from commands.logger import flush as _log_flush
            _log_flush()
        except Exception:
            pass
        try:
            for w in _windows.values():
                w.destroy()
            if _tools_window is not None:
                _tools_window.destroy()
            if _settings_window is not None:
                _settings_window.destroy()
            if _canvas_window is not None:
                _canvas_window.destroy()
        except Exception:
            pass
        try:
            if _canvas_server is not None:
                _canvas_server.stop()
        except Exception:
            pass
        finally:
            _kill_other_instances()
            os._exit(0)

    threading.Thread(target=tray_run, daemon=True).start()

    # ---- 健康检查看门狗 ----
    threading.Thread(target=_health_check_watchdog, daemon=True).start()

    # ---- pending 文件后台监控（文件关联：检测到文件 → 显示 capture 窗口 → JS 注入） ----
    threading.Thread(target=_pending_file_watcher, daemon=True).start()

    # ---- 主事件循环 ----
    try:
        log_info("进入主事件循环")

        # 启动后默认显示 FlashNote 主窗口，其余窗口由热键呼出
        def show_default():
            time.sleep(0.3)
            try:
                if not _state["quitting"]:
                    _set_last_active("flash")
                    _safe_show_window(_windows["flash"])
                    log_info("启动完成，显示主窗口 FlashNote")
                    _perf_mark("startup_complete")
                    _perf_measure("main_start", "config_loaded", "启动")
                    _perf_measure("config_loaded", "windows_created", "启动")
                    _perf_measure("windows_created", "startup_complete", "启动")
                    _perf_measure("main_start", "startup_complete", "启动")
            except Exception as e:
                log_error("启动显示主窗口异常: %s" % e)
        threading.Thread(target=show_default, daemon=True).start()

        webview.start(debug=False, gui="edgechromium")
    except Exception as e:
        log_error("启动失败: %s" % e)
        show_error_box(APP_TITLE, "启动失败：%s" % e)
        return 1

    log_info("程序正常退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())

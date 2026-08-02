# -*- coding: utf-8 -*-
"""全局快捷键统一管理器（Windows RegisterHotKey 系统级热键）。

解决的问题：
1. 原 keyboard 库为普通键盘钩子监听，Chrome/VSCode 等软件会抢先处理快捷键，
   导致本软件无法被调出。RegisterHotKey 是 Windows 系统级热键，注册后由系统
   统一裁决，任何程序前台运行时按下都会可靠触发（类似 QQ截图/Everything）。
2. EXE 长时间运行后热键失效问题：看门狗每 30 秒检测消息循环存活 + 每 2 分钟
   强制重注册。

实现：
- 在独立线程中创建隐藏消息窗口，RegisterHotKey 注册（窗口与消息循环同线程）
- WM_HOTKEY 消息循环中把热键事件置位，工作线程消费后执行回调（零阻塞）
- 回调不阻塞消息循环，避免卡顿

使用：
    hm = HotkeyManager()
    hm.add_hotkey("flash", "alt+e", on_flash)
    hm.start()
"""
import ctypes
import ctypes.wintypes as wt
import os
import threading
import time

from commands.logger import log_info, log_warn, log_error

WM_HOTKEY = 0x0312
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
WM_APP_REBIND = 0x8001  # 自定义：请求在热键线程内重注册热键
PM_REMOVE = 0x0001
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_BASE = 0xC000  # 应用级热键 id 从 0xC000 起（Windows 预留）

USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32

USER32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
USER32.RegisterHotKey.restype = wt.BOOL
USER32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
USER32.UnregisterHotKey.restype = wt.BOOL
USER32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
USER32.CreateWindowExW.restype = wt.HWND
USER32.DestroyWindow.argtypes = [wt.HWND]
USER32.DestroyWindow.restype = wt.BOOL
USER32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
USER32.PostMessageW.restype = wt.BOOL
USER32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
USER32.PostThreadMessageW.restype = wt.BOOL
USER32.GetMessageW.argtypes = [wt.LPMSG, wt.HWND, wt.UINT, wt.UINT]
USER32.GetMessageW.restype = ctypes.c_int
USER32.PeekMessageW.argtypes = [wt.LPMSG, wt.HWND, wt.UINT, wt.UINT, wt.UINT]
USER32.PeekMessageW.restype = wt.BOOL
USER32.TranslateMessage.argtypes = [wt.LPMSG]
USER32.TranslateMessage.restype = wt.BOOL
USER32.DispatchMessageW.argtypes = [wt.LPMSG]
USER32.DispatchMessageW.restype = wt.LPARAM
USER32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
USER32.DefWindowProcW.restype = wt.LPARAM
KERNEL32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
KERNEL32.GetModuleHandleW.restype = wt.HINSTANCE
KERNEL32.GetLastError.argtypes = []
KERNEL32.GetLastError.restype = wt.DWORD

WNDPROC = ctypes.WINFUNCTYPE(wt.LPARAM, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
# 保持 WNDPROC 引用，防止被垃圾回收
_wndproc_ref = None


class _WNDCLASSW(ctypes.Structure):
    """ctypes.wintypes 无 WNDCLASSW，按 Windows 定义手动声明"""
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


_CLASS_NAME = "LeoDiaryHotkeyMsgWnd"


def default_error_log_path():
    """shortcut_error.log 默认路径：%APPDATA%\\Obsidian-upload\\shortcut_error.log"""
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "Obsidian-upload", "shortcut_error.log")


def _parse_hotkey(hotkey_str):
    """解析 "alt+e" → (mods, vk)。支持 alt/ctrl/shift/win + 单字符。"""
    parts = [p.strip().lower() for p in str(hotkey_str).split("+")]
    mods = 0
    key = ""
    for p in parts:
        if p in ("alt", "menu"):
            mods |= MOD_ALT
        elif p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("win", "super"):
            mods |= MOD_WIN
        elif p:
            key = p
    if not key:
        return None
    return mods, ord(key.upper())


class HotkeyManager:
    """多个 Windows 全局热键的统一注册与守护。"""

    def __init__(self, error_log_path=None):
        self._hotkeys = {}        # name -> (hotkey_str, callback)
        self._events = {}         # name -> threading.Event（回调触发信号）
        self._installed = set()   # 当前已注册成功的热键名
        self._stop = threading.Event()
        self._log_path = error_log_path or default_error_log_path()
        self._log_lock = threading.Lock()
        # RegisterHotKey 相关
        self._hwnd = None
        self._thread_id = None
        self._id_map = {}         # name -> hotkey id
        self._id_rev = {}         # hotkey id -> name
        self._next_id = HOTKEY_ID_BASE
        self._wndproc = None
        self._thread = None       # 热键线程（窗口 + 消息循环）
        self._msg_thread = None   # 看门狗重建的消息循环线程
        self._resync = threading.Event()  # 看门狗请求热键线程内重注册

    # ---- 公共 API ----
    def add_hotkey(self, name, hotkey_str, callback):
        """注册一个热键。name 用于日志标识，hotkey_str 如 "alt+e"。"""
        self._hotkeys[name] = (hotkey_str, callback)

    def start(self):
        """注册所有热键并启动工作线程 + 看门狗。返回是否全部注册成功。"""
        self._ready = threading.Event()
        self._start_ok = [False]
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="hotkey-msg")
        self._thread.start()
        self._ready.wait(3)
        ok = self._start_ok[0]
        threading.Thread(target=self._worker_loop, daemon=True,
                         name="hotkey-worker").start()
        threading.Thread(target=self._watchdog_loop, daemon=True,
                         name="hotkey-watchdog").start()
        if ok:
            log_info("热键管理器已启动（RegisterHotKey，%d 个热键，30秒检测 + 2分钟强制重置）"
                     % len(self._hotkeys))
        return ok

    def stop(self):
        """停止所有线程并释放热键（退出程序时调用）"""
        self._stop.set()
        try:
            self._unregister_all()
        except Exception:
            pass
        if self._hwnd:
            try:
                USER32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

    def status(self):
        """当前每个热键的注册状态（供日志/检测使用）"""
        return {name: (name in self._installed)
                for name in self._hotkeys}

    # ---- 内部实现：热键线程（创建窗口 + 注册 + 消息循环） ----
    def _run(self):
        self._thread_id = threading.get_ident()
        try:
            if not self._create_message_window():
                self._start_ok[0] = False
                self._ready.set()
                return
            ok = self._register_all()
            self._start_ok[0] = ok
            self._ready.set()
            self._message_loop()
        except Exception as e:
            log_error("热键线程异常: %s" % e)
            self._start_ok[0] = False
            self._ready.set()

    def _create_message_window(self):
        global _wndproc_ref
        try:
            self._wndproc = WNDPROC(self._wnd_proc)
            _wndproc_ref = self._wndproc
            hinst = KERNEL32.GetModuleHandleW(None)
            wc = _WNDCLASSW()
            wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
            wc.hInstance = hinst
            wc.lpszClassName = _CLASS_NAME
            USER32.RegisterClassW(ctypes.byref(wc))  # 已注册则忽略
            self._hwnd = USER32.CreateWindowExW(
                0, _CLASS_NAME, _CLASS_NAME,
                0, 0, 0, 0, 0,
                None, None, hinst, None)
            return bool(self._hwnd)
        except Exception as e:
            log_error("创建热键消息窗口失败: %s" % e)
            return False

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_HOTKEY:
            hid = wparam & 0xFFFF
            name = self._id_rev.get(hid)
            if name:
                ev = self._events.get(name)
                if ev:
                    ev.set()  # 零阻塞：仅置位，工作线程消费
        elif msg == WM_DESTROY:
            # 通知消息循环退出
            if self._thread_id:
                try:
                    USER32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            return 0
        elif msg == WM_CLOSE:
            try:
                USER32.DestroyWindow(hwnd)
            except Exception:
                pass
            return 0
        return USER32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self):
        while not self._stop.is_set():
            # 看门狗请求的重注册：在热键线程内执行，避免跨线程注册/注销导致 1408
            if self._resync.is_set():
                self._resync.clear()
                try:
                    self._register_all()
                except Exception as e:
                    log_error("热键重注册异常: %s" % e)
                    self._log("热键重注册异常: %s" % e, "重注册异常")
            msg = wt.MSG()
            if USER32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_QUIT:
                    break
                USER32.TranslateMessage(ctypes.byref(msg))
                USER32.DispatchMessageW(ctypes.byref(msg))
            else:
                self._stop.wait(0.05)

    # ---- 注册 / 注销 ----
    def _register_all(self):
        self._unregister_all()
        all_ok = True
        for name, (hk, _cb) in self._hotkeys.items():
            parsed = _parse_hotkey(hk)
            if parsed is None:
                all_ok = False
                msg = "热键 %s (%s) 格式无法解析" % (name, hk)
                log_error(msg)
                self._log(msg, "解析失败")
                continue
            mods, vk = parsed
            hid = self._next_id
            self._next_id += 1
            if USER32.RegisterHotKey(self._hwnd, hid, mods | MOD_NOREPEAT, vk):
                self._id_map[name] = hid
                self._id_rev[hid] = name
                self._events[name] = threading.Event()
                self._installed.add(name)
                log_info("热键 %s (%s) 注册成功" % (name, hk))
            else:
                self._installed.discard(name)
                all_ok = False
                msg = "热键 %s (%s) 注册失败 (error=%s)" % (
                    name, hk, KERNEL32.GetLastError())
                log_error(msg)
                self._log(msg, "注册失败")
        if not all_ok:
            self._log("热键注册完成，存在失败项", "注册失败")
        return all_ok

    def _unregister_all(self):
        for name, hid in list(self._id_map.items()):
            try:
                USER32.UnregisterHotKey(self._hwnd, hid)
            except Exception:
                pass
        self._id_map.clear()
        self._id_rev.clear()
        self._installed.clear()

    # ---- 工作线程：消费热键事件并执行回调 ----
    def _worker_loop(self):
        while not self._stop.is_set():
            for name, ev in list(self._events.items()):
                if ev.is_set():
                    ev.clear()
                    try:
                        _hk, callback = self._hotkeys[name]
                        callback()
                    except Exception as e:
                        log_error("热键 %s 回调异常: %s" % (name, e))
                        self._log("热键 %s 回调异常: %s" % (name, e), "回调异常")
            self._stop.wait(0.2)

    # ---- 看门狗 ----
    def _watchdog_loop(self):
        check = 0
        while not self._stop.is_set():
            time.sleep(30)
            if self._stop.is_set():
                break
            check += 1
            thread_alive = (self._thread is not None and self._thread.is_alive()) \
                or (self._msg_thread is not None and self._msg_thread.is_alive())
            if not thread_alive:
                log_warn("看门狗: 热键消息循环失效，执行重置")
                self._log("看门狗: 消息循环失效，执行重置", "消息循环失效")
                # 完整重建：销毁旧窗口，新线程内重新建窗+注册（确保注册在热键线程执行）
                try:
                    if self._hwnd:
                        USER32.DestroyWindow(self._hwnd)
                except Exception:
                    pass
                self._hwnd = None
                self._resync.clear()
                self._msg_thread = threading.Thread(target=self._run,
                                                    daemon=True, name="hotkey-msg2")
                self._msg_thread.start()
                check = 0
            elif check >= 4:  # 每 2 分钟强制重注册，确保绝对存活（热键线程内执行）
                log_info("看门狗: 2分钟强制重置热键（热键线程内重注册）")
                self._resync.set()
                check = 0
            elif check % 2 == 0:
                log_info("看门狗: 热键健康 (check=%d)" % check)

    # ---- 日志 ----
    def _log(self, msg, status_note):
        """写 shortcut_error.log：时间 + 错误信息 + 快捷键状态"""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        detail = ", ".join(
            "%s(%s)=%s" % (name, hk, "ok" if name in self._installed else "lost")
            for name, (hk, _cb) in self._hotkeys.items())
        line = "[%s] %s | 快捷键状态: %s | %s\n" % (ts, msg, detail, status_note)
        with self._log_lock:
            try:
                os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass

# -*- coding: utf-8 -*-
"""通用应用工具模块：窗口操作、屏幕坐标、错误弹窗等。

可独立复用，不依赖 pywebview。
全局热键统一管理见 commands/hotkey_manager.py（HotkeyManager）。
"""
import ctypes
from ctypes import wintypes


def pick_folder(title="选择文件夹"):
    """Windows 文件夹选择对话框（SHBrowseForFolderW），返回绝对路径；取消返回 None。

    不使用 Tkinter（项目规范禁用），通过 ctypes 直接调用 Shell32。
    """
    BIF_RETURNONLYFSDIRS = 0x00000001
    BIF_NEWDIALOGSTYLE = 0x00000040
    MAX_PATH = 260

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", ctypes.c_wchar_p),
            ("lpszTitle", ctypes.c_wchar_p),
            ("ulFlags", wintypes.UINT),
            ("lpfn", ctypes.c_void_p),
            ("lParam", ctypes.c_void_p),
            ("iImage", ctypes.c_int),
        ]

    try:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)
        display = ctypes.create_unicode_buffer(MAX_PATH)
        bi = BROWSEINFO(
            None, None, display, title,
            BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE,
            None, None, 0,
        )
        shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
        pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
        if not pidl:
            ole32.CoUninitialize()
            return None
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        shell32.SHGetPathFromIDListW(pidl, buf)
        ole32.CoTaskMemFree(pidl)
        ole32.CoUninitialize()
        path = buf.value or None
        return path if path and path.strip() else None
    except Exception:
        try:
            ole32.CoUninitialize()
        except Exception:
            pass
        return None


def get_screen_size():
    """返回 (screen_width, screen_height)"""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def get_center_position(window_width, window_height):
    """计算窗口居中的 (x, y) 坐标"""
    sw, sh = get_screen_size()
    wx = max(0, (sw - window_width) // 2)
    wy = max(0, (sh - window_height) // 2)
    return wx, wy


def bring_window_to_front(title):
    """通过窗口标题查找窗口并强制置顶到最前"""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    return False


def show_error_box(title, msg):
    """Win32 错误弹窗（不使用 Tkinter）"""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(msg), str(title), 0x10)
    except Exception:
        pass
# -*- coding: utf-8 -*-
"""窗口管理器：全局热键调起窗口的统一激活流程 + 强制前台聚焦。

解决的问题：
1. SetForegroundWindow 受 Windows 前台锁限制，后台进程调用通常被拒绝，
   导致热键弹出窗口后还要手动点击任务栏。
2. HWND 在 64 位系统是 64 位指针，未设置 argtypes 时会被 ctypes 截断。

方案：
- show_capture_window(type)：统一流程 显示 → 恢复 → 激活 → 置顶瞬间 → 置前。
- force_foreground(hwnd)：AttachThreadInput 挂到前台线程 + 模拟一次 Alt 键
  绕过系统前台限制，确保窗口立即成为活动窗口并获得键盘焦点。
"""
import ctypes
import ctypes.wintypes as wt

USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32

# 常量
SW_RESTORE = 9
SW_SHOW = 5
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002

# 正确声明 Win32 签名（避免 64 位 HWND 截断）
USER32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
USER32.FindWindowW.restype = wt.HWND
USER32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
USER32.ShowWindow.restype = wt.BOOL
USER32.BringWindowToTop.argtypes = [wt.HWND]
USER32.BringWindowToTop.restype = wt.BOOL
USER32.SetForegroundWindow.argtypes = [wt.HWND]
USER32.SetForegroundWindow.restype = wt.BOOL
USER32.GetForegroundWindow.argtypes = []
USER32.GetForegroundWindow.restype = wt.HWND
USER32.GetWindowThreadProcessId.argtypes = [wt.HWND, wt.LPDWORD]
USER32.GetWindowThreadProcessId.restype = wt.DWORD
USER32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
USER32.AttachThreadInput.restype = wt.BOOL
USER32.SetFocus.argtypes = [wt.HWND]
USER32.SetFocus.restype = wt.HWND
USER32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wt.UINT]
USER32.SetWindowPos.restype = wt.BOOL
USER32.keybd_event.argtypes = [wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_ulonglong]
KERNEL32.GetCurrentThreadId.argtypes = []
KERNEL32.GetCurrentThreadId.restype = wt.DWORD


def find_hwnd_by_title(title):
    """通过窗口标题查找窗口句柄（pywebview 窗口标题唯一）。"""
    return USER32.FindWindowW(None, title)


def force_foreground(hwnd):
    """让后台窗口可靠获得前台焦点，返回是否成功。

    组合拳：AttachThreadInput 到前台线程 → ShowWindow/置顶/SetForegroundWindow
    → 兜底模拟一次 Alt 键（系统允许该技巧绕过前台锁）。
    """
    if not hwnd:
        return False
    cur_thread = KERNEL32.GetCurrentThreadId()
    fg = USER32.GetForegroundWindow()
    fg_thread = USER32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = False
    if fg and fg_thread and fg_thread != cur_thread:
        try:
            attached = bool(USER32.AttachThreadInput(cur_thread, fg_thread, True))
        except Exception:
            attached = False
    try:
        USER32.ShowWindow(hwnd, SW_RESTORE)
        USER32.BringWindowToTop(hwnd)
        USER32.SetForegroundWindow(hwnd)
        USER32.SetFocus(hwnd)
    except Exception:
        pass
    if attached:
        try:
            USER32.AttachThreadInput(cur_thread, fg_thread, False)
        except Exception:
            pass
    # 兜底：模拟一次 Alt 键后重试置前（QQ截图/微信快捷键的通用做法）
    if USER32.GetForegroundWindow() != hwnd:
        try:
            USER32.keybd_event(VK_MENU, 0, 0, 0)
            USER32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            USER32.BringWindowToTop(hwnd)
            USER32.SetForegroundWindow(hwnd)
        except Exception:
            pass
    return USER32.GetForegroundWindow() == hwnd


def show_capture_window(win, title):
    """统一窗口激活流程：显示 → 恢复 → 置顶瞬间 → 置前 → 聚焦。

    win: pywebview 窗口对象；title: Win32 窗口标题（用于 FindWindowW）。
    置顶仅在激活瞬间生效，随后恢复，避免永久挡住其他窗口。
    """
    if win is not None:
        try:
            if not win.is_visible():
                win.show()
        except Exception:
            try:
                win.show()
            except Exception:
                pass
        try:
            win.restore()
        except Exception:
            pass
    hwnd = find_hwnd_by_title(title)
    if hwnd:
        force_foreground(hwnd)
        # 激活瞬间置顶，随后恢复（避免长期遮挡）
        try:
            USER32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
            USER32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE)
        except Exception:
            pass
        return True
    return False

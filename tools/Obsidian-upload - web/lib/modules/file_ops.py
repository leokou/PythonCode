# -*- coding: utf-8 -*-
"""工作区文件操作（file_ops.py V1.0）：资源管理器右键菜单后端能力。

职责：
- copy_text(text)：复制文本到 Windows 剪贴板（ctypes，无第三方依赖）
- reveal_in_explorer(path)：在 Windows 资源管理器中定位选中文件
- open_with_vscode(path)：用 VSCode 打开文件（code 命令，-r 复用已开窗口）
- rename_file(path, new_name)：重命名文件（保留扩展名 / 重名检测 / 同步 history.rename）
- delete_file(path)：删除文件（移动到回收站，可恢复；同步 history.remove）

设计原则：
- 只做文件系统 / 系统命令操作，不依赖 UI / 网络，可独立测试。
- 删除走回收站（SHFileOperationW FOF_ALLOWUNDO），禁止直接物理删除。
- 公共能力复用 history（重命名 / 删除后同步历史记录）。
"""
import ctypes
import os
import shutil
import subprocess
from ctypes import wintypes

from lib.modules import history

INVALID_CHARS = '<>:"|?*'


def copy_text(text):
    """复制文本到 Windows 剪贴板（CF_UNICODETEXT）。成功返回 True。"""
    if text is None:
        text = ""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            GMEM_MOVEABLE = 0x0002
            GMEM_ZEROINIT = 0x0040
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
            if not h:
                return False
            p = kernel32.GlobalLock(h)
            if not p:
                kernel32.GlobalFree(h)
                return False
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
            CF_UNICODETEXT = 13
            user32.SetClipboardData(CF_UNICODETEXT, h)
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def get_clipboard_text():
    """读取 Windows 剪贴板文本（CF_UNICODETEXT）。返回 (ok, text)。"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        if not user32.OpenClipboard(None):
            return False, ""
        try:
            CF_UNICODETEXT = 13
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return False, ""
            p = kernel32.GlobalLock(h)
            if not p:
                return False, ""
            try:
                text = ctypes.wstring_at(p)
            finally:
                kernel32.GlobalUnlock(h)
            return True, text
        finally:
            user32.CloseClipboard()
    except Exception:
        return False, ""


def reveal_in_explorer(path):
    """在 Windows 资源管理器中打开路径。返回 (ok, msg)。

    - 文件：定位并选中（/select,）
    - 文件夹：直接打开该文件夹窗口
    """
    if not path or not os.path.exists(path):
        return False, "文件不存在或已移动"
    try:
        if os.path.isdir(path):
            # 文件夹：直接打开该文件夹窗口（不用 /select,）
            subprocess.Popen(["explorer", os.path.normpath(path)])
            return True, "已打开文件夹"
        # 文件：定位并选中（explorer 对带逗号的单参数解析不可靠，须拆成两个参数）
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        return True, "已在资源管理器中定位"
    except Exception as e:
        return False, "打开资源管理器失败：%s" % e


def open_with_vscode(path):
    """用 VSCode 打开文件（-r 复用已打开窗口）。返回 (ok, msg)。"""
    if not path or not os.path.exists(path):
        return False, "文件不存在或已移动"
    code = shutil.which("code")
    if not code:
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        ]
        code = next((c for c in candidates if os.path.exists(c)), None)
    if not code:
        return False, "未找到 VSCode（code 命令或安装路径）"
    try:
        subprocess.Popen([code, "-r", os.path.normpath(path)],
                         cwd=os.path.dirname(os.path.normpath(path)))
        return True, "已用 VSCode 打开"
    except Exception as e:
        return False, "启动 VSCode 失败：%s" % e


def rename_file(path, new_name):
    """重命名文件或文件夹。返回 (ok, msg, new_path)。

    - 文件：用户未输入扩展名时自动保留原扩展名（文件夹不补扩展名）
    - 重名检测（不区分大小写）
    - 成功后同步 history.rename（历史面板路径跟随，含子路径）
    """
    if not path or not os.path.exists(path):
        return False, "文件不存在或已移动", path
    is_dir = os.path.isdir(path)
    new_name = (new_name or "").strip()
    if not new_name:
        return False, "名称不能为空", path
    if os.sep in new_name or "/" in new_name or "\\" in new_name:
        return False, "名称不能包含路径分隔符", path
    for ch in INVALID_CHARS:
        if ch in new_name:
            return False, "名称包含非法字符：%s" % ch, path
    if new_name in (".", ".."):
        return False, "名称无效", path

    base = os.path.basename(path)
    ext = os.path.splitext(base)[1]
    if not is_dir and not os.path.splitext(new_name)[1] and ext:
        new_name += ext

    d = os.path.dirname(path)
    new_path = os.path.normpath(os.path.join(d, new_name))
    if os.path.normcase(new_path) == os.path.normcase(path):
        return True, "名称未变化", path
    if os.path.exists(new_path):
        return False, "同名文件已存在", path
    try:
        os.rename(path, new_path)
    except OSError as e:
        return False, "重命名失败：%s" % e, path
    history.rename(path, new_path)
    return True, "已重命名为 %s" % new_name, new_path


class _SHFILEOPSTRUCTW(ctypes.Structure):
    """SHFILEOPSTRUCTW 结构（SHFileOperationW 删除到回收站用）。"""
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.INT),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def delete_file(path):
    """删除文件或文件夹到回收站（可恢复）。返回 (ok, msg)。

    - 走 SHFileOperationW FO_DELETE + FOF_ALLOWUNDO（不确认、静默）
    - 成功后同步 history（单文件 remove，文件夹 remove_tree）
    """
    if not path or not os.path.exists(path):
        return False, "文件不存在或已移动"
    is_dir = os.path.isdir(path)
    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    try:
        pfrom = os.path.normpath(path) + "\0"
        op = _SHFILEOPSTRUCTW(
            None, FO_DELETE, pfrom, None,
            FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT,
            False, None, None)
        ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if ret != 0:
            return False, "删除失败（错误码 %s）" % ret
    except Exception as e:
        return False, "删除失败：%s" % e
    if not os.path.exists(path):
        if is_dir:
            history.remove_tree(path)
        else:
            history.remove(path)
        return True, "已删除到回收站"
    return False, "文件未被删除"


def create_folder(parent):
    """在指定目录内新建文件夹，重名自动加 (2)(3)…。返回 (ok, msg, new_path)。"""
    if not parent or not os.path.isdir(parent):
        return False, "目录不存在", parent
    new_path = os.path.normpath(os.path.join(parent, "新建文件夹"))
    i = 2
    while os.path.exists(new_path):
        new_path = os.path.normpath(os.path.join(parent, "新建文件夹 (%d)" % i))
        i += 1
    try:
        os.makedirs(new_path)
    except OSError as e:
        return False, "创建失败：%s" % e, parent
    return True, "已创建文件夹 %s" % os.path.basename(new_path), new_path


def create_file(parent):
    """在指定目录内新建 Markdown 文件，重名自动加 (2)(3)…。返回 (ok, msg, new_path)。"""
    if not parent or not os.path.isdir(parent):
        return False, "目录不存在", parent
    new_path = os.path.normpath(os.path.join(parent, "新建笔记.md"))
    i = 2
    while os.path.exists(new_path):
        new_path = os.path.normpath(os.path.join(parent, "新建笔记 (%d).md" % i))
        i += 1
    try:
        with open(new_path, "w", encoding="utf-8") as f:
            f.write("")
    except OSError as e:
        return False, "创建失败：%s" % e, parent
    return True, "已创建文件 %s" % os.path.basename(new_path), new_path


def duplicate_file(path):
    """复制文件或文件夹副本到当前目录：生成「原名-副本」，重名自动加 (2)(3)…。返回 (ok, msg, new_path)。"""
    if not path or not os.path.exists(path):
        return False, "文件不存在", path
    d = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))
    new_path = os.path.normpath(os.path.join(d, "%s-副本%s" % (stem, ext)))
    i = 2
    while os.path.exists(new_path):
        new_path = os.path.normpath(os.path.join(d, "%s-副本(%d)%s" % (stem, i, ext)))
        i += 1
    try:
        if os.path.isdir(path):
            shutil.copytree(path, new_path)
        else:
            shutil.copy2(path, new_path)
    except OSError as e:
        return False, "复制失败：%s" % e, path
    return True, "已复制副本 %s" % os.path.basename(new_path), new_path


def move_item(path, dest_dir):
    """移动文件或文件夹到目标目录。返回 (ok, msg, new_path)。

    - 目标目录必须存在；目标不能是自身或其内部（移动文件夹时）
    - 目标已有同名项时自动加 (2)(3)… 序号，不覆盖
    - 移动后同步 history.move_path（源路径下所有记录迁移到新位置）
    """
    if not path or not os.path.exists(path):
        return False, "文件不存在或已移动", path
    if not dest_dir or not os.path.isdir(dest_dir):
        return False, "目标目录不存在", path
    src = os.path.normpath(path)
    dst = os.path.normpath(dest_dir)
    if os.path.normcase(src) == os.path.normcase(dst):
        return False, "目标目录不能是自身", path
    if os.path.normcase(dst).startswith(os.path.normcase(src) + os.sep):
        return False, "不能移动到自身内部", path
    base = os.path.basename(src)
    target = os.path.normpath(os.path.join(dst, base))
    i = 2
    while os.path.exists(target):
        stem, ext = os.path.splitext(base)
        target = os.path.normpath(os.path.join(dst, "%s(%d)%s" % (stem, i, ext)))
        i += 1
    try:
        shutil.move(src, target)
    except Exception as e:
        return False, "移动失败：%s" % e, path
    history.move_path(src, target)
    return True, "已移动到 %s" % os.path.basename(dst), target


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "copy":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        print("copy_text:", copy_text(text))
    else:
        print("用法: python file_ops.py copy <文本>")

# -*- coding: utf-8 -*-
"""LeoDiary Capture —— 多窗口、多标签页 Markdown 快速记录工具。

技术栈：Python + HTML/CSS/JS + Edge WebView2（pywebview 6.x）
窗口：四个独立窗口（Inbox Capture / FlashNote Capture / Daily Log / Capture），可同时存在、互不干扰
热键：Alt+S 打开 Inbox / Alt+E 打开 FlashNote / Alt+J 打开每日日志 / Alt+D 打开 Capture（HotkeyManager 看门狗守护）
功能：Markdown 编辑 + 实时预览 + 多标签页 + 图片上传（PicGo → Cloudflare R2）
托盘：pystray 常驻，点 X 隐藏窗口到托盘
日志：app.log（全链路）+ shortcut_error.log（热键异常）

打包：
    pyinstaller --onefile --windowed --add-data "web;web" --add-data "config.json;." \
        --add-data "commands;commands" --add-data "app.ico;." main.py
"""
import ctypes
import json
import os
import sys
import threading
import time

from commands.app_utils import (
    get_center_position,
    show_error_box,
)
from commands.hotkey_manager import HotkeyManager
from commands.logger import log_info, log_error, log_warn

import webview

import pages as page_store
import settings as settings_store
import storage
import file_assoc
import window_manager
import layout_store
import history as history_store
import workspace as workspace_store
import search_engine
import file_explorer
import file_ops
import capture as capture_store

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
    "layout": {"editor_width": 60, "preview_width": 30, "outline_width": 10, "outline_visible": True, "explorer_sort": "time"},
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


def _check_single_instance():
    """单实例检查：如果已有实例运行，激活其任一窗口后返回 False"""
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    _mutex_handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if not _mutex_handle:
        return True
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        for title in WINDOW_TITLES.values():
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        log_info("已有实例运行，已激活现有窗口")
        return False
    log_info("单实例检查通过")
    return True


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_config():
    """优先读取 EXE/脚本旁 config.json，缺省用内置默认值并补全缺键。"""
    cfg = dict(DEFAULT_CONFIG)
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "config.json"))
    candidates.append(resource_path("config.json"))
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


class Api:
    """每个窗口独立的 js_api（inbox/flash/log 三份实例，编辑状态互不共享）。

    前端通过 pywebview.api.get_config() 获取本窗口类型，upload_image/save 按类型分派。
    """

    def __init__(self, cfg, window_type):
        self.cfg = cfg
        self.window_type = window_type
        self.log = os.path.join(log_dir(), "upload_debug.log")
        self._init_log_dir()

    def _init_log_dir(self):
        try:
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
        except Exception:
            pass

    # ---- 前端配置：告诉页面它是哪个窗口 ----
    def get_config(self):
        return {
            "windowType": self.window_type,
            "title": WINDOW_TITLES[self.window_type],
            "saveLabel": {
                "inbox": "保存 Inbox",
                "flash": "保存 FlashNote",
                "log": "保存日志",
                "capture": capture_store.WINDOW_DEF["saveLabel"],
            }[self.window_type],
            "hotkeyHint": {
                "inbox": "Alt+S 呼出窗口",
                "flash": "Alt+E 呼出窗口",
                "log": "Alt+J 呼出窗口",
                "capture": capture_store.WINDOW_DEF["hotkeyHint"],
            }[self.window_type],
            "defaultSavePath": settings_store.get_default_save_path(self.cfg),
            "layout": layout_store.load_layout(),
        }

    # ---- 三栏布局：读取 / 保存宽度比例与目录可见性 ----
    def get_layout(self):
        return layout_store.load_layout()

    def save_layout(self, layout):
        if not isinstance(layout, dict):
            return {"ok": False, "msg": "布局参数无效"}
        if not layout_store.save_layout(layout):
            return {"ok": False, "msg": "布局保存失败"}
        self.cfg["layout"] = layout
        log_info("三栏布局已保存: %s" % layout)
        return {"ok": True}

    # ---- 历史记录 ----
    def get_history(self, limit=100):
        """获取最近历史记录（按最后编辑时间倒序，默认 100 条）。"""
        try:
            return {"ok": True, "items": history_store.query(limit)}
        except Exception as e:
            log_error("获取历史记录失败: %s" % e)
            return {"ok": False, "items": [], "msg": "获取历史记录失败"}

    def search_history(self, keyword, limit=100):
        """按文件名称模糊搜索历史记录。"""
        try:
            return {"ok": True, "items": history_store.search(keyword, limit)}
        except Exception as e:
            log_error("搜索历史记录失败: %s" % e)
            return {"ok": False, "items": [], "msg": "搜索历史记录失败"}

    def open_history_file(self, path):
        """从历史列表重新打开文件：读取内容 + 更新最近打开时间。"""
        try:
            res = file_explorer.open_file(path)
            if not res.get("ok"):
                return res
            log_info("从历史重新打开文件: %s" % path)
            return res
        except Exception as e:
            log_error("打开历史文件失败(%s): %s" % (path, e))
            return {"ok": False, "msg": "打开文件失败：%s" % e}

    # ---- 工作区资源管理器 ----
    def pick_workspace_folder(self):
        """弹出 Windows 文件夹选择对话框（pywebview 原生 IFileDialog），返回所选路径（取消返回 null）。"""
        try:
            win = next((w for w in webview.windows if w is not None), None)
            if win is None:
                return {"ok": False, "path": None, "msg": "窗口不可用"}
            picked = win.create_file_dialog(webview.FOLDER_DIALOG)
            if isinstance(picked, (tuple, list)):
                picked = picked[0] if picked else None
            if picked:
                log_info("已选择工作区文件夹: %s" % picked)
                return {"ok": True, "path": picked}
            return {"ok": False, "path": None}
        except Exception as e:
            log_error("选择文件夹失败: %s" % e)
            return {"ok": False, "path": None, "msg": "选择文件夹失败"}

    def get_workspace(self):
        """返回工作区文件夹列表。"""
        try:
            return {"ok": True, "folders": file_explorer.folders()}
        except Exception as e:
            log_error("获取工作区失败: %s" % e)
            return {"ok": False, "folders": [], "msg": "获取工作区失败"}

    def add_workspace_folder(self, path):
        """添加工作区文件夹。"""
        ok, msg, folders = file_explorer.add_folder(path)
        log_info("添加工作区文件夹: %s -> %s" % (path, msg))
        return {"ok": ok, "folders": folders, "msg": msg}

    def remove_workspace_folder(self, path):
        """移除工作区文件夹。"""
        ok, msg, folders = file_explorer.remove_folder(path)
        log_info("移除工作区文件夹: %s -> %s" % (path, msg))
        return {"ok": ok, "folders": folders, "msg": msg}

    def get_file_tree(self, path, sort="time"):
        """扫描目录的直接子项（懒加载，前端展开目录时调用）。
        sort: "time" 最近修改时间倒序（默认，最新在前）| "name" 名称 A-Z。
        """
        try:
            items = file_explorer.scan(path, sort, self.cfg)
            return {"ok": True, "items": items}
        except Exception as e:
            log_error("扫描目录失败(%s): %s" % (path, e))
            return {"ok": False, "items": [], "msg": "扫描目录失败"}

    def search_workspace(self, keyword, limit=100, match_case=False, regex=False, whole_word=False):
        """在工作区内全量搜索文件内容。

        match_case=True 区分大小写；regex=True 按正则匹配；whole_word=True 只匹配完整单词。
        """
        try:
            roots = [f["path"] for f in workspace_store.folders()]
            results, err = search_engine.search(
                roots, keyword, self.cfg, limit,
                match_case=bool(match_case), regex=bool(regex), whole_word=bool(whole_word))
            if err:
                return {"ok": False, "results": [], "count": 0, "msg": err}
            return {"ok": True, "results": results, "count": len(results)}
        except Exception as e:
            log_error("工作区搜索失败(%s): %s" % (keyword, e))
            return {"ok": False, "results": [], "count": 0, "msg": "搜索失败"}

    # ---- 资源管理器右键菜单：文件操作 ----
    def explorer_copy_text(self, text):
        """复制文本到剪贴板（复制文件名称 / 完整路径）。"""
        ok = file_ops.copy_text(text)
        log_info("资源管理器复制文本: %s" % ("成功" if ok else "失败"))
        return {"ok": ok, "msg": "" if ok else "复制到剪贴板失败"}

    def explorer_reveal(self, path):
        """在 Windows 资源管理器中定位并选中文件。"""
        ok, msg = file_ops.reveal_in_explorer(path)
        return {"ok": ok, "msg": msg}

    def explorer_open_vscode(self, path):
        """用 VSCode 打开文件。"""
        ok, msg = file_ops.open_with_vscode(path)
        log_info("资源管理器 VSCode 打开: %s (%s)" % (path, msg))
        return {"ok": ok, "msg": msg}

    def explorer_rename(self, path, new_name):
        """重命名文件（保留扩展名），同步历史记录。返回新路径。"""
        ok, msg, new_path = file_ops.rename_file(path, new_name)
        log_info("资源管理器重命名: %s -> %s (%s)" % (path, new_path, msg))
        return {"ok": ok, "msg": msg, "path": new_path}

    def explorer_delete(self, path):
        """删除文件到回收站（可恢复），同步历史记录。"""
        ok, msg = file_ops.delete_file(path)
        log_info("资源管理器删除: %s (%s)" % (path, msg))
        return {"ok": ok, "msg": msg}

    def explorer_dirs(self):
        """工作区内所有目录（含子目录），供移动弹窗选择。"""
        try:
            return {"ok": True, "dirs": file_explorer.all_dirs(self.cfg)}
        except Exception as e:
            log_error("获取目录列表失败: %s" % e)
            return {"ok": False, "dirs": [], "msg": "获取目录列表失败"}

    def explorer_duplicate(self, path):
        """复制文件副本到当前目录。"""
        ok, msg, new_path = file_ops.duplicate_file(path)
        log_info("资源管理器复制副本: %s -> %s (%s)" % (path, new_path, msg))
        return {"ok": ok, "msg": msg, "path": new_path}

    def explorer_move(self, path, dest_dir):
        """移动文件/文件夹到目标目录，同步历史记录。"""
        ok, msg, new_path = file_ops.move_item(path, dest_dir)
        log_info("资源管理器移动: %s -> %s (%s)" % (path, new_path, msg))
        return {"ok": ok, "msg": msg, "path": new_path}

    def explorer_new_folder(self, path):
        """在指定目录内新建文件夹。"""
        ok, msg, new_path = file_ops.create_folder(path)
        log_info("资源管理器新建文件夹: %s -> %s (%s)" % (path, new_path, msg))
        return {"ok": ok, "msg": msg, "path": new_path}

    def explorer_new_file(self, path):
        """在指定目录内新建 Markdown 文件。"""
        ok, msg, new_path = file_ops.create_file(path)
        log_info("资源管理器新建文件: %s -> %s (%s)" % (path, new_path, msg))
        return {"ok": ok, "msg": msg, "path": new_path}

    # ---- 页面（Tab 独立文件）管理 ----
    def _new_page_id(self):
        global _page_seq
        _page_seq += 1
        return "%s-%d-%d" % (self.window_type, int(time.time() * 1000), _page_seq)

    def _tab_dir(self):
        if self.window_type == "capture":
            # Capture 的 Tab 独立文件与聚合文件同在 A📥 收集（Capture）目录
            return os.path.dirname(capture_store.capture_file_path(self.cfg))
        root = settings_store.get_default_save_path(self.cfg)
        return os.path.join(root, page_store.tab_subdir(self.window_type))

    def create_page(self, title=""):
        """新增 Tab 时创建对应 Markdown 文件并登记到 pages.json。"""
        try:
            d = self._tab_dir()
            page_store.ensure_dir(d)
            base = page_store.sanitize_filename(title) or page_store.untitled_name()
            path = page_store.unique_file(d, base)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            page = {
                "id": self._new_page_id(),
                "window_type": self.window_type,
                "title": title or base,
                "file": path,
                "created": page_store.now_str(),
                "updated": page_store.now_str(),
                "status": "saved",
            }
            page_store.add_page(page)
            history_store.record_edit(path)
            log_info("创建页面(%s): %s" % (self.window_type, path))
            return {"ok": True, "page": page}
        except Exception as e:
            log_error("创建页面失败: %s" % e)
            return {"ok": False, "msg": "创建页面失败：%s" % e}

    def autosave_page(self, page_id, content):
        """自动保存：覆盖写入 Tab 文件（防丢失缓存，不追加）。

        默认保存路径变更后，已存在页面会自动迁移到新目录再写。
        """
        try:
            path = self._page_target_path(page_id)
            if not path:
                return {"ok": False, "msg": "页面不存在"}
            wrote = page_store.write_page_file(page_id, content)
            if not wrote:
                return {"ok": False, "msg": "自动保存失败"}
            history_store.record_edit(wrote)
            return {"ok": True, "file": wrote}
        except Exception as e:
            log_error("自动保存失败(%s): %s" % (page_id, e))
            return {"ok": False, "msg": "自动保存失败：%s" % e}

    def _page_target_path(self, page_id):
        """按当前默认保存路径解析页面目标文件：路径变化则先迁移。"""
        page = page_store.find_page(page_id)
        if not page:
            return None
        new_dir = self._tab_dir()
        path = page_store.migrate_page(page_id, new_dir)
        return path

    def rename_page(self, page_id, new_title):
        """首行标题变更时同步重命名文件并更新 pages.json。"""
        try:
            page = page_store.find_page(page_id)
            if not page:
                return {"ok": False, "msg": "页面不存在"}
            base = page_store.sanitize_filename(new_title)
            if not base:
                return {"ok": True, "page": page}
            old_path = page.get("file", "")
            old_base = os.path.splitext(os.path.basename(old_path))[0]
            if old_base == base:
                page_store.update_page(page_id, title=new_title.strip(), updated=page_store.now_str())
                page["title"] = new_title.strip()
                return {"ok": True, "page": page}
            d = self._tab_dir()
            page_store.ensure_dir(d)
            new_path = page_store.unique_file(d, base)
            try:
                if old_path and os.path.exists(old_path):
                    os.rename(old_path, new_path)
                else:
                    open(new_path, "w", encoding="utf-8").close()
            except Exception:
                new_path = old_path
            page_store.update_page(page_id, title=new_title.strip(), file=new_path,
                                   updated=page_store.now_str())
            page["file"] = new_path
            page["title"] = new_title.strip()
            log_info("重命名页面(%s): %s -> %s" % (page_id, old_base, base))
            return {"ok": True, "page": page}
        except Exception as e:
            log_error("重命名页面失败(%s): %s" % (page_id, e))
            return {"ok": False, "msg": "重命名页面失败：%s" % e}

    def get_pages(self):
        """返回本窗口类型的所有页面元数据（用于启动恢复）。"""
        try:
            pages = [p for p in page_store.load_pages()
                     if p.get("window_type") == self.window_type]
            return {"ok": True, "pages": pages}
        except Exception as e:
            log_error("获取页面列表失败: %s" % e)
            return {"ok": False, "msg": "获取页面列表失败"}

    def restore_page(self, page_id):
        """读取页面文件内容（用于恢复未保存页面）。"""
        try:
            page = page_store.find_page(page_id)
            if not page:
                return {"ok": False, "msg": "页面不存在"}
            content = ""
            try:
                with open(page.get("file", ""), "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
            history_store.record_open(page.get("file", ""))
            return {"ok": True, "content": content, "page": page}
        except Exception as e:
            log_error("恢复页面失败(%s): %s" % (page_id, e))
            return {"ok": False, "msg": "恢复页面失败"}
    def close_page(self, page_id, delete_file=False):
        """关闭 Tab：删除文件（可选）+ 从 pages.json 移除。"""
        try:
            page = page_store.find_page(page_id)
            if page and delete_file:
                f = page.get("file", "")
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                        log_info("已删除页面文件: %s" % f)
                    except Exception as e:
                        log_error("删除页面文件失败: %s" % e)
            page_store.remove_page(page_id)
            log_info("关闭页面(%s): %s" % (page_id, "删除文件" if delete_file else "保留文件"))
            return {"ok": True}
        except Exception as e:
            log_error("关闭页面失败(%s): %s" % (page_id, e))
            return {"ok": False, "msg": "关闭页面失败"}

    # ---- 文件关联：打开外部文件 / 覆盖保存 ----
    def get_pending_files(self):
        """前端轮询获取待打开的外部文件（仅 Inbox 窗口消费，统一在此打开）。

        新实例带文件参数启动时写入 pending 队列，运行中的实例前端轮询此接口消费。
        """
        try:
            if self.window_type != "inbox":
                return {"ok": True, "files": []}
            paths = file_assoc.take_pending_files()
            files = file_assoc.read_external_files(paths)
            if files:
                for f in files:
                    history_store.record_open(f.get("path", ""))
                log_info("打开外部文件 %d 个" % len(files))
                _set_last_active("inbox")
                _safe_show_window(_windows.get("inbox"))
            return {"ok": True, "files": files}
        except Exception as e:
            log_error("获取待打开文件失败: %s" % e)
            return {"ok": True, "files": []}

    def save_external_file(self, path, content):
        """文件关联打开的文件：保存时直接覆盖原文件，不另存为、不改变原路径。"""
        try:
            if not path:
                return {"ok": False, "msg": "缺少文件路径"}
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(content or "")
            history_store.record_edit(path)
            log_info("已覆盖外部文件: %s" % path)
            return {"ok": True, "path": path,
                    "msg": "已保存到 %s" % os.path.basename(path)}
        except Exception as e:
            log_error("保存外部文件失败(%s): %s" % (path, e))
            return {"ok": False, "msg": "保存失败：%s" % e}

    # ---- 保存按钮：Tab 文件 + 聚合追加 并存 ----
    def save_with_page(self, page_id, content, hide=True):
        """点保存：覆盖写当前 Tab 文件，同时执行原有聚合追加逻辑。
        hide=True 保存后隐藏窗口；hide=False（同步）窗口保持打开。"""
        tab_ok, tab_msg = True, ""
        if page_id:
            try:
                path = self._page_target_path(page_id)
                if not path:
                    tab_ok = False
                    tab_msg = "页面不存在 · "
                else:
                    wrote = page_store.write_page_file(page_id, content)
                    if wrote:
                        history_store.record_edit(wrote)
                    tab_msg = ("已保存页面 %s · " % os.path.basename(wrote)) if wrote else ""
                    tab_ok = bool(wrote)
            except Exception as e:
                tab_ok = False
                tab_msg = "页面保存失败：%s · " % e
        agg_ok, agg_msg = self._aggregate_append(content)
        if not tab_ok or not agg_ok:
            self._hide_window()
            return {"ok": False, "msg": tab_msg + agg_msg}
        if hide:
            self._hide_window()
        return {"ok": True, "msg": tab_msg + agg_msg}

    def _aggregate_append(self, content):
        """原有聚合追加逻辑：返回 (ok, msg)。"""
        if not content or not content.strip():
            return False, "没有内容可保存"
        try:
            if self.window_type == "log":
                d = self.cfg.get("log_dir") or r"D:\Obsidian\LeoDiary\Journals"
                ts, path = storage.save_daily_log(d, content)
                msg = "已保存日志 %s · %s" % (os.path.basename(path), ts)
            elif self.window_type == "capture":
                ok_cap, msg_cap, ts, path = capture_store.save_capture(self.cfg, content)
                if not ok_cap:
                    return False, msg_cap
                msg = msg_cap
            else:
                path = (self.cfg["inbox_file"] if self.window_type == "inbox"
                        else self.cfg["flashnote_file"])
                ts = storage.save_note(path, content)
                msg = "已保存到 %s · %s" % (os.path.basename(path), ts)
            history_store.record_edit(path)
            log_info("保存成功(%s): %s · %s" % (self.window_type, os.path.basename(path), ts))
            return True, msg
        except Exception as e:
            log_error("保存失败(%s): %s" % (self.window_type, e))
            return False, "保存失败：%s" % e

    # ---- 图片上传 ----
    def upload_image(self, data_url):
        log_info("图片上传开始（%s）" % self.window_type)
        try:
            import uploader
            img = uploader.decode_base64_png(data_url)
            png = uploader.image_to_png_bytes(img)
            name = uploader.picgo_filename()
            ok, url, debug = uploader.upload_to_picgo(
                png, name, self.cfg["picgo_api"])
            if not ok:
                msg = debug.get("hint") or debug.get("service_status") or "上传失败"
                import markdown as mdlib
                mdlib.log_debug(
                    "==================\nUpload Failed\n==================\n%s"
                    % json.dumps(debug, ensure_ascii=False, indent=2),
                    log_dir())
                log_error("图片上传失败: %s" % msg)
                return {"ok": False, "msg": msg}
            link = uploader.generate_markdown(url)
            import markdown as mdlib
            mdlib.log_debug(
                "==================\nUpload Success\n==================\n"
                "Original File:\n%s\n\nRemote URL:\n%s\n\nMarkdown:\n%s\n"
                "==================" % (name, url, link),
                log_dir())
            log_info("图片上传成功: %s" % url)
            return {"ok": True, "url": url, "markdown": link}
        except Exception as e:
            log_error("图片处理异常: %s" % e)
            return {"ok": False, "msg": "图片处理失败：%s" % e}

    # ---- 保存：按窗口类型分派目标（保留原有聚合逻辑） ----
    def save(self, content, hide=True):
        ok, msg = self._aggregate_append(content)
        if not ok:
            return {"ok": False, "msg": msg}
        if hide:
            self._hide_window()
        return {"ok": True, "msg": msg}

    # ---- 保存后隐藏本窗口 ----
    def _hide_window(self):
        w = _windows.get(self.window_type)
        if w:
            try:
                w.hide()
                log_info("窗口已隐藏: %s" % self.window_type)
            except Exception:
                pass

    # ---- 前端弹窗 ----
    def show_error(self, title, msg):
        show_error_box(title, msg)
        return True

    # ---- 前端调试日志 ----
    def log_debug(self, msg):
        log_info("前端调试: %s" % msg)
        return True

    # ---- 打开工具箱窗口 ----
    def open_tools(self):
        if _tools_window is not None:
            _safe_show_window(_tools_window)
            log_info("打开工具箱窗口（来源: %s）" % self.window_type)
        return True

    # ---- 打开设置窗口 ----
    def open_settings(self):
        if _settings_window is not None:
            _safe_show_window(_settings_window)
            log_info("打开设置窗口（来源: %s）" % self.window_type)
        return True

    # ---- 设置：读取 / 保存默认保存路径 ----
    def get_settings(self):
        return {"ok": True,
                "default_save_path": settings_store.get_default_save_path(self.cfg)}

    def save_settings(self, default_save_path):
        p = (default_save_path or "").strip()
        if not p:
            return {"ok": False, "msg": "保存路径不能为空"}
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            log_error("保存路径不可用: %s (%s)" % (p, e))
            return {"ok": False, "msg": "路径不可用：%s" % e}
        if not settings_store.save_settings(p):
            return {"ok": False, "msg": "设置写入失败"}
        self.cfg["default_save_path"] = p
        log_info("默认保存路径已更新: %s" % p)
        return {"ok": True, "path": p}


class SettingsApi:
    """设置窗口 js_api：与 Api 共享同一份 cfg（修改立即对所有窗口生效）。"""

    def __init__(self, cfg):
        self.cfg = cfg

    def get_settings(self):
        return {"ok": True,
                "default_save_path": settings_store.get_default_save_path(self.cfg)}

    def save_settings(self, default_save_path):
        p = (default_save_path or "").strip()
        if not p:
            return {"ok": False, "msg": "保存路径不能为空"}
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            log_error("保存路径不可用: %s (%s)" % (p, e))
            return {"ok": False, "msg": "路径不可用：%s" % e}
        if not settings_store.save_settings(p):
            return {"ok": False, "msg": "设置写入失败"}
        self.cfg["default_save_path"] = p
        log_info("设置窗口: 默认保存路径已更新: %s" % p)
        return {"ok": True, "path": p}


class ToolApi:
    """工具箱窗口 js_api：工具列表 / 排序保存 / 派发执行。

    工具配置来源：优先读 %APPDATA%\\Obsidian-upload\\tools.json（用户可写，保存排序），
    缺失时回退到打包内置 tools/tools.json，最后回退代码内置默认。
    执行：把工具命令通过 evaluate_js 派发给最近激活的编辑窗口（_last_active）。
    """

    def __init__(self):
        self.user_path = os.path.join(log_dir(), "tools.json")
        self.builtin_path = resource_path(os.path.join("tools", "tools.json"))

    def _builtin_default(self):
        return {
            "tools": [
                {
                    "id": "clean_empty_lines",
                    "name": "🧹 删除空行",
                    "desc": "清理 Markdown 连续空行",
                    "icon": "🧹",
                    "iconSize": 64,
                    "order": 1,
                }
            ]
        }

    def _load(self):
        """返回工具列表（dict 列表）"""
        for path in (self.user_path, self.builtin_path):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    tools = data.get("tools") if isinstance(data, dict) else data
                    if isinstance(tools, list) and tools:
                        return tools
                except Exception as e:
                    log_warn("读取工具配置失败 %s: %s" % (path, e))
        return self._builtin_default()["tools"]

    def _save(self, tools):
        payload = {"tools": tools}
        try:
            os.makedirs(os.path.dirname(self.user_path), exist_ok=True)
            with open(self.user_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            log_error("保存工具配置失败: %s" % e)
            return False

    # ---- 前端：获取工具列表（按 order 排序） ----
    def get_tools(self):
        try:
            tools = self._load()
            return sorted(tools, key=lambda t: t.get("order", 999))
        except Exception as e:
            log_error("获取工具列表失败: %s" % e)
            return self._builtin_default()["tools"]

    # ---- 前端：保存拖动后的排序 ----
    def save_order(self, order_ids):
        try:
            order_map = {str(i): n + 1 for n, i in enumerate(order_ids)}
            tools = self._load()
            for t in tools:
                o = order_map.get(str(t.get("id", "")))
                if o:
                    t["order"] = o
            tools.sort(key=lambda t: t.get("order", 999))
            ok = self._save(tools)
            log_info("工具排序已保存: %s" % ("成功" if ok else "失败"))
            return ok
        except Exception as e:
            log_error("保存工具排序失败: %s" % e)
            return False

    # ---- 前端：执行工具（派发到最近激活的编辑窗口） ----
    def run_tool(self, tool_id):
        key = _last_active if _last_active in _windows else "flash"
        w = _windows.get(key)
        if w is None:
            return {"ok": False, "msg": "没有可用的编辑窗口"}
        try:
            w.evaluate_js("window.__runTool && window.__runTool(%s)" % json.dumps(tool_id))
            log_info("工具箱派发工具: %s → %s" % (tool_id, key))
            return {"ok": True, "msg": "已在 %s 执行" % WINDOW_TITLES[key]}
        except Exception as e:
            log_error("派发工具失败(%s → %s): %s" % (tool_id, key, e))
            return {"ok": False, "msg": "执行失败：%s" % e}


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
    global _windows, _hotkeys, _tools_window, _settings_window

    cfg = load_config()

    # ---- 文件关联：提取启动参数中的文件路径（带参数启动 / Windows 文件关联） ----
    # 无论是否已有实例，先把文件写入 pending 队列：旧实例轮询消费打开，
    # 新实例（本进程）启动后由前端轮询同一队列打开。
    file_args = file_assoc.filter_file_args(sys.argv[1:], cfg)
    if file_args:
        file_assoc.enqueue_pending(file_args)
        log_info("启动参数待打开文件 %d 个: %s"
                 % (len(file_args), "; ".join(file_args)))

    # ---- 单实例检查 ----
    if not _check_single_instance():
        if file_args:
            # 带文件参数：文件已写入 pending，交给运行中的实例打开，不打扰用户
            log_info("已有实例运行，外部文件已交给运行中的实例打开")
        else:
            show_error_box(APP_TITLE, "程序已在运行中，已为你激活现有窗口。")
        return 0

    log_info("=" * 50)
    log_info("程序启动（多窗口模式）")
    log_info("=" * 50)

    index_path = os.path.abspath(resource_path(os.path.join("web", "editor.html")))
    if not os.path.exists(index_path):
        log_error("找不到界面文件: %s" % index_path)
        show_error_box(APP_TITLE, "找不到界面文件：%s\n请重新打包（--add-data \"web;web\"）。" % index_path)
        return 1

    ws = cfg.get("window_size") or [2800, 1600]
    ww, wh = int(ws[0]), int(ws[1])
    wx, wy = get_center_position(ww, wh)
    log_info("窗口尺寸 %dx%d, 位置(%d,%d)" % (ww, wh, wx, wy))

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
        return on_shown

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
            _windows[d["key"]] = win
            log_info("窗口创建成功: %s (%s)" % (d["key"], d["title"]))
    except Exception as e:
        log_error("创建窗口失败: %s" % e)
        show_error_box(APP_TITLE, "创建窗口失败（需要 Edge WebView2 Runtime）：\n%s" % e)
        return 1

    # ---- 工具箱窗口（独立 1000x600，hidden 预创建） ----
    try:
        tools_html = os.path.abspath(resource_path(os.path.join("web", "tools.html")))
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
        settings_html = os.path.abspath(resource_path(os.path.join("web", "settings.html")))
        if not os.path.exists(settings_html):
            log_error("找不到设置界面: %s" % settings_html)
        stx, sty = get_center_position(620, 480)
        settings_win = webview.create_window(
            SETTINGS_TITLE,
            url=settings_html,
            js_api=SettingsApi(cfg),
            width=620,
            height=480,
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

    # ---- 热键回调：呼出对应窗口并置顶 + 聚焦编辑器 ----
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
        try:
            _flush_all_windows()
        except Exception:
            pass
        try:
            history_store.flush()
        except Exception:
            pass
        try:
            for w in _windows.values():
                w.destroy()
            if _tools_window is not None:
                _tools_window.destroy()
            if _settings_window is not None:
                _settings_window.destroy()
        except Exception:
            pass
        finally:
            _kill_other_instances()
            os._exit(0)

    threading.Thread(target=tray_run, daemon=True).start()

    # ---- 健康检查看门狗 ----
    threading.Thread(target=_health_check_watchdog, daemon=True).start()

    # ---- 主事件循环 ----
    try:
        log_info("进入主事件循环")

        # 启动后默认显示 FlashNote 主窗口，其余窗口由热键呼出
        def show_default():
            time.sleep(1.5)
            try:
                if not _state["quitting"]:
                    _set_last_active("flash")
                    _safe_show_window(_windows["flash"])
                    log_info("启动完成，显示主窗口 FlashNote")
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

# -*- coding: utf-8 -*-
"""API 桥接层：暴露给前端 JS 的 pywebview js_api。

包含三个类：
- Api          编辑器窗口 js_api（inbox/flash/log/capture 四份实例，编辑状态互不共享）
- SettingsApi  设置窗口 js_api（与 Api 共享同一份 cfg）
- ToolApi      工具箱窗口 js_api（工具列表 / 排序 / 派发执行）

依赖 main 模块的全局状态（_windows / _tools_window / _page_seq 等），
通过 `from lib.core import main as _main` 获取模块引用，方法调用时访问。
"""
import json
import os
import time

from commands.app_utils import show_error_box
from commands.logger import log_info, log_error, log_warn

import webview

from lib.core import settings as settings_store
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
)

# main 模块引用：在 main.py 顶部通过 sys.modules.setdefault 注册后可获取。
# 方法调用时 main 已完全加载，全局状态均已定义。
from lib.core import main as _main

# 新建页面的默认内容（# 标题 + 空行模板）
NEW_PAGE_DEFAULT_CONTENT = "# \n" + "\n" * 20


class Api:
    """每个窗口独立的 js_api（inbox/flash/log 三份实例，编辑状态互不共享）。

    前端通过 pywebview.api.get_config() 获取本窗口类型，upload_image/save 按类型分派。
    """

    def __init__(self, cfg, window_type):
        self.cfg = cfg
        self.window_type = window_type
        self.log = os.path.join(_main.log_dir(), "upload_debug.log")
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
            "title": _main.WINDOW_TITLES[self.window_type],
            "saveLabel": {
                "inbox": "保存 Inbox",
                "flash": "保存 FlashNote",
                "log": "保存日志",
                "capture": capture_store.WINDOW_DEF["saveLabel"],
            }[self.window_type],
            "hotkeyHint": {
                "inbox": "Alt+E 呼出窗口",
                "flash": "Alt+S 呼出窗口",
                "log": "Alt+R 呼出窗口",
                "capture": capture_store.WINDOW_DEF["hotkeyHint"],
            }[self.window_type],
            "defaultSavePath": settings_store.get_default_save_path(self.cfg),
            "layout": layout_store.load_layout(self.window_type),
            "theme": theme_store.get_theme(self.window_type),
            "attachmentsDir": self._attachments_dir(),
            "picgoUpload": settings_store.get_picgo_upload(),
        }

    def _attachments_dir(self):
        """取附件目录（供前端解析 ![[image]] 预览用）。"""
        try:
            from lib.backend import image_handler
            return image_handler.attachments_dir(self.cfg, _main.log_dir())
        except Exception as e:
            log_error("获取附件目录失败: %s" % e)
            return ""

    # ---- 三栏布局：读取 / 保存宽度比例与目录可见性 ----
    def get_layout(self):
        return layout_store.load_layout(self.window_type)

    def save_layout(self, layout):
        if not isinstance(layout, dict):
            return {"ok": False, "msg": "布局参数无效"}
        if not layout_store.save_layout(layout, self.window_type):
            return {"ok": False, "msg": "布局保存失败"}
        self.cfg["layout"] = layout
        log_info("三栏布局已保存(%s): %s" % (self.window_type, layout))
        return {"ok": True}

    # ---- 主题：读取 / 保存（per-window，每个窗口独立） ----
    def get_theme(self):
        return theme_store.get_theme(self.window_type)

    def save_theme(self, window_theme=None, editor=None, preview=None):
        ok, msg, theme = theme_store.save_theme(self.window_type, window_theme, editor, preview)
        log_info("主题已保存 (%s): %s" % (self.window_type, theme))
        return {"ok": ok, "msg": msg, "theme": theme}

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

    def move_workspace_folder(self, path, direction):
        """上移/下移工作区文件夹（direction: "up" | "down"）。"""
        ok, msg, folders = file_explorer.move_folder(path, direction)
        log_info("移动工作区文件夹(%s, %s): %s" % (path, direction, msg))
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

    def list_md_files(self, prefix="", limit=50):
        """列出工作区内 .md 文件名（用于 [[wikilink]] 自动补全）。

        prefix: 文件名前缀过滤（大小写不敏感）；limit: 最多返回数量。
        返回 {ok, items:[{name, path}], count}。
        跳过隐藏目录（.obsidian/.git/node_modules 等）。
        """
        try:
            roots = [f["path"] for f in workspace_store.folders()]
            prefix_lower = (prefix or "").strip().lower()
            skip_dirs = {".obsidian", ".git", ".trash", "node_modules", "__pycache__"}
            seen = set()
            items = []
            for root in roots:
                if not root or not os.path.isdir(root):
                    continue
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
                    for fn in filenames:
                        if not fn.lower().endswith(".md"):
                            continue
                        name = fn[:-3]
                        name_lower = name.lower()
                        if prefix_lower and not name_lower.startswith(prefix_lower):
                            continue
                        full = os.path.join(dirpath, fn)
                        norm = os.path.normcase(full)
                        if norm in seen:
                            continue
                        seen.add(norm)
                        items.append({"name": name, "path": full})
                        if len(items) >= limit:
                            return {"ok": True, "items": items, "count": len(items)}
            return {"ok": True, "items": items, "count": len(items)}
        except Exception as e:
            log_error("列出 .md 文件失败(%s): %s" % (prefix, e))
            return {"ok": False, "items": [], "count": 0, "msg": "列出文件失败"}

    def open_wikilink(self, filename):
        """点击 [[filename]] 时调用：按文件名精确查找 .md 文件。

        找到 → 返回 {ok, content, title, path, exists:True}
        未找到 → 在 Capture 目录新建空 .md 文件 → 返回 {ok, content:"", title, path, exists:False, created:True}
        """
        try:
            clean = (filename or "").strip()
            if not clean:
                return {"ok": False, "msg": "文件名为空"}
            roots = [f["path"] for f in workspace_store.folders()]
            skip_dirs = {".obsidian", ".git", ".trash", "node_modules", "__pycache__"}
            target_lower = clean.lower()
            for root in roots:
                if not root or not os.path.isdir(root):
                    continue
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
                    for fn in filenames:
                        if not fn.lower().endswith(".md"):
                            continue
                        name = fn[:-3]
                        if name.lower() == target_lower:
                            full = os.path.join(dirpath, fn)
                            res = file_explorer.open_file(full)
                            if res.get("ok"):
                                res["exists"] = True
                                return res
            # 未找到：在 Capture 目录新建文件
            cap_dir = os.path.dirname(capture_store.capture_file_path(self.cfg))
            page_store.ensure_dir(cap_dir)
            safe_name = page_store.sanitize_filename(clean) or clean
            new_path = page_store.unique_file(cap_dir, safe_name)
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(NEW_PAGE_DEFAULT_CONTENT)
            history_store.record_edit(new_path)
            log_info("Wikilink 新建文件: %s" % new_path)
            return {"ok": True, "content": NEW_PAGE_DEFAULT_CONTENT, "title": clean, "path": new_path,
                    "exists": False, "created": True}
        except Exception as e:
            log_error("open_wikilink 失败(%s): %s" % (filename, e))
            return {"ok": False, "msg": "打开链接失败：%s" % e}

    # ---- 收藏夹：收藏列表 / 添加 / 移除 / 上下移动 ----
    def favorites_list(self):
        try:
            return {"ok": True, "items": favorites_store.get_list()}
        except Exception as e:
            log_error("获取收藏失败: %s" % e)
            return {"ok": False, "items": [], "msg": "获取收藏失败"}

    def favorites_is_favorite(self, path):
        try:
            return {"ok": True, "fav": favorites_store.is_favorite(path)}
        except Exception as e:
            log_error("查询收藏状态失败(%s): %s" % (path, e))
            return {"ok": False, "fav": False, "msg": "查询收藏状态失败"}

    def favorites_add(self, path):
        ok, msg = favorites_store.add(path)
        log_info("收藏添加(%s): %s" % (path, msg))
        return {"ok": ok, "msg": msg}

    def favorites_remove(self, path):
        ok, msg = favorites_store.remove(path)
        log_info("收藏移除(%s): %s" % (path, msg))
        return {"ok": ok, "msg": msg}

    def favorites_move(self, path, direction):
        ok, msg = favorites_store.move(path, direction)
        log_info("收藏移动(%s, %s): %s" % (path, direction, msg))
        return {"ok": ok, "msg": msg}

    # ---- 资源管理器右键菜单：文件操作 ----
    def explorer_copy_text(self, text):
        """复制文本到剪贴板（复制文件名称 / 完整路径）。"""
        ok = file_ops.copy_text(text)
        log_info("资源管理器复制文本: %s" % ("成功" if ok else "失败"))
        return {"ok": ok, "msg": "" if ok else "复制到剪贴板失败"}

    def clipboard_get_text(self):
        """读取剪贴板文本（编辑器右键菜单「粘贴」用）。"""
        ok, text = file_ops.get_clipboard_text()
        return {"ok": ok, "text": text, "msg": "" if ok else "读取剪贴板失败"}

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

    def explorer_batch_delete(self, paths):
        """批量删除多个文件到回收站。paths 是路径列表。"""
        ok, msg, count = file_ops.batch_delete(paths)
        log_info("资源管理器批量删除: %d 个文件 (%s)" % (count, msg))
        return {"ok": ok, "msg": msg, "count": count}

    def explorer_batch_move(self, paths, dest_dir):
        """批量移动多个文件到目标目录。paths 是路径列表。"""
        ok, msg, count = file_ops.batch_move(paths, dest_dir)
        log_info("资源管理器批量移动: %d 个文件 -> %s (%s)" % (count, dest_dir, msg))
        return {"ok": ok, "msg": msg, "count": count}

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
        _main._page_seq += 1
        return "%s-%d-%d" % (self.window_type, int(time.time() * 1000), _main._page_seq)

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
                f.write(NEW_PAGE_DEFAULT_CONTENT)
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
        内容与磁盘一致时跳过写盘与历史记录（30 秒保险保存不污染“最近编辑”排序）。
        """
        try:
            path = self._page_target_path(page_id)
            if not path:
                return {"ok": False, "msg": "页面不存在"}
            text = content or ""
            old = None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    old = f.read()
            except Exception:
                old = None
            if old == text:
                return {"ok": True, "file": path}
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

    def save_tab_order(self, page_ids):
        """保存 Tab 拖拽排序结果（按页面 id 顺序重排 pages.json，重启按新顺序恢复）。"""
        try:
            ordered = list(page_ids) if page_ids else []
            ok = page_store.reorder_pages(ordered)
            log_info("保存 Tab 排序(%s): %s" % (self.window_type, "成功" if ok else "失败"))
            return ok
        except Exception as e:
            log_error("保存 Tab 排序失败(%s): %s" % (self.window_type, e))
            return False

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
        """前端轮询获取待打开的外部文件（仅 Capture 窗口消费，统一在此打开）。

        新实例带文件参数启动时写入 pending 队列，运行中的实例前端轮询此接口消费。
        """
        try:
            if self.window_type != "capture":
                return {"ok": True, "files": []}
            paths = file_assoc.take_pending_files()
            files = file_assoc.read_external_files(paths)
            if files:
                for f in files:
                    history_store.record_open(f.get("path", ""))
                log_info("打开外部文件 %d 个" % len(files))
                _main._set_last_active("capture")
                _main._safe_show_window(_main._windows.get("capture"))
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
        hide=True 保存后隐藏窗口；hide=False（同步）窗口保持打开。
        Tab 文件在聚合追加之后再记录历史，保证用户编辑的文件同秒内排最前。"""
        tab_ok, tab_msg = True, ""
        wrote = ""
        if page_id:
            try:
                path = self._page_target_path(page_id)
                if not path:
                    tab_ok = False
                    tab_msg = "页面不存在 · "
                else:
                    wrote = page_store.write_page_file(page_id, content)
                    tab_msg = ("已保存页面 %s · " % os.path.basename(wrote)) if wrote else ""
                    tab_ok = bool(wrote)
            except Exception as e:
                tab_ok = False
                tab_msg = "页面保存失败：%s · " % e
        agg_ok, agg_msg = self._aggregate_append(content)
        if wrote:
            history_store.record_edit(wrote)
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
    def get_picgo_upload(self):
        """图片上传开关（编辑窗口粘贴图片时实时读取，设置窗口改后立即生效）。"""
        return {"ok": True, "enabled": settings_store.get_picgo_upload()}

    def upload_image(self, data_url):
        log_info("图片上传开始（%s）" % self.window_type)
        try:
            from lib.backend import uploader
            from lib.backend import markdown as mdlib
            img = uploader.decode_base64_png(data_url)
            png = uploader.image_to_png_bytes(img)
            name = uploader.picgo_filename()
            ok, url, debug = uploader.upload_to_picgo(
                png, name, self.cfg["picgo_api"])
            if not ok:
                msg = debug.get("hint") or debug.get("service_status") or (
                    "上传失败（PicGo 返回格式异常，HTTP %s）"
                    % debug.get("status", "?"))
                mdlib.log_debug(
                    "==================\nUpload Failed\n==================\n%s"
                    % json.dumps(debug, ensure_ascii=False, indent=2),
                    _main.log_dir())
                log_error("图片上传失败: %s" % msg)
                return {"ok": False, "msg": msg}
            link = uploader.generate_markdown(url)
            mdlib.log_debug(
                "==================\nUpload Success\n==================\n"
                "Original File:\n%s\n\nRemote URL:\n%s\n\nMarkdown:\n%s\n"
                "==================" % (name, url, link),
                _main.log_dir())
            log_info("图片上传成功: %s" % url)
            return {"ok": True, "url": url, "markdown": link}
        except Exception as e:
            log_error("图片处理异常: %s" % e)
            return {"ok": False, "msg": "图片处理失败：%s" % e}

    def upload_clipboard_image(self):
        """剪贴板位图（截图）→ PicGo 上传 → 返回 Markdown 链接。

        前端对剪贴板位图无法用 getAsFile 取到文件数据（返回 null），
        必须由后端读剪贴板位图再上传。返回结构与 upload_image 一致。
        """
        log_info("剪贴板位图上传开始（%s）" % self.window_type)
        try:
            from lib.backend import uploader
            from lib.backend import markdown as mdlib
            img, err = uploader.clipboard_image()
            if img is None:
                return {"ok": False, "url": "", "markdown": "",
                        "msg": err or "剪贴板没有图片"}
            png = uploader.image_to_png_bytes(img)
            name = uploader.picgo_filename()
            ok, url, debug = uploader.upload_to_picgo(
                png, name, self.cfg["picgo_api"])
            if not ok:
                msg = debug.get("hint") or debug.get("service_status") or (
                    "上传失败（PicGo 返回格式异常，HTTP %s）"
                    % debug.get("status", "?"))
                mdlib.log_debug(
                    "==================\nUpload Failed (clipboard)\n"
                    "==================\n%s"
                    % json.dumps(debug, ensure_ascii=False, indent=2),
                    _main.log_dir())
                log_error("剪贴板图片上传失败: %s" % msg)
                return {"ok": False, "url": "", "markdown": "", "msg": msg}
            link = uploader.generate_markdown(url)
            mdlib.log_debug(
                "==================\nUpload Success (clipboard)\n"
                "==================\nOriginal File:\n%s\n\nRemote URL:\n%s\n\n"
                "Markdown:\n%s\n==================" % (name, url, link),
                _main.log_dir())
            log_info("剪贴板图片上传成功: %s" % url)
            return {"ok": True, "url": url, "markdown": link}
        except Exception as e:
            log_error("剪贴板图片处理异常: %s" % e)
            return {"ok": False, "url": "", "markdown": "", "msg": "图片处理失败：%s" % e}

    # ---- 富文本粘贴：解析 HTML → 保存图片 → 返回 Obsidian Markdown ----
    def paste_html(self, content):
        """解析剪贴板 HTML 富文本，提取图片保存为附件，返回 Obsidian Markdown。

        content: HTML 字符串（来自前端 paste 事件的 text/html）。
        返回 {"ok": bool, "markdown": str, "imageCount": int, "msg": str}。

        流程：JS clipboard html → 本方法 → clipboard_parser 解析 →
        image_handler 保存图片 → html_converter 转 Markdown → 返回。
        图片失败不影响文字粘贴。
        """
        try:
            from lib.backend import clipboard_parser, html_converter, image_handler
            html = content or ""
            if not html.strip():
                return {"ok": False, "markdown": "", "imageCount": 0, "msg": "无 HTML 内容"}
            nodes = clipboard_parser.parse_html(html)
            if not nodes:
                return {"ok": False, "markdown": "", "imageCount": 0, "msg": "HTML 解析无内容"}
            att_dir = self._attachments_dir()
            if not att_dir:
                return {"ok": False, "markdown": "", "imageCount": 0, "msg": "附件目录不可用"}
            # 保存所有图片（按 src 去重）
            image_map = {}
            image_nodes = [n for n in nodes if n["type"] == "image"]
            for node in image_nodes:
                src = node.get("src", "")
                if src in image_map:
                    continue
                fn = image_handler.save_image(src, att_dir, _main.log_dir())
                if fn:
                    image_map[src] = fn
            md = html_converter.nodes_to_markdown(nodes, image_map)
            if not md.strip():
                return {"ok": False, "markdown": "", "imageCount": len(image_map),
                        "msg": "转换后无内容"}
            log_info("paste_html 成功(%s): %d 节点, %d/%d 图片已保存"
                     % (self.window_type, len(nodes), len(image_map), len(image_nodes)))
            return {"ok": True, "markdown": md, "imageCount": len(image_map), "msg": ""}
        except Exception as e:
            log_error("paste_html 失败: %s" % e)
            return {"ok": False, "markdown": "", "imageCount": 0,
                    "msg": "HTML 粘贴失败：%s" % e}

    # ---- 截图粘贴：剪贴板位图 → 附件 → Obsidian Markdown 引用 ----
    def paste_clipboard_image(self):
        """保存剪贴板位图（截图）为附件，返回 Obsidian Markdown 引用。

        返回 {"ok": bool, "markdown": str, "msg": str}。
        处理 CF_BITMAP/CF_DIB/CF_DIBV5（Pillow ImageGrab）。
        """
        try:
            from lib.backend import image_handler
            att_dir = self._attachments_dir()
            if not att_dir:
                return {"ok": False, "markdown": "", "msg": "附件目录不可用"}
            fn = image_handler.save_clipboard_bitmap(att_dir, _main.log_dir())
            if fn:
                log_info("paste_clipboard_image 成功(%s): %s" % (self.window_type, fn))
                return {"ok": True, "markdown": "![[%s]]" % fn, "msg": ""}
            return {"ok": False, "markdown": "", "msg": "剪贴板没有图片"}
        except Exception as e:
            log_error("paste_clipboard_image 失败: %s" % e)
            return {"ok": False, "markdown": "", "msg": "图片保存失败：%s" % e}

    # ---- 附件 data URL：供预览区 ![[image]] 渲染（WebView2 跨域 file:// 兜底）----
    def get_attachment_data_url(self, filename):
        """读取附件文件并返回 data URL（base64），供预览区 <img> 加载。

        filename: 附件文件名（不含路径）。返回 {"ok": bool, "dataUrl": str}。
        跨域 file:// 在 pywebview HTTP 模式下不可用，改用 data URL 保证预览。
        """
        try:
            if not filename:
                return {"ok": False, "dataUrl": ""}
            # 安全：只取文件名，禁止路径穿越
            safe = os.path.basename(filename)
            if safe != filename:
                return {"ok": False, "dataUrl": ""}
            att_dir = self._attachments_dir()
            if not att_dir:
                return {"ok": False, "dataUrl": ""}
            path = os.path.join(att_dir, safe)
            if not os.path.isfile(path):
                return {"ok": False, "dataUrl": ""}
            import base64
            ext = os.path.splitext(safe)[1].lower()
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
                ".svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")
            with open(path, "rb") as f:
                data = f.read()
            data_url = "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
            return {"ok": True, "dataUrl": data_url}
        except Exception as e:
            log_error("get_attachment_data_url 失败(%s): %s" % (filename, e))
            return {"ok": False, "dataUrl": ""}

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
        w = _main._windows.get(self.window_type)
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

    # ---- 在默认浏览器中打开 URL ----
    def open_url(self, url):
        """用系统默认浏览器打开 URL（http/https 协议）。"""
        import webbrowser
        if not url or not isinstance(url, str):
            return {"ok": False, "msg": "无效的 URL"}
        url = url.strip()
        if not url.startswith(("http://", "https://", "mailto:", "tel:")):
            return {"ok": False, "msg": "不支持的协议：%s" % url}
        try:
            webbrowser.open(url)
            log_info("已在浏览器打开: %s" % url)
            return {"ok": True}
        except Exception as e:
            log_error("打开 URL 失败(%s): %s" % (url, e))
            return {"ok": False, "msg": "打开失败：%s" % e}

    # ---- 打开工具箱窗口 ----
    def open_tools(self):
        if _main._tools_window is not None:
            # 记录来源窗口，使工具箱主题与打开它的窗口保持一致
            if _main._tools_api is not None:
                _main._tools_api.source_window = self.window_type
            _main._safe_show_window(_main._tools_window)
            # 立即按来源窗口重应用主题（工具箱窗口常驻，避免停留在上次来源主题）
            try:
                _main._tools_window.evaluate_js(
                    "if(window.ThemeManager) window.ThemeManager.load();")
            except Exception as e:
                log_error("重应用工具箱主题失败: %s" % e)
            log_info("打开工具箱窗口（来源: %s）" % self.window_type)
        return True

    def open_canvas(self):
        if _main._canvas_window is not None:
            _main._safe_show_window(_main._canvas_window)
            log_info("打开画布窗口（来源: %s）" % self.window_type)
        return True

    # ---- 打开 To Do 任务窗口（复用 tools/to-do 模块） ----
    def open_todo(self):
        from lib.modules import todo_window
        ok = todo_window.show()
        log_info("打开 To Do 窗口（来源: %s，成功: %s）" % (self.window_type, ok))
        return ok

    # ---- 导入当前页签 Markdown 到 Drawnix 画布（思维导图） ----
    def import_markdown_to_canvas(self, md_text):
        try:
            if _main._canvas_server is None:
                raise RuntimeError("画布 HTTP 服务未启动")
            # markdown 文本交给 Drawnix 官方 parseMarkdownToDrawnix 解析为思维导图
            _main._canvas_server.submit_import({"markdown": md_text or ""})
            if _main._canvas_window is not None:
                _main._safe_show_window(_main._canvas_window)
            log_info("导入 Markdown 到画布成功（来源: %s）" % self.window_type)
            return {"ok": True, "msg": "已导入到画布"}
        except Exception as e:
            log_error("导入 Markdown 到画布失败: %s" % e)
            return {"ok": False, "msg": "导入失败：%s" % e}

    # ---- 功能区：获取 / 排序 勾选工具（转发到 ToolApi） ----
    def get_pinned_tools(self):
        return ToolApi().get_pinned_tools()

    def save_pinned_order(self, order_ids):
        return ToolApi().save_pinned_order(order_ids)

    def save_pin(self, tool_id, pinned):
        return ToolApi().save_pin(tool_id, pinned)

    # ---- 打开设置窗口 ----
    def open_settings(self):
        if _main._settings_window is not None:
            # 记录来源窗口，使设置窗主题与打开它的窗口保持一致
            if _main._settings_api is not None:
                _main._settings_api.source_window = self.window_type
            _main._safe_show_window(_main._settings_window)
            # 每次打开都按来源窗口重应用主题（设置窗是单例常驻，init 只跑一次）
            try:
                _main._settings_window.evaluate_js(
                    "if(window.applyWindowThemeToSelf) "
                    "window.applyWindowThemeToSelf('%s');" % self.window_type)
            except Exception as e:
                log_error("重应用设置窗主题失败: %s" % e)
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
        self.source_window = "flash"   # 打开设置窗口的来源窗口（用于让设置窗主题与来源一致）

    def get_source_window(self):
        """返回打开设置窗口的来源窗口类型（flash/inbox/log/capture）。"""
        return {"ok": True, "windowType": self.source_window}

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

    # ---- 图片上传开关（PicGo / 附件） ----
    def get_picgo_upload(self):
        return {"ok": True, "enabled": settings_store.get_picgo_upload()}

    def save_picgo_upload(self, enabled):
        """保存图片上传开关：True=粘贴图片走 PicGo（→ Cloudflare），False=存本地附件。"""
        if not settings_store.save_picgo_upload(enabled):
            return {"ok": False, "msg": "设置写入失败"}
        log_info("设置窗口: 图片上传开关已更新: %s"
                 % ("PicGo" if enabled else "附件"))
        return {"ok": True, "enabled": bool(enabled)}

    # ---- 主题：选项列表 / 读取 / 保存（per-window 四个页签） ----
    def get_themes(self):
        return {"ok": True,
                "themes": theme_store.get_theme_options(),
                "allThemes": theme_store.get_theme()}

    def get_theme(self, window_type="flash"):
        return theme_store.get_theme(window_type)

    def save_theme(self, window_type="flash", window_theme=None, editor=None, preview=None):
        ok, msg, theme = theme_store.save_theme(window_type, window_theme, editor, preview)
        log_info("设置窗口: 主题已保存 (%s): %s" % (window_type, theme))
        return {"ok": ok, "msg": msg, "theme": theme, "windowType": window_type}

    # ---- To Do Microsoft 同步：读取 / 保存 client_id（用户覆盖内置值） ----
    def get_microsoft_config(self):
        """返回 To Do 微软同步配置：用户覆盖优先，否则内置默认。"""
        override = settings_store.get_microsoft_config()
        builtin_client, builtin_tenant = "", "consumers"
        try:
            p = _main.resource_path(os.path.join("tools", "to-do", "config.json"))
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    ms = (json.load(f) or {}).get("microsoft") or {}
                builtin_client = ms.get("client_id") or ""
                builtin_tenant = ms.get("tenant") or "consumers"
        except Exception:
            pass
        return {
            "ok": True,
            "client_id": override.get("client_id") or builtin_client,
            "tenant": override.get("tenant") or builtin_tenant,
            "has_override": bool(override.get("client_id")),
            "builtin_client_id": builtin_client,
        }

    def save_microsoft_config(self, client_id=None, tenant=None):
        """保存用户自定义 Microsoft client_id（空字符串 = 恢复内置默认）。"""
        if not settings_store.save_microsoft_config(client_id, tenant):
            return {"ok": False, "msg": "配置写入失败"}
        log_info("设置窗口: To Do Microsoft 配置已更新")
        return {"ok": True}


class ToolApi:
    """工具箱窗口 js_api：工具列表 / 排序保存 / 派发执行。

    工具配置来源：优先读 %APPDATA%\\Obsidian-upload\\tools.json（用户可写，保存排序），
    缺失时回退到打包内置 tools/tools.json，最后回退代码内置默认。
    执行：把工具命令通过 evaluate_js 派发给最近激活的编辑窗口（_last_active）。
    """

    def __init__(self):
        self.user_path = os.path.join(_main.log_dir(), "tools.json")
        self.builtin_path = _main.resource_path(os.path.join("tools", "tools.json"))
        self.source_window = "flash"   # 打开工具箱的来源窗口，使主题与打开它的窗口一致

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
        """返回工具列表（dict 列表），自动合并内置配置中的新工具到用户配置。

        优先读取用户配置（%APPDATA%\\Obsidian-upload\\tools.json），
        再读取内置配置（tools/tools.json），将内置有但用户缺失的新工具追加到用户配置并保存。
        """
        user_tools = None
        # 1. 读取用户配置
        if os.path.exists(self.user_path):
            try:
                with open(self.user_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tools = data.get("tools") if isinstance(data, dict) else data
                if isinstance(tools, list) and tools:
                    user_tools = tools
            except Exception as e:
                log_warn("读取用户工具配置失败 %s: %s" % (self.user_path, e))
        # 2. 读取内置配置
        builtin_tools = None
        if os.path.exists(self.builtin_path):
            try:
                with open(self.builtin_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tools = data.get("tools") if isinstance(data, dict) else data
                if isinstance(tools, list) and tools:
                    builtin_tools = tools
            except Exception as e:
                log_warn("读取内置工具配置失败 %s: %s" % (self.builtin_path, e))
        # 3. 合并：内置中有但用户缺失的工具，追加到用户配置
        if user_tools is not None and builtin_tools is not None:
            user_ids = {t.get("id") for t in user_tools}
            new_tools = [t for t in builtin_tools if t.get("id") not in user_ids]
            if new_tools:
                user_tools.extend(new_tools)
                self._save(user_tools)
                log_info("自动合并 %d 个新工具到用户配置: %s"
                         % (len(new_tools), ", ".join(t.get("id", "") for t in new_tools)))
            return user_tools
        if user_tools is not None:
            return user_tools
        if builtin_tools is not None:
            return builtin_tools
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
            self._ensure_pin_fields(tools)
            return sorted(tools, key=lambda t: t.get("order", 999))
        except Exception as e:
            log_error("获取工具列表失败: %s" % e)
            return self._builtin_default()["tools"]

    def _ensure_pin_fields(self, tools):
        """补齐勾选字段：pinned（是否显示在保存按钮左侧功能区）+ pinned_order（功能区排序）。"""
        for t in tools:
            t.setdefault("pinned", False)
            t.setdefault("pinned_order", 0)

    def _broadcast_refresh_pinbar(self):
        """勾选状态变化后通知所有编辑器窗口刷新功能区。"""
        for key, w in list(_main._windows.items()):
            try:
                w.evaluate_js("window.__reloadPinToolbar && window.__reloadPinToolbar()")
            except Exception:
                pass

    # ---- 前端：勾选 / 取消勾选工具（决定是否显示在功能区） ----
    def save_pin(self, tool_id, pinned):
        try:
            tools = self._load()
            self._ensure_pin_fields(tools)
            pinned = bool(pinned)
            changed = False
            for t in tools:
                if str(t.get("id", "")) == str(tool_id):
                    t["pinned"] = pinned
                    if pinned and not t.get("pinned_order"):
                        t["pinned_order"] = max([x.get("pinned_order", 0) for x in tools] or [0]) + 1
                    if not pinned:
                        t["pinned_order"] = 0
                    changed = True
                    break
            if not changed:
                return False
            ok = self._save(tools)
            log_info("工具勾选已保存(%s→%s): %s" % (tool_id, pinned, "成功" if ok else "失败"))
            if ok:
                self._broadcast_refresh_pinbar()
            return ok
        except Exception as e:
            log_error("保存工具勾选失败: %s" % e)
            return False

    # ---- 前端（编辑器窗口）：获取功能区工具列表（按 pinned_order 排序） ----
    def get_pinned_tools(self):
        try:
            tools = self._load()
            self._ensure_pin_fields(tools)
            return sorted([t for t in tools if t.get("pinned")],
                          key=lambda t: t.get("pinned_order", 0))
        except Exception as e:
            log_error("获取功能区工具失败: %s" % e)
            return []

    # ---- 主题（工具箱窗口只读；跟随打开它的来源窗口，保证主题一致） ----
    def get_theme(self):
        return theme_store.get_theme(self.source_window)

    # ---- 前端（编辑器窗口）：保存功能区拖动排序 ----
    def save_pinned_order(self, order_ids):
        try:
            order_map = {str(i): n + 1 for n, i in enumerate(order_ids)}
            tools = self._load()
            for t in tools:
                o = order_map.get(str(t.get("id", "")))
                if o:
                    t["pinned_order"] = o
            ok = self._save(tools)
            log_info("功能区排序已保存: %s" % ("成功" if ok else "失败"))
            return ok
        except Exception as e:
            log_error("保存功能区排序失败: %s" % e)
            return False

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
        key = _main._last_active if _main._last_active in _main._windows else "flash"
        w = _main._windows.get(key)
        if w is None:
            return {"ok": False, "msg": "没有可用的编辑窗口"}
        try:
            w.evaluate_js("window.__runTool && window.__runTool(%s)" % json.dumps(tool_id))
            log_info("工具箱派发工具: %s → %s" % (tool_id, key))
            return {"ok": True, "msg": "已在 %s 执行" % _main.WINDOW_TITLES[key]}
        except Exception as e:
            log_error("派发工具失败(%s → %s): %s" % (tool_id, key, e))
            return {"ok": False, "msg": "执行失败：%s" % e}

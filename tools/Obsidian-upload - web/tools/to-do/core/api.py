"""前端 js_api 桥接层（pywebview）。

把 UI 的调用转接到 TaskManager / SyncEngine / MicrosoftAuth，
不承载业务逻辑（业务在 manager / sync_engine）。
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

from adapters.microsoft.auth import MicrosoftAuth
from core import __version__
from core.manager import TaskManager
from core.sync_engine import SyncEngine, SyncBusyError
from core.models import Task, TaskAttachment, TaskStats

log = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _file_url(path: str) -> str:
    """本地路径 -> file:// URL（pywebview file:// 页面可直接作为 img src）。"""
    if not path:
        return ""
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        return ""
    return "file:///" + p.replace("\\", "/")


class TodoApi:
    """暴露给 todo.html 的 js_api。注意：参数名禁止使用 window。"""

    def __init__(
        self,
        manager: TaskManager,
        engine: SyncEngine,
        auth: Optional[MicrosoftAuth] = None,
        config: Optional[dict] = None,
    ):
        self._manager = manager
        self._engine = engine
        self._auth = auth
        self._config = config or {}

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    def app_info(self) -> dict:
        return {
            "name": self._config.get("app_name", "Leo Todo"),
            "version": __version__,
            "auto_sync_on_start": bool(
                (self._config.get("sync") or {}).get("auto_sync_on_start", True)
            ),
            "sources": self._engine.adapters(),
        }

    # ------------------------------------------------------------------
    # 任务查询
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        status: Optional[str] = None,
        include_deleted: bool = False,
        project: Optional[str] = None,
        priority: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[dict]:
        tasks = self._manager.list_tasks(
            status=status, include_deleted=include_deleted, project=project,
            priority=priority, tag=tag, search=search,
        )
        return [self._task_view(t) for t in tasks]

    def get_task(self, task_id: str) -> Optional[dict]:
        task = self._manager.get_task(task_id)
        return self._task_view(task) if task else None

    def list_deleted(self) -> List[dict]:
        return [self._task_view(t) for t in self._manager.list_deleted()]

    def search(self, query: str) -> List[dict]:
        if not query:
            return []
        return self._task_view(self._manager.list_tasks(search=query))  # type: ignore

    def stats(self) -> dict:
        return self._manager.stats().to_dict()

    def projects(self) -> List[str]:
        return self._manager.projects()

    def tags(self) -> List[str]:
        return self._manager.tags()

    # ------------------------------------------------------------------
    # 任务操作
    # ------------------------------------------------------------------

    def create_task(self, data: dict) -> Optional[dict]:
        task = Task.from_dict(data or {})
        task = self._manager.create_task(task)
        return self._task_view(task)

    def update_task(self, task_id: str, fields: dict) -> Optional[dict]:
        task = self._manager.update_task(task_id, fields or {})
        return self._task_view(task) if task else None

    def complete_task(self, task_id: str, completed: bool = True) -> Optional[dict]:
        task = self._manager.complete_task(task_id, bool(completed))
        return self._task_view(task) if task else None

    def delete_task(self, task_id: str) -> Optional[dict]:
        task = self._manager.soft_delete(task_id)
        return self._task_view(task) if task else None

    def restore_task(self, task_id: str) -> Optional[dict]:
        task = self._manager.restore_task(task_id)
        return self._task_view(task) if task else None

    # ------------------------------------------------------------------
    # 附件
    # ------------------------------------------------------------------

    def list_attachments(self, task_id: str) -> List[dict]:
        attachments = self._manager.list_attachments(task_id)
        return [self._attachment_view(a) for a in attachments]

    def add_attachment_data(
        self, task_id: str, file_name: str, base64_data: str
    ) -> Optional[dict]:
        """接收 JS FileReader 上传的附件（base64）。"""
        store = self._manager.attachment_store
        if store is None:
            return None
        try:
            raw = base64.b64decode(base64_data.split(",", 1)[-1])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"附件编码无效：{exc}")
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise ValueError("附件超过 15MB 限制")
        file_type = _guess_type(file_name, raw)
        path = store.save_bytes(task_id, file_name, raw)
        att = TaskAttachment(
            task_id=task_id,
            file_name=file_name,
            file_type=file_type,
            source="leo",
            local_path=path,
        )
        self._manager.add_attachment_record(att)
        return self._attachment_view(att)

    def remove_attachment(self, attachment_id: str) -> bool:
        self._manager.remove_attachment(attachment_id)
        return True

    # ------------------------------------------------------------------
    # 同步
    # ------------------------------------------------------------------

    def sync(self, source: Optional[str] = None) -> dict:
        try:
            reports = self._engine.sync(source=source)
            return {"ok": True, "reports": [r.to_dict() for r in reports]}
        except SyncBusyError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            log.exception("同步失败")
            return {"ok": False, "error": str(exc)}

    def sync_busy(self) -> bool:
        return self._engine.is_syncing

    def last_sync(self, source: str = "microsoft") -> str:
        return self._manager._db.get_meta(f"last_sync.{source}")

    # ------------------------------------------------------------------
    # Microsoft 认证
    # ------------------------------------------------------------------

    def ms_status(self) -> dict:
        log.info("ms_status: 被调用, auth=%s", self._auth is not None)
        if self._auth is None:
            log.info("ms_status: auth 为 None（Microsoft 适配器未启用）")
            return {"enabled": False, "logged_in": False, "message": "未配置 Microsoft"}
        try:
            logged_in = self._auth.is_logged_in()
            log.info("ms_status: is_logged_in 返回=%s", logged_in)
            return {"enabled": True, "logged_in": logged_in}
        except Exception as exc:
            log.warning("ms_status 异常: %s", exc)
            import traceback
            traceback.print_exc()
            return {"enabled": True, "logged_in": False, "error": str(exc)}

    def ms_login(self) -> dict:
        if self._auth is None:
            return {"ok": False, "message": "未配置 Microsoft"}
        try:
            self._auth.login(mode="interactive")
            return {"ok": True, "message": "Microsoft 登录成功"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def ms_device_start(self) -> dict:
        """设备码流第一步：返回用户需要访问的 URL 与验证码。"""
        if self._auth is None:
            return {"ok": False, "message": "未配置 Microsoft"}
        try:
            flow = self._auth.initiate_device_flow()
            return {
                "ok": True,
                "verification_uri": flow.get("verification_uri", ""),
                "user_code": flow.get("user_code", ""),
                "message": flow.get("message", ""),
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def ms_device_wait(self) -> dict:
        """设备码流第二步：阻塞轮询授权结果。"""
        if self._auth is None:
            return {"ok": False, "message": "未配置 Microsoft"}
        try:
            self._auth.wait_device_flow()
            return {"ok": True, "message": "Microsoft 登录成功"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def copy_text(self, text) -> dict:
        """复制文本到系统剪贴板（Win32，支持 Unicode 中文）。"""
        try:
            import ctypes
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002
            data = (text or "").encode("utf-16-le")
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            # 声明 Win32 函数签名，确保 64 位指针不被截断
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype = ctypes.c_int
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = ctypes.c_int
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = ctypes.c_int
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_int
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            kernel32.GlobalFree.restype = ctypes.c_void_p
            if not user32.OpenClipboard(0):
                return {"ok": False, "message": "打开剪贴板失败"}
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data) + 2)
                if not h_mem:
                    return {"ok": False, "message": "内存分配失败"}
                ptr = kernel32.GlobalLock(h_mem)
                if not ptr:
                    kernel32.GlobalFree(h_mem)
                    return {"ok": False, "message": "内存锁定失败"}
                try:
                    ctypes.memmove(ptr, data, len(data))
                    ctypes.c_uint16.from_address(ptr + len(data)).value = 0
                finally:
                    kernel32.GlobalUnlock(h_mem)
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            finally:
                user32.CloseClipboard()
            return {"ok": True}
        except Exception as exc:
            log.warning("copy_text 失败: %s", exc)
            return {"ok": False, "message": str(exc)}

    def open_device_uri(self, url) -> dict:
        """用系统浏览器（优先 Google Chrome）打开设备码登录网址。"""
        try:
            import os
            import subprocess
            candidates = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            for path in candidates:
                if os.path.isfile(path):
                    subprocess.Popen([path, url])
                    return {"ok": True, "browser": "chrome"}
            os.startfile(url)
            return {"ok": True, "browser": "default"}
        except Exception as exc:
            log.warning("open_device_uri 失败: %s", exc)
            return {"ok": False, "message": str(exc)}

    def ms_logout(self) -> bool:
        if self._auth is not None:
            self._auth.logout()
        return True

    def ms_save_cache(self) -> dict:
        """强制保存 Microsoft 令牌缓存到磁盘。"""
        if self._auth is not None:
            try:
                self._auth.save_cache()
                return {"ok": True, "message": "令牌缓存已保存"}
            except Exception as exc:
                return {"ok": False, "message": str(exc)}
        return {"ok": False, "message": "未配置 Microsoft"}

    # ------------------------------------------------------------------
    # 视图转换
    # ------------------------------------------------------------------

    def _task_view(self, task: Task) -> dict:
        view = task.to_dict()
        view["attachments"] = [
            self._attachment_view(a) for a in self._manager.list_attachments(task.id)
        ]
        return view

    def _attachment_view(self, att: TaskAttachment) -> dict:
        view = att.to_dict()
        view["preview_url"] = _file_url(att.local_path) if att.is_image else ""
        view["size"] = _file_size(att.local_path)
        return view


def _guess_type(file_name: str, data: bytes) -> str:
    name = (file_name or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".gif"):
        return "image/gif"
    if name.endswith(".webp"):
        return "image/webp"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/octet-stream"


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

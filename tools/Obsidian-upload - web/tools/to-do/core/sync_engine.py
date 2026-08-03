"""同步引擎：双向同步编排。

架构：
    Leo Todo DB  <->  SyncEngine  <->  TodoAdapter(各外部来源)  <->  外部系统

同步规则：
  - 全量 vs 增量：增量由各来源 Adapter 自行决定拉取范围；
  - 新增/更新：按 source_id 判断，外部存在 -> 更新，不存在 -> 新增；
  - 冲突：Last-Write-Wins，比较 updated_at（UTC ISO，字典序可比）；
  - 删除：本地一律软删除（status=deleted，绝不物理删除），
          本地删除会推送 DELETE 到外部；外部删除 -> 本地软删除。

TodoAdapter 协议（外部来源需要实现）：
    source                      来源标识（如 "microsoft"）
    list_tasks()                拉取全部外部任务，返回 list[Task]（已映射）
    list_attachments(task)      返回附件元数据 list[dict]（含 id/name/...）
    download_attachment(task, meta, dest_path)  把附件下载到 dest_path
    create_task(task)           在外部创建，返回带 source_id/source_list_id 的 Task
    update_task(task)           在外部更新
    delete_task(task)           在外部删除
    push_attachment(task, attachment)  本地附件上传外部（可选）
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Dict, List, Optional

from core.models import (
    SYNC_SYNCED, SYNC_LOCAL, SYNC_PENDING_PUSH, SYNC_PENDING_DELETE, SYNC_ERROR,
    SOURCE_LEO,
    Task, TaskAttachment, SyncReport, now_iso,
)
from core.manager import TaskManager

log = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


class TodoAdapter:
    """外部来源适配器接口。子类必须实现 source / list_tasks / create/update/delete。"""

    source: str = ""

    def list_tasks(self) -> List[Task]:
        raise NotImplementedError

    def list_attachments(self, task: Task) -> List[dict]:
        return []

    def download_attachment(self, task: Task, meta: dict, dest_path: str) -> int:
        raise NotImplementedError

    def create_task(self, task: Task) -> Task:
        raise NotImplementedError

    def update_task(self, task: Task) -> Task:
        raise NotImplementedError

    def delete_task(self, task: Task) -> None:
        raise NotImplementedError

    def push_attachment(self, task: Task, attachment: TaskAttachment) -> None:
        raise NotImplementedError


class SyncEngine:
    """同步引擎：管理多个外部来源适配器，执行双向同步。"""

    def __init__(self, manager: TaskManager):
        self._manager = manager
        self._adapters: Dict[str, TodoAdapter] = {}
        self._lock = threading.RLock()
        self._syncing = False

    def register_adapter(self, adapter: TodoAdapter) -> None:
        if not adapter.source:
            raise ValueError("adapter 必须声明 source")
        self._adapters[adapter.source] = adapter
        log.info("注册适配器：%s", adapter.source)

    def adapters(self) -> List[str]:
        return list(self._adapters.keys())

    @property
    def is_syncing(self) -> bool:
        return self._syncing

    # ------------------------------------------------------------------
    # 同步入口
    # ------------------------------------------------------------------

    def sync(
        self,
        source: Optional[str] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> List[SyncReport]:
        """执行同步。source 为空则同步全部已注册来源。"""
        with self._lock:
            if self._syncing:
                raise SyncBusyError("同步进行中，请稍候")
            self._syncing = True
        try:
            sources = [source] if source else list(self._adapters.keys())
            reports = []
            for src in sources:
                adapter = self._adapters.get(src)
                if adapter is None:
                    raise ValueError(f"未注册的适配器：{src}")
                report = self._sync_source(adapter, progress)
                reports.append(report)
            return reports
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # 单来源双向同步
    # ------------------------------------------------------------------

    @staticmethod
    def _note(progress: Optional[ProgressCallback], message: str) -> None:
        log.info(message)
        if progress:
            try:
                progress(message)
            except Exception:
                pass

    def _sync_source(self, adapter: TodoAdapter, progress: Optional[ProgressCallback]) -> SyncReport:
        report = SyncReport(
            source=adapter.source,
            started_at=now_iso(),
        )
        self._note(progress, f"开始同步 {adapter.source} ...")

        external = adapter.list_tasks()
        report.pulled = len(external)
        self._note(progress, f"拉取到 {len(external)} 个外部任务")

        # --- 拉取阶段：外部 -> 本地 -------------------------------------
        seen: set = set()
        for ext in external:
            if not ext.source_id:
                continue
            seen.add(ext.source_id)
            local = self._manager.find_by_source_id(ext.source, ext.source_id)
            if local is None:
                ext.sync_status = SYNC_SYNCED
                self._manager.create_task(ext)
                report.created += 1
                self._pull_attachments(adapter, ext, report)
            else:
                local_ts = local.updated_at or ""
                ext_ts = ext.updated_at or ""
                # Last-Write-Wins：外部较新则覆盖本地
                if ext_ts > local_ts:
                    self._manager.apply_external(local.id, ext)
                    report.updated += 1
                    self._pull_attachments(adapter, ext, report)
                elif local.sync_status in (SYNC_ERROR,):
                    # 本地推送失败过，外部是最新依据，直接对齐
                    self._manager.apply_external(local.id, ext)
                    report.updated += 1

        # 外部删除检测：本地已同步任务不在外部列表 -> 外部已删 -> 本地软删除
        for local in self._manager.list_synced_for_source(adapter.source):
            if local.source_id not in seen:
                self._manager.soft_delete(local.id, push=False)
                report.deleted_local += 1

        # --- 推送阶段：本地 -> 外部 -------------------------------------
        for local in self._manager.list_pending(source=adapter.source):
            if local.sync_status == SYNC_PENDING_DELETE:
                self._push_delete(adapter, local, report)
            else:
                self._push_upsert(adapter, local, report)

        report.finished_at = now_iso()
        self._manager._db.set_meta(f"last_sync.{adapter.source}", report.finished_at)
        self._note(progress, f"同步完成：新增 {report.created}，更新 {report.updated}，"
                             f"删除 {report.deleted_local + report.pushed_delete}")
        return report

    # ------------------------------------------------------------------
    # 拉取附件
    # ------------------------------------------------------------------

    def _pull_attachments(self, adapter: TodoAdapter, task: Task, report: SyncReport) -> None:
        if not getattr(adapter, "list_attachments", None):
            return
        try:
            metas = adapter.list_attachments(task)
        except Exception as exc:  # 附件失败不影响任务本体
            report.errors.append(f"拉取附件列表失败 {task.id}: {exc}")
            log.warning("拉取附件列表失败 %s: %s", task.id, exc)
            return

        store = self._manager.attachment_store
        keep_urls = set()
        for meta in metas:
            source_url = meta.get("source_url") or ""
            if not source_url:
                continue
            keep_urls.add(source_url)
            if self._manager._db.find_attachment_by_source_url(source_url):
                continue
            if not store or not store.is_image_ext(meta.get("name") or ""):
                continue
            if meta.get("size", 0) > self._max_attachment_bytes(meta.get("size", 0)):
                continue
            try:
                dest = store.resolve_path(task.id, meta.get("name") or "attachment")
                adapter.download_attachment(task, meta, dest)
                self._manager.add_attachment_record(TaskAttachment(
                    task_id=task.id,
                    file_name=meta.get("name") or "",
                    file_type=meta.get("content_type") or "",
                    source=adapter.source,
                    source_url=source_url,
                    local_path=dest,
                ))
                report.attachments_pulled += 1
            except Exception as exc:
                report.errors.append(f"下载附件失败 {task.id}/{meta.get('name')}: {exc}")
                log.warning("下载附件失败 %s/%s: %s", task.id, meta.get("name"), exc)
                store.delete_file(dest)

        # 清理：外部已删除的附件 -> 本地删除记录 + 文件
        for removed_id in self._manager._db.prune_attachments_not_in(task.id, keep_urls):
            removed = self._manager.get_attachment(removed_id)
            if removed and store:
                store.delete_file(removed.local_path)

    @staticmethod
    def _max_attachment_bytes(size: int) -> int:
        # 单附件限制 10MB
        return 10 * 1024 * 1024

    # ------------------------------------------------------------------
    # 推送
    # ------------------------------------------------------------------

    def _push_upsert(self, adapter: TodoAdapter, local: Task, report: SyncReport) -> None:
        try:
            if local.source_id:
                # 有外部 id：走更新（适配器负责解析列表）
                adapter.update_task(local)
                self._manager.mark_synced(local.id)
                report.pushed_update += 1
            else:
                created = adapter.create_task(local)
                self._manager.set_source_ids(
                    local.id, created.source_id or "", created.source_list_id or ""
                )
                # 本地任务推送成功后归属该来源，纳入双向同步
                if local.source == SOURCE_LEO:
                    self._manager._db.update_task(
                        local.id, {"source": adapter.source}
                    )
                self._manager.mark_synced(local.id)
                fresh = self._manager.get_task(local.id)
                report.pushed_create += 1
                if fresh:
                    self._push_local_attachments(adapter, fresh, report)
        except Exception as exc:
            report.errors.append(f"推送任务失败 {local.id}: {exc}")
            self._manager.mark_error(local.id, str(exc))

    def _push_delete(self, adapter: TodoAdapter, local: Task, report: SyncReport) -> None:
        if not local.source_id or not local.source_list_id:
            # 无外部 id，纯本地任务，直接结束
            self._manager.mark_synced(local.id)
            return
        try:
            adapter.delete_task(local)
            # 保留墓碑记录：状态 deleted + sync_status synced
            self._manager.mark_synced(local.id)
            report.pushed_delete += 1
        except Exception as exc:
            report.errors.append(f"推送删除失败 {local.id}: {exc}")
            self._manager.mark_error(local.id, str(exc))

    def _push_local_attachments(self, adapter: TodoAdapter, local: Task, report: SyncReport) -> None:
        store = self._manager.attachment_store
        if not store:
            return
        for att in self._manager.list_attachments(local.id):
            if not att.local_path or not os.path.isfile(att.local_path):
                continue
            if att.source:
                continue  # 已经归属外部来源的附件不用重复推送
            try:
                source_url = adapter.push_attachment(local, att)
                if source_url:
                    self._manager.mark_attachment_synced(att.id, adapter.source, source_url)
                    report.attachments_pushed += 1
            except Exception as exc:
                report.errors.append(f"推送附件失败 {local.id}/{att.file_name}: {exc}")
                log.warning("推送附件失败 %s/%s: %s", local.id, att.file_name, exc)


class SyncBusyError(Exception):
    """同步正在进行中。"""

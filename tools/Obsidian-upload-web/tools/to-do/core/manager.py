"""任务管理器：Leo Todo 的核心业务逻辑（不依赖任何外部来源）。

职责：创建 / 修改 / 完成 / 软删除 / 恢复 / 查询 / 分类 / 统计，
以及同步相关的状态标记（pending_push / pending_delete / synced）。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from core.models import (
    STATUS_TODO, STATUS_COMPLETED, STATUS_DELETED,
    SYNC_LOCAL, SYNC_SYNCED, SYNC_PENDING_PUSH, SYNC_PENDING_DELETE, SYNC_ERROR,
    SOURCE_LEO,
    Task, TaskAttachment, TaskStats, now_iso,
)
from storage.database import Database
from storage.attachment import AttachmentStore

log = logging.getLogger(__name__)


class TaskManager:
    def __init__(self, db: Database, attachment_store: Optional[AttachmentStore] = None):
        self._db = db
        self._att = attachment_store

    # ------------------------------------------------------------------
    # 附件
    # ------------------------------------------------------------------

    @property
    def attachment_store(self) -> Optional[AttachmentStore]:
        return self._att

    def add_attachment_record(self, att: TaskAttachment) -> TaskAttachment:
        self._db.insert_attachment(att)
        return att

    def list_attachments(self, task_id: str) -> List[TaskAttachment]:
        return self._db.list_attachments(task_id)

    def get_attachment(self, attachment_id: str) -> Optional[TaskAttachment]:
        return self._db.get_attachment(attachment_id)

    def remove_attachment(self, attachment_id: str) -> Optional[str]:
        """删除附件：先删文件再删记录，返回删除的本地路径。"""
        att = self._db.get_attachment(attachment_id)
        if att is None:
            return None
        path = att.local_path
        if self._att:
            self._att.delete_file(path)
        self._db.delete_attachment(attachment_id)
        return path

    def mark_attachment_synced(self, attachment_id: str, source: str, source_url: str) -> None:
        self._db.update_attachment(
            attachment_id, {"source": source, "source_url": source_url}
        )

    def clean_orphan_attachments(self) -> int:
        """清理没有数据库记录的孤儿附件文件。"""
        if not self._att:
            return 0
        keep = {a.local_path for a in self._db.all_attachment_records() if a.local_path}
        return self._att.clean_orphan_files(keep)

    # ------------------------------------------------------------------
    # 任务 CRUD
    # ------------------------------------------------------------------

    def create_task(self, task: Task) -> Task:
        """创建任务（默认 source=leo / sync_status=local）。

        外部拉取的任务自带 created_at/updated_at，必须保留（LWW 依据）；
        本地新建任务由 Task.__post_init__ 生成当前时间。
        """
        if not task.source:
            task.source = SOURCE_LEO
        if not task.sync_status:
            task.sync_status = SYNC_LOCAL
        self._db.insert_task(task)
        log.info("创建任务 %s: %s", task.id, task.title)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._db.get_task(task_id)

    def update_task(self, task_id: str, fields: dict) -> Optional[Task]:
        """修改任务字段；来源是外部同步的任务会标记为 pending_push。"""
        task = self._db.get_task(task_id)
        if task is None:
            return None
        data = dict(fields)
        if "tags" in data and not isinstance(data["tags"], list):
            data["tags"] = []
        task = self._db.update_task(task_id, data)
        if task and task.source != SOURCE_LEO and task.status != STATUS_DELETED:
            self._db.update_task(task_id, {"sync_status": SYNC_PENDING_PUSH})
            task = self._db.get_task(task_id)
        log.info("更新任务 %s: %s", task_id, data)
        return task

    def complete_task(self, task_id: str, completed: bool = True) -> Optional[Task]:
        status = STATUS_COMPLETED if completed else STATUS_TODO
        return self.update_task(task_id, {"status": status})

    def soft_delete(self, task_id: str, push: bool = True) -> Optional[Task]:
        """软删除：status=deleted，绝不物理删除。

        push=True（本地用户删除）：
            - 有外部来源 id 的任务 → 标记 pending_delete（待推送删除到外部）
            - 纯本地任务 → 保持 local（无需推送）
        push=False（外部已删除，引擎检测到）：只标记墓碑，不推送。
        """
        task = self._db.get_task(task_id)
        if task is None:
            return None
        self._db.update_task(task_id, {"status": STATUS_DELETED})
        if push and task.source_id and task.source != SOURCE_LEO:
            self._db.update_task(task_id, {"sync_status": SYNC_PENDING_DELETE})
        task = self._db.get_task(task_id)
        log.info("软删除任务 %s: %s", task_id, task.title)
        return task

    def restore_task(self, task_id: str) -> Optional[Task]:
        """恢复被软删除的任务。"""
        task = self._db.get_task(task_id)
        if task is None or task.status != STATUS_DELETED:
            return task
        self._db.update_task(task_id, {"status": STATUS_TODO})
        if task.source_id and task.source != SOURCE_LEO:
            self._db.update_task(task_id, {"sync_status": SYNC_PENDING_PUSH})
        else:
            self._db.update_task(task_id, {"sync_status": SYNC_LOCAL})
        task = self._db.get_task(task_id)
        log.info("恢复任务 %s: %s", task_id, task.title)
        return task

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        status: Optional[str] = None,
        include_deleted: bool = False,
        project: Optional[str] = None,
        priority: Optional[str] = None,
        tag: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Task]:
        return self._db.query_tasks(
            status=status, include_deleted=include_deleted, project=project,
            priority=priority, tag=tag, source=source, search=search, limit=limit,
        )

    def list_deleted(self) -> List[Task]:
        return self._db.query_tasks(status=STATUS_DELETED)

    def list_pending(self, source: Optional[str] = None) -> List[Task]:
        """需要推送到外部来源的任务：
        - 本地新建（sync_status=local / pending_push / error，且未删除）
        - 待推送删除（sync_status=pending_delete）
        """
        all_tasks = self._db.all_task_records()
        result = []
        for t in all_tasks:
            if source and t.source not in (source, SOURCE_LEO):
                continue
            if t.sync_status == SYNC_PENDING_DELETE:
                result.append(t)
            elif t.sync_status in (SYNC_LOCAL, SYNC_PENDING_PUSH, SYNC_ERROR) and not t.is_deleted:
                result.append(t)
        return result

    def list_synced_for_source(self, source: str) -> List[Task]:
        """来自指定来源且已同步、未删除的任务（用于检测外部删除）。"""
        result = []
        for t in self._db.all_task_records():
            if (
                t.source == source
                and t.sync_status == SYNC_SYNCED
                and not t.is_deleted
                and t.source_id
            ):
                result.append(t)
        return result

    def find_by_source_id(self, source: str, source_id: str) -> Optional[Task]:
        return self._db.find_by_source_id(source, source_id)

    def stats(self) -> TaskStats:
        def count(where, params=()):
            return self._db.count_tasks(where, params)

        total = count("1=1")
        active = count("status IN ('todo','in_progress')")
        in_progress = count("status='in_progress'")
        completed = count("status='completed'")
        deleted = count("status='deleted'")
        overdue = count(
            "status NOT IN ('completed','deleted') AND due_date != '' "
            "AND due_date < ?", (now_iso(),)
        )
        return TaskStats(
            total=total, active=active, in_progress=in_progress,
            completed=completed, deleted=deleted, overdue=overdue,
            project_count=len(self._db.distinct_projects()),
            tag_count=len(self._db.distinct_tags()),
        )

    def projects(self) -> List[str]:
        return self._db.distinct_projects()

    def tags(self) -> List[str]:
        return self._db.distinct_tags()

    # ------------------------------------------------------------------
    # 同步状态标记（供 SyncEngine 调用）
    # ------------------------------------------------------------------

    def apply_external(self, task_id: str, external: Task) -> Optional[Task]:
        """用外部任务覆盖本地（外部版本较新时调用），标记 synced。"""
        return self._db.update_task(
            task_id,
            {
                "title": external.title,
                "description": external.description,
                "status": external.status,
                "priority": external.priority,
                "project": external.project,
                "tags": list(external.tags),
                "source": external.source,
                "source_id": external.source_id,
                "source_list_id": external.source_list_id,
                "due_date": external.due_date,
                "updated_at": external.updated_at,
                "sync_status": SYNC_SYNCED,
            },
        )

    def mark_synced(self, task_id: str) -> Optional[Task]:
        return self._db.set_sync_status(task_id, SYNC_SYNCED)

    def mark_error(self, task_id: str, message: str) -> Optional[Task]:
        task = self._db.set_sync_status(task_id, SYNC_ERROR)
        log.error("任务同步失败 %s: %s", task_id, message)
        return task

    def set_source_ids(self, task_id: str, source_id: str, source_list_id: str) -> Optional[Task]:
        return self._db.update_task(
            task_id,
            {"source_id": source_id, "source_list_id": source_list_id},
        )

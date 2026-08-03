"""SQLite 本地任务数据库。

tasks 表           任务本体（唯一数据源）
task_attachments   任务附件关系
sync_meta          同步元数据（各来源最近同步时间）

线程安全：pywebview 的 js_api 在后台线程调用，
使用 RLock + check_same_thread=False，所有写操作包在事务里。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Generator, List, Optional

from core.models import Task, TaskAttachment, now_iso, normalize_ts

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'todo',
    priority        TEXT NOT NULL DEFAULT 'medium',
    project         TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    source          TEXT NOT NULL DEFAULT 'leo',
    source_id       TEXT NOT NULL DEFAULT '',
    source_list_id  TEXT NOT NULL DEFAULT '',
    due_date        TEXT NOT NULL DEFAULT '',
    sync_status     TEXT NOT NULL DEFAULT 'local',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_source_id  ON tasks(source_id);
CREATE INDEX IF NOT EXISTS idx_tasks_source     ON tasks(source);
CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project    ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_due        ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_updated    ON tasks(updated_at);

CREATE TABLE IF NOT EXISTS task_attachments (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    file_type   TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    source_url  TEXT NOT NULL DEFAULT '',
    local_path  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_attachments_task      ON task_attachments(task_id);
CREATE INDEX IF NOT EXISTS idx_attachments_source_url ON task_attachments(source_url);

CREATE TABLE IF NOT EXISTS sync_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL DEFAULT ''
);
"""


class Database:
    """任务数据库。对外提供任务 / 附件的增删改查与同步元数据。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    # ------------------------------------------------------------------
    # 基础
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            project=row["project"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source=row["source"],
            source_id=row["source_id"],
            source_list_id=row["source_list_id"],
            due_date=row["due_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            sync_status=row["sync_status"],
        )

    def _row_to_attachment(self, row: sqlite3.Row) -> TaskAttachment:
        return TaskAttachment(
            id=row["id"],
            task_id=row["task_id"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            source=row["source"],
            source_url=row["source_url"],
            local_path=row["local_path"],
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------
    # tasks CRUD
    # ------------------------------------------------------------------

    def insert_task(self, task: Task) -> None:
        task.updated_at = normalize_ts(task.updated_at or now_iso())
        task.created_at = normalize_ts(task.created_at or task.updated_at)
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO tasks (id, title, description, status, priority,
                   project, tags, source, source_id, source_list_id, due_date,
                   sync_status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task.id, task.title, task.description, task.status,
                    task.priority, task.project, json.dumps(task.tags, ensure_ascii=False),
                    task.source, task.source_id, task.source_list_id, task.due_date,
                    task.sync_status, task.created_at, task.updated_at,
                ),
            )

    def update_task(self, task_id: str, fields: dict) -> Optional[Task]:
        """按字段白名单更新任务；任何更新都会刷新 updated_at。"""
        allowed = {
            "title", "description", "status", "priority", "project", "tags",
            "source", "source_id", "source_list_id", "due_date", "sync_status",
            "updated_at",
        }
        data = {k: v for k, v in fields.items() if k in allowed}
        if not data:
            return self.get_task(task_id)

        task = self.get_task(task_id)
        if task is None:
            return None
        for k, v in data.items():
            setattr(task, k, v)
        if isinstance(task.tags, str):
            task.tags = json.loads(task.tags) if task.tags else []
        if "updated_at" not in data:
            task.updated_at = now_iso()
        task.updated_at = normalize_ts(task.updated_at or now_iso())

        with self._tx() as conn:
            conn.execute(
                """UPDATE tasks SET title=?, description=?, status=?, priority=?,
                   project=?, tags=?, source=?, source_id=?, source_list_id=?,
                   due_date=?, sync_status=?, updated_at=?
                   WHERE id=?""",
                (
                    task.title, task.description, task.status, task.priority,
                    task.project, json.dumps(task.tags, ensure_ascii=False),
                    task.source, task.source_id, task.source_list_id,
                    task.due_date, task.sync_status, task.updated_at, task.id,
                ),
            )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            )
            row = cur.fetchone()
            return self._row_to_task(row) if row else None

    def find_by_source_id(self, source: str, source_id: str) -> Optional[Task]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM tasks WHERE source=? AND source_id=? LIMIT 1",
                (source, source_id),
            )
            row = cur.fetchone()
            return self._row_to_task(row) if row else None

    def query_tasks(
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
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        elif not include_deleted:
            where.append("status != ?")
            params.append("deleted")
        if project:
            where.append("project=?")
            params.append(project)
        if priority:
            where.append("priority=?")
            params.append(priority)
        if source:
            where.append("source=?")
            params.append(source)
        if tag:
            where.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if search:
            where.append("(title LIKE ? OR description LIKE ? OR tags LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        sql = "SELECT * FROM tasks"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(sql, params)
            return [self._row_to_task(r) for r in cur.fetchall()]

    def count_tasks(self, where: str = "", params: tuple = ()) -> int:
        sql = "SELECT COUNT(*) FROM tasks"
        if where:
            sql += " WHERE " + where
        with self._lock:
            cur = self._conn.execute(sql, params)
            return int(cur.fetchone()[0])

    def distinct_projects(self) -> List[str]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT DISTINCT project FROM tasks "
                "WHERE project != '' AND status != 'deleted' ORDER BY project"
            )
            return [r["project"] for r in cur.fetchall()]

    def distinct_tags(self) -> List[str]:
        tags: set = set()
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT tags FROM tasks WHERE status != 'deleted' AND tags != '[]'"
            )
            for row in cur:
                try:
                    tags.update(json.loads(row["tags"]))
                except (ValueError, TypeError):
                    continue
        return sorted(tags)

    # ------------------------------------------------------------------
    # 附件
    # ------------------------------------------------------------------

    def insert_attachment(self, att: TaskAttachment) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO task_attachments
                   (id, task_id, file_name, file_type, source, source_url, local_path, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (att.id, att.task_id, att.file_name, att.file_type,
                 att.source, att.source_url, att.local_path, att.created_at),
            )

    def list_attachments(self, task_id: str) -> List[TaskAttachment]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM task_attachments WHERE task_id=? ORDER BY created_at",
                (task_id,),
            )
            return [self._row_to_attachment(r) for r in cur.fetchall()]

    def get_attachment(self, attachment_id: str) -> Optional[TaskAttachment]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM task_attachments WHERE id=?", (attachment_id,)
            )
            row = cur.fetchone()
            return self._row_to_attachment(row) if row else None

    def find_attachment_by_source_url(self, source_url: str) -> Optional[TaskAttachment]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM task_attachments WHERE source_url=? LIMIT 1",
                (source_url,),
            )
            row = cur.fetchone()
            return self._row_to_attachment(row) if row else None

    def delete_attachment(self, attachment_id: str) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM task_attachments WHERE id=?", (attachment_id,))

    def update_attachment(self, attachment_id: str, fields: dict) -> Optional[TaskAttachment]:
        allowed = {"task_id", "file_name", "file_type", "source", "source_url", "local_path"}
        data = {k: v for k, v in fields.items() if k in allowed}
        if not data:
            return self.get_attachment(attachment_id)
        att = self.get_attachment(attachment_id)
        if att is None:
            return None
        for k, v in data.items():
            setattr(att, k, v)
        with self._tx() as conn:
            conn.execute(
                """UPDATE task_attachments
                   SET task_id=?, file_name=?, file_type=?, source=?, source_url=?, local_path=?
                   WHERE id=?""",
                (att.task_id, att.file_name, att.file_type, att.source,
                 att.source_url, att.local_path, att.id),
            )
        return att

    def prune_attachments_not_in(self, task_id: str, keep_source_urls: set) -> List[str]:
        """删除该任务下 source_url 不在 keep 集合内的附件记录，返回被删 id 列表。"""
        removed = []
        for att in self.list_attachments(task_id):
            if att.source_url and att.source_url not in keep_source_urls:
                removed.append(att.id)
                self.delete_attachment(att.id)
        return removed

    def all_attachment_records(self) -> List[TaskAttachment]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute("SELECT * FROM task_attachments")
            return [self._row_to_attachment(r) for r in cur.fetchall()]

    def all_task_records(self) -> List[Task]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC")
            return [self._row_to_task(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # sync_meta
    # ------------------------------------------------------------------

    def set_sync_status(self, task_id: str, sync_status: str) -> Optional[Task]:
        """只更新 sync_status 列，不触碰 updated_at（避免簿记污染 LWW 时间戳）。"""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET sync_status=? WHERE id=?", (sync_status, task_id)
            )
        return self.get_task(task_id)

    def get_meta(self, key: str) -> str:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT value FROM sync_meta WHERE key=?", (key,)
            )
            row = cur.fetchone()
            return row["value"] if row else ""

    def set_meta(self, key: str, value: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO sync_meta (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

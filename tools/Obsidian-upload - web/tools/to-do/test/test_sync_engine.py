"""同步引擎测试：使用 FakeAdapter 模拟外部任务源（完全离线）。

覆盖：首次全量同步 / 外部更新覆盖 / 外部删除检测 /
本地创建推送 / 本地修改推送 / 本地删除推送 / LWW 冲突。
"""
from __future__ import annotations

import os
import tempfile
import unittest

from core.models import (
    STATUS_TODO, STATUS_COMPLETED, STATUS_DELETED,
    SYNC_SYNCED, SYNC_PENDING_PUSH, SYNC_PENDING_DELETE,
    SOURCE_LEO, SOURCE_MICROSOFT,
    Task, normalize_ts, now_iso,
)
from core.manager import TaskManager
from core.sync_engine import SyncEngine, TodoAdapter
from storage.database import Database
from storage.attachment import AttachmentStore

FAKE_SOURCE = "fake"


class FakeAdapter(TodoAdapter):
    """内存版外部任务源。lastModified 自动递增，模拟微软行为。"""

    source = FAKE_SOURCE

    def __init__(self):
        self._tasks = {}          # id -> graph dict
        self._seq = 0
        self._deleted_calls = []

    def _next_ts(self):
        self._seq += 1
        return f"2026-08-01T00:00:{self._seq:02d}.000Z"

    def seed(self, task_id, title, status="notStarted", ts=None):
        g = {
            "id": task_id,
            "title": title,
            "status": status,
            "importance": "normal",
            "body": {"contentType": "text", "content": ""},
            "lastModifiedDateTime": ts or self._next_ts(),
            "createdDateTime": ts or self._next_ts(),
            "categories": [],
            "listId": "list_1",
        }
        self._tasks[task_id] = g
        return g

    # -- TodoAdapter 接口 --
    def list_tasks(self):
        return [self._to_leo(g) for g in self._tasks.values()]

    def _to_leo(self, g):
        return Task(
            title=g["title"],
            description=(g.get("body") or {}).get("content", ""),
            status={"notStarted": STATUS_TODO, "inProgress": "in_progress",
                    "completed": STATUS_COMPLETED}.get(g["status"], STATUS_TODO),
            priority="medium",
            project="列表A",
            source=FAKE_SOURCE,
            source_id=g["id"],
            source_list_id="list_1",
            created_at=normalize_ts(g["createdDateTime"]),
            updated_at=normalize_ts(g["lastModifiedDateTime"]),
            sync_status=SYNC_SYNCED,
        )

    def create_task(self, task):
        gid = f"fake_{len(self._tasks) + 1}"
        ts = self._next_ts()
        self._tasks[gid] = {
            "id": gid, "title": task.title, "status": "notStarted",
            "importance": "normal", "body": {"contentType": "text", "content": task.description},
            "lastModifiedDateTime": ts, "createdDateTime": ts, "categories": list(task.tags),
            "listId": "list_1",
        }
        task.source_id = gid
        task.source_list_id = "list_1"
        return task

    def update_task(self, task):
        g = self._tasks.get(task.source_id)
        if g is None:
            raise RuntimeError(f"外部任务不存在: {task.source_id}")
        g["title"] = task.title
        g["status"] = "completed" if task.status == STATUS_COMPLETED else "notStarted"
        g["body"]["content"] = task.description
        g["categories"] = list(task.tags)
        g["lastModifiedDateTime"] = self._next_ts()
        return task

    def delete_task(self, task):
        self._deleted_calls.append(task.source_id)
        self._tasks.pop(task.source_id, None)

    def list_attachments(self, task):
        return []

    def download_attachment(self, task, meta, dest_path):
        return 0

    def push_attachment(self, task, attachment):
        return "graph://fake"

    def update_external(self, task_id, title, ts):
        self._tasks[task_id]["title"] = title
        self._tasks[task_id]["lastModifiedDateTime"] = ts


class SyncEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="leo_todo_sync_")
        self.db = Database(os.path.join(self.tmpdir, "todo.db"))
        self.mgr = TaskManager(self.db, AttachmentStore(os.path.join(self.tmpdir, "att")))
        self.engine = SyncEngine(self.mgr)
        self.adapter = FakeAdapter()
        self.engine.register_adapter(self.adapter)

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------

    def test_first_sync_pulls_all(self):
        self.adapter.seed("ext_1", "购买显示器")
        self.adapter.seed("ext_2", "准备周报")
        report = self.engine.sync(FAKE_SOURCE)[0]
        self.assertEqual(report.pulled, 2)
        self.assertEqual(report.created, 2)
        local = self.mgr.list_tasks()
        self.assertEqual(len(local), 2)
        for t in local:
            self.assertEqual(t.sync_status, SYNC_SYNCED)
            self.assertEqual(t.source, FAKE_SOURCE)
        self.assertTrue(self.db.get_meta(f"last_sync.{FAKE_SOURCE}"))

    def test_external_update_overrides_when_newer(self):
        self.adapter.seed("ext_1", "旧标题", ts="2026-08-01T00:00:01.000Z")
        self.engine.sync(FAKE_SOURCE)
        task = self.mgr.find_by_source_id(FAKE_SOURCE, "ext_1")
        self.assertEqual(task.title, "旧标题")

        # 外部更新（时间戳较新）-> 本地应被覆盖
        self.adapter.update_external("ext_1", "新标题", "2026-08-02T00:00:00.000Z")
        self.engine.sync(FAKE_SOURCE)
        task = self.mgr.get_task(task.id)
        self.assertEqual(task.title, "新标题")

    def test_external_deletion_marks_local_deleted(self):
        self.adapter.seed("ext_1", "会被外部删除")
        self.adapter.seed("ext_2", "保留")
        self.engine.sync(FAKE_SOURCE)

        # 外部删除 ext_1
        del self.adapter._tasks["ext_1"]
        report = self.engine.sync(FAKE_SOURCE)[0]
        self.assertEqual(report.deleted_local, 1)
        deleted = self.mgr.find_by_source_id(FAKE_SOURCE, "ext_1")
        self.assertEqual(deleted.status, STATUS_DELETED)
        self.assertEqual(deleted.sync_status, SYNC_SYNCED)  # 墓碑，不推送
        # 未被误删
        self.assertEqual(self.mgr.get_task(self.mgr.find_by_source_id(FAKE_SOURCE, "ext_2").id).status, STATUS_TODO)

    def test_local_create_pushed(self):
        local = self.mgr.create_task(Task(title="本地任务"))
        report = self.engine.sync(FAKE_SOURCE)[0]
        self.assertEqual(report.pushed_create, 1)
        synced = self.mgr.get_task(local.id)
        self.assertEqual(synced.sync_status, SYNC_SYNCED)
        self.assertEqual(synced.source, FAKE_SOURCE)  # 推送后归属外部来源
        self.assertTrue(synced.source_id.startswith("fake_"))
        self.assertEqual(len(self.adapter._tasks), 1)

    def test_local_edit_pushed(self):
        self.adapter.seed("ext_1", "原始", ts="2026-08-01T00:00:01.000Z")
        self.engine.sync(FAKE_SOURCE)
        task = self.mgr.find_by_source_id(FAKE_SOURCE, "ext_1")
        self.mgr.update_task(task.id, {"title": "本地改"})
        self.assertEqual(self.mgr.get_task(task.id).sync_status, SYNC_PENDING_PUSH)

        self.engine.sync(FAKE_SOURCE)
        self.assertEqual(self.mgr.get_task(task.id).sync_status, SYNC_SYNCED)
        self.assertEqual(self.adapter._tasks["ext_1"]["title"], "本地改")

    def test_local_delete_pushed(self):
        self.adapter.seed("ext_1", "待删除", ts="2026-08-01T00:00:01.000Z")
        self.engine.sync(FAKE_SOURCE)
        task = self.mgr.find_by_source_id(FAKE_SOURCE, "ext_1")
        self.mgr.soft_delete(task.id)
        self.assertEqual(self.mgr.get_task(task.id).sync_status, SYNC_PENDING_DELETE)

        report = self.engine.sync(FAKE_SOURCE)[0]
        self.assertEqual(report.pushed_delete, 1)
        self.assertIn("ext_1", self.adapter._deleted_calls)
        self.assertNotIn("ext_1", self.adapter._tasks)
        # 墓碑保留在本地
        tomb = self.mgr.get_task(task.id)
        self.assertEqual(tomb.status, STATUS_DELETED)
        self.assertEqual(tomb.sync_status, SYNC_SYNCED)

    def test_conflict_lww_local_newer_kept(self):
        # 首次同步：外部较新
        self.adapter.seed("ext_1", "外部版本", ts="2026-08-01T00:00:01.000Z")
        self.engine.sync(FAKE_SOURCE)
        task = self.mgr.find_by_source_id(FAKE_SOURCE, "ext_1")

        # 本地修改（updated_at 更新 -> 新于外部）
        self.mgr.update_task(task.id, {"title": "本地版本"})
        local_ts = self.mgr.get_task(task.id).updated_at
        # 外部同步一个更旧的时间戳
        self.adapter.update_external("ext_1", "外部旧版本", "2026-07-01T00:00:00.000Z")
        self.engine.sync(FAKE_SOURCE)

        # 本地较新 -> 本地不应被覆盖，且本地改动会推送给外部（LWW 胜者推送）
        kept = self.mgr.get_task(task.id)
        self.assertEqual(kept.title, "本地版本")
        self.assertEqual(kept.updated_at, local_ts)
        self.assertEqual(kept.sync_status, SYNC_SYNCED)
        self.assertEqual(self.adapter._tasks["ext_1"]["title"], "本地版本")

    def test_sync_busy_guard(self):
        self.engine._syncing = True
        with self.assertRaises(Exception):
            self.engine.sync(FAKE_SOURCE)
        self.engine._syncing = False

    def test_unregistered_source(self):
        with self.assertRaises(ValueError):
            self.engine.sync("nope")


if __name__ == "__main__":
    unittest.main()

"""数据库层测试：tasks / task_attachments / sync_meta CRUD。"""
from __future__ import annotations

import os
import tempfile
import unittest

from core.models import Task, TaskAttachment, new_id
from storage.database import Database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="leo_todo_db_")
        self.db = Database(os.path.join(self.tmpdir, "todo.db"))

    def tearDown(self):
        self.db.close()

    def _task(self, **kw):
        kw.setdefault("title", "默认任务")
        task = Task(**kw)
        self.db.insert_task(task)
        return task

    def test_insert_and_get(self):
        t = self._task(title="买显示器", priority="high", project="硬件")
        got = self.db.get_task(t.id)
        self.assertEqual(got.title, "买显示器")
        self.assertEqual(got.priority, "high")
        self.assertEqual(got.project, "硬件")
        self.assertTrue(got.created_at)
        self.assertTrue(got.updated_at)

    def test_update_task_refreshes_updated_at(self):
        t = self._task(title="a")
        before = t.updated_at
        updated = self.db.update_task(t.id, {"title": "b"})
        self.assertEqual(updated.title, "b")
        self.assertGreaterEqual(updated.updated_at, before)
        # 显式传入 updated_at 应被保留
        pinned = "2020-01-01T00:00:00.000Z"
        again = self.db.update_task(t.id, {"title": "c", "updated_at": pinned})
        self.assertEqual(again.updated_at, pinned)

    def test_query_filters(self):
        self._task(title="任务A", status="todo", project="P1", priority="high", tags=["工作"])
        self._task(title="任务B", status="completed", project="P2", priority="low", tags=["生活"])
        self._task(title="任务C", status="deleted")

        self.assertEqual(len(self.db.query_tasks()), 2)  # 默认排除已删除
        self.assertEqual(len(self.db.query_tasks(include_deleted=True)), 3)
        self.assertEqual(len(self.db.query_tasks(status="completed")), 1)
        self.assertEqual(len(self.db.query_tasks(project="P1")), 1)
        self.assertEqual(len(self.db.query_tasks(priority="low")), 1)
        self.assertEqual(len(self.db.query_tasks(tag="生活")), 1)
        self.assertEqual(len(self.db.query_tasks(search="任务B")), 1)

    def test_find_by_source_id(self):
        t = self._task(source="microsoft", source_id="ms_1")
        found = self.db.find_by_source_id("microsoft", "ms_1")
        self.assertEqual(found.id, t.id)
        self.assertIsNone(self.db.find_by_source_id("microsoft", "nope"))

    def test_tags_json_roundtrip(self):
        t = self._task(tags=["工作", "重要"])
        got = self.db.get_task(t.id)
        self.assertEqual(got.tags, ["工作", "重要"])
        self.assertEqual(self.db.distinct_tags(), ["工作", "重要"])

    def test_attachments_crud(self):
        t = self._task(title="带附件")
        att = TaskAttachment(task_id=t.id, file_name="design.png", file_type="image/png",
                             source="microsoft", source_url="graph://x", local_path="C:/tmp/a.png")
        self.db.insert_attachment(att)
        got = self.db.get_attachment(att.id)
        self.assertEqual(got.file_name, "design.png")
        self.assertTrue(got.is_image)
        self.assertEqual(len(self.db.list_attachments(t.id)), 1)

        # 按 source_url 查重
        dup = self.db.find_attachment_by_source_url("graph://x")
        self.assertEqual(dup.id, att.id)

        # 更新（推送后标记归属）
        updated = self.db.update_attachment(att.id, {"source": "leo", "source_url": "graph://y"})
        self.assertEqual(updated.source, "leo")
        self.assertEqual(updated.source_url, "graph://y")

        # 裁剪不在集合内的
        removed = self.db.prune_attachments_not_in(t.id, {"graph://zzz"})
        self.assertEqual(removed, [att.id])
        self.assertEqual(len(self.db.list_attachments(t.id)), 0)

    def test_sync_meta(self):
        self.assertEqual(self.db.get_meta("k"), "")
        self.db.set_meta("k", "v1")
        self.assertEqual(self.db.get_meta("k"), "v1")
        self.db.set_meta("k", "v2")
        self.assertEqual(self.db.get_meta("k"), "v2")

    def test_persist_across_reopen(self):
        t = self._task(title="持久化")
        self.db.close()
        db2 = Database(os.path.join(self.tmpdir, "todo.db"))
        got = db2.get_task(t.id)
        self.assertEqual(got.title, "持久化")
        db2.close()


if __name__ == "__main__":
    unittest.main()

"""任务管理器测试：CRUD / 软删除 / 恢复 / 同步状态标记。"""
from __future__ import annotations

import os
import tempfile
import unittest

from core.models import (
    Task, TaskAttachment, STATUS_DELETED, SYNC_LOCAL, SYNC_SYNCED,
    SYNC_PENDING_PUSH, SYNC_PENDING_DELETE, SOURCE_MICROSOFT,
)
from core.manager import TaskManager
from storage.database import Database
from storage.attachment import AttachmentStore


class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="leo_todo_mgr_")
        self.db = Database(os.path.join(self.tmpdir, "todo.db"))
        self.store = AttachmentStore(os.path.join(self.tmpdir, "attachments"))
        self.mgr = TaskManager(self.db, self.store)

    def tearDown(self):
        self.db.close()

    def test_create_and_get(self):
        t = self.mgr.create_task(Task(title="优化Markdown编辑器", project="LeoDiary Capture"))
        self.assertEqual(t.source, "leo")
        self.assertEqual(t.sync_status, SYNC_LOCAL)
        got = self.mgr.get_task(t.id)
        self.assertEqual(got.title, "优化Markdown编辑器")

    def test_update_marks_pending_push_for_external(self):
        t = self.mgr.create_task(Task(
            title="a", source=SOURCE_MICROSOFT, source_id="ms_1", sync_status=SYNC_SYNCED,
        ))
        self.assertEqual(t.sync_status, SYNC_SYNCED)
        updated = self.mgr.update_task(t.id, {"title": "b"})
        self.assertEqual(updated.sync_status, SYNC_PENDING_PUSH)

    def test_soft_delete_local_keeps_local(self):
        t = self.mgr.create_task(Task(title="本地任务"))
        deleted = self.mgr.soft_delete(t.id)
        self.assertEqual(deleted.status, STATUS_DELETED)
        self.assertEqual(deleted.sync_status, SYNC_LOCAL)  # 本地任务无外部来源，不推送

    def test_soft_delete_external_marks_pending_delete(self):
        t = self.mgr.create_task(Task(title="外部任务", source=SOURCE_MICROSOFT, source_id="ms_9"))
        deleted = self.mgr.soft_delete(t.id)
        self.assertEqual(deleted.status, STATUS_DELETED)
        self.assertEqual(deleted.sync_status, SYNC_PENDING_DELETE)

    def test_restore(self):
        t = self.mgr.create_task(Task(title="x", source=SOURCE_MICROSOFT, source_id="ms_7"))
        self.mgr.soft_delete(t.id)
        restored = self.mgr.restore_task(t.id)
        self.assertEqual(restored.status, "todo")
        self.assertEqual(restored.sync_status, SYNC_PENDING_PUSH)

    def test_apply_external_and_mark_synced(self):
        t = self.mgr.create_task(Task(title="旧标题"))
        ext = Task(title="新标题", description="外部描述", status="completed",
                   priority="high", project="P", tags=["t1"], source=SOURCE_MICROSOFT,
                   source_id="ms_5", source_list_id="list_1",
                   updated_at="2026-08-02T10:00:00.000Z")
        applied = self.mgr.apply_external(t.id, ext)
        self.assertEqual(applied.title, "新标题")
        self.assertEqual(applied.status, "completed")
        self.assertEqual(applied.sync_status, SYNC_SYNCED)
        self.assertEqual(applied.updated_at, "2026-08-02T10:00:00.000Z")

    def test_list_pending(self):
        local = self.mgr.create_task(Task(title="待推送本地"))
        external = self.mgr.create_task(Task(title="外部", source=SOURCE_MICROSOFT, source_id="ms_3"))
        self.mgr.update_task(external.id, {"title": "外部改"})  # pending_push
        self.mgr.create_task(Task(title="已同步外部", source=SOURCE_MICROSOFT,
                                  source_id="ms_4", sync_status=SYNC_SYNCED))
        pending = self.mgr.list_pending(source=SOURCE_MICROSOFT)
        ids = {t.id for t in pending}
        self.assertIn(local.id, ids)
        self.assertIn(external.id, ids)
        self.assertEqual(len(ids), 2)

    def test_attachment_flow(self):
        t = self.mgr.create_task(Task(title="带附件"))
        path = self.store.save_bytes(t.id, "shot.png", b"\x89PNG\r\n\x1a\n1234")
        self.mgr.add_attachment_record(TaskAttachment(
            task_id=t.id, file_name="shot.png", file_type="image/png",
            source="leo", local_path=path,
        ))
        atts = self.mgr.list_attachments(t.id)
        self.assertEqual(len(atts), 1)
        self.assertTrue(atts[0].is_image)

        # 删除附件：文件和记录都清除
        removed = self.mgr.remove_attachment(atts[0].id)
        self.assertTrue(os.path.isfile(removed) is False or not os.path.exists(removed))
        self.assertEqual(len(self.mgr.list_attachments(t.id)), 0)

    def test_stats(self):
        self.mgr.create_task(Task(title="a"))
        self.mgr.create_task(Task(title="b", status="completed"))
        s = self.mgr.stats()
        self.assertEqual(s.total, 2)
        self.assertEqual(s.active, 1)
        self.assertEqual(s.completed, 1)


if __name__ == "__main__":
    unittest.main()

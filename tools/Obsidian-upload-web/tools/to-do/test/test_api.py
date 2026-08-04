"""TodoApi 桥接层集成测试：模拟 pywebview 的 js_api 调用（无 GUI / 无网络）。"""
from __future__ import annotations

import base64
import os
import tempfile
import unittest

from core.config import load_config
from core.manager import TaskManager
from core.sync_engine import SyncEngine
from core.api import TodoApi
from storage.database import Database
from storage.attachment import AttachmentStore

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _config(tmpdir: str) -> dict:
    return {
        "app_name": "Leo Todo",
        "db_file": os.path.join(tmpdir, "todo.db"),
        "attachments_dir": os.path.join(tmpdir, "attachments"),
        "image_exts": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
        "sync": {"auto_sync_on_start": False},
        "microsoft": {"enabled": False},
    }


class TodoApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="leo_todo_api_")
        cfg = _config(self.tmpdir)
        self.db = Database(cfg["db_file"])
        self.store = AttachmentStore(cfg["attachments_dir"])
        self.mgr = TaskManager(self.db, self.store)
        self.engine = SyncEngine(self.mgr)
        self.api = TodoApi(self.mgr, self.engine, auth=None, config=cfg)

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------

    def test_app_info(self):
        info = self.api.app_info()
        self.assertEqual(info["name"], "Leo Todo")
        self.assertFalse(info["auto_sync_on_start"])

    def test_create_and_query_flow(self):
        created = self.api.create_task({
            "title": "开发首页", "project": "Web", "priority": "high",
            "tags": ["前端", "重要"], "description": "设计图参照",
        })
        self.assertIn("leo_task_", created["id"])
        self.assertEqual(created["source"], "leo")
        self.assertEqual(created["sync_status"], "local")

        listed = self.api.list_tasks()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["tags"], ["前端", "重要"])

        # 更新 + 完成 + 删除（软删除）
        updated = self.api.update_task(created["id"], {"title": "开发首页 v2"})
        self.assertEqual(updated["title"], "开发首页 v2")
        done = self.api.complete_task(created["id"], True)
        self.assertEqual(done["status"], "completed")
        deleted = self.api.delete_task(created["id"])
        self.assertEqual(deleted["status"], "deleted")
        self.assertEqual(len(self.api.list_deleted()), 1)
        restored = self.api.restore_task(created["id"])
        self.assertEqual(restored["status"], "todo")

    def test_attachment_image_preview(self):
        """测试3：附件图片显示（本地预览路径）。"""
        task = self.api.create_task({"title": "开发首页", "description": "含设计图"})
        b64 = base64.b64encode(_PNG_BYTES).decode("ascii")
        att = self.api.add_attachment_data(task["id"], "设计图.png", b64)
        self.assertTrue(att["is_image"])
        # preview_url 必须是存在的本地文件
        self.assertTrue(att["preview_url"].startswith("file:///"))
        local = att["local_path"]
        self.assertTrue(os.path.isfile(local))
        # 任务视图携带附件
        view = self.api.get_task(task["id"])
        self.assertEqual(len(view["attachments"]), 1)
        self.assertTrue(view["attachments"][0]["preview_url"].startswith("file:///"))

        # 删除附件 -> 文件和记录都清除
        self.assertTrue(self.api.remove_attachment(att["id"]))
        self.assertFalse(os.path.exists(local))

    def test_stats_and_filters(self):
        self.api.create_task({"title": "a"})
        self.api.create_task({"title": "b", "project": "P1", "priority": "high"})
        self.api.create_task({"title": "c", "status": "completed"})
        s = self.api.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["active"], 2)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(self.api.projects(), ["P1"])

        filtered = self.api.list_tasks(project="P1")
        self.assertEqual(len(filtered), 1)
        searched = self.api.list_tasks(search="b")
        self.assertEqual(len(searched), 1)

    def test_ms_status_without_auth(self):
        status = self.api.ms_status()
        self.assertEqual(status["enabled"], False)


if __name__ == "__main__":
    unittest.main()

"""Mapper 测试：Microsoft Graph Task <-> Leo Task 转换（无网络）。"""
from __future__ import annotations

import unittest

from adapters.microsoft.mapper import Mapper
from core.models import (
    STATUS_TODO, STATUS_IN_PROGRESS, STATUS_COMPLETED,
    PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
    SOURCE_MICROSOFT, SYNC_SYNCED, Task,
)


class MapperTestCase(unittest.TestCase):
    def setUp(self):
        self.mapper = Mapper()

    def _graph_task(self, **kw):
        data = {
            "id": "graph_1",
            "title": "购买显示器",
            "status": "notStarted",
            "importance": "high",
            "body": {"contentType": "text", "content": "27寸 4K"},
            "createdDateTime": "2026-08-01T02:00:00Z",
            "lastModifiedDateTime": "2026-08-01T03:00:00.1234567Z",
            "categories": ["工作", "购物"],
            "listId": "list_1",
            "dueDateTime": {"dateTime": "2026-08-15T10:00:00", "timeZone": "UTC"},
        }
        data.update(kw)
        return data

    def test_graph_to_leo(self):
        leo = self.mapper.graph_task_to_leo(self._graph_task(), "购物清单", "list_1")
        self.assertEqual(leo.title, "购买显示器")
        self.assertEqual(leo.source, SOURCE_MICROSOFT)
        self.assertEqual(leo.source_id, "graph_1")
        self.assertEqual(leo.source_list_id, "list_1")
        self.assertEqual(leo.project, "购物清单")
        self.assertEqual(leo.status, STATUS_TODO)
        self.assertEqual(leo.priority, PRIORITY_HIGH)
        self.assertEqual(leo.tags, ["工作", "购物"])
        self.assertEqual(leo.sync_status, SYNC_SYNCED)
        # 时间规范化（7 位小数 -> 3 位，字典序可比）
        self.assertEqual(leo.updated_at, "2026-08-01T03:00:00.123Z")
        self.assertEqual(leo.due_date, "2026-08-15T10:00:00.000Z")
        self.assertFalse(leo.id.startswith("graph_"))  # 本地 uuid

    def test_status_mapping(self):
        leo = self.mapper.graph_task_to_leo(self._graph_task(status="inProgress"), "L", "1")
        self.assertEqual(leo.status, STATUS_IN_PROGRESS)
        leo = self.mapper.graph_task_to_leo(self._graph_task(status="completed"), "L", "1")
        self.assertEqual(leo.status, STATUS_COMPLETED)
        leo = self.mapper.graph_task_to_leo(self._graph_task(status="deferred"), "L", "1")
        self.assertEqual(leo.status, STATUS_TODO)

    def test_html_body_converted(self):
        g = self._graph_task(body={"contentType": "html", "content": "<div>第一行<br>第二行</div>"})
        leo = self.mapper.graph_task_to_leo(g, "L", "1")
        self.assertNotIn("<div>", leo.description)
        self.assertIn("第二行", leo.description)

    def test_leo_to_graph_create(self):
        leo = Task(
            title="优化Markdown编辑器", description="增加目录",
            status=STATUS_IN_PROGRESS, priority=PRIORITY_HIGH,
            project="LeoDiary", tags=["开发"],
            due_date="2026-09-01T00:00:00.000Z",
        )
        payload = self.mapper.leo_to_graph_create(leo)
        self.assertEqual(payload["title"], "优化Markdown编辑器")
        self.assertEqual(payload["status"], "inProgress")
        self.assertEqual(payload["importance"], "high")
        self.assertEqual(payload["categories"], ["开发"])
        self.assertEqual(payload["body"]["content"], "增加目录")
        self.assertEqual(payload["dueDateTime"]["timeZone"], "UTC")

    def test_priority_mapping_roundtrip(self):
        for ms, leo in [("low", PRIORITY_LOW), ("normal", PRIORITY_MEDIUM), ("high", PRIORITY_HIGH)]:
            leo_task = self.mapper.graph_task_to_leo(self._graph_task(importance=ms), "L", "1")
            self.assertEqual(leo_task.priority, leo)
            back = self.mapper.leo_to_graph_create(leo_task)
            self.assertEqual(back["importance"], ms)


if __name__ == "__main__":
    unittest.main()

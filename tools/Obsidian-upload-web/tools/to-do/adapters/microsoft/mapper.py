"""Microsoft Graph Task <-> Leo Task 数据转换。

所有 Microsoft 数据结构只出现在本文件，转换后即为 Leo 原生 Task。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.models import (
    STATUS_TODO, STATUS_IN_PROGRESS, STATUS_COMPLETED,
    PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH,
    SYNC_SYNCED, SOURCE_MICROSOFT,
    Task, normalize_ts, now_iso,
)

# Microsoft status -> Leo status
_MS_STATUS_TO_LEO = {
    "notStarted": STATUS_TODO,
    "inProgress": STATUS_IN_PROGRESS,
    "completed": STATUS_COMPLETED,
    # Microsoft 特有状态一律归入待办
    "waitingOnOthers": STATUS_TODO,
    "deferred": STATUS_TODO,
}
# Leo status -> Microsoft status
_LEO_STATUS_TO_MS = {
    STATUS_TODO: "notStarted",
    STATUS_IN_PROGRESS: "inProgress",
    STATUS_COMPLETED: "completed",
}

# Microsoft importance -> Leo priority
_MS_IMPORTANCE_TO_PRIORITY = {
    "low": PRIORITY_LOW,
    "normal": PRIORITY_MEDIUM,
    "high": PRIORITY_HIGH,
}
# Leo priority -> Microsoft importance
_PRIORITY_TO_MS_IMPORTANCE = {
    PRIORITY_LOW: "low",
    PRIORITY_MEDIUM: "normal",
    PRIORITY_HIGH: "high",
}

# 支持映射到 Microsoft categories 的附件类型白名单
_IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/jpg",
}


class Mapper:
    """Microsoft Graph 任务与 Leo Task 互转。"""

    # ------------------------------------------------------------------
    # Microsoft -> Leo
    # ------------------------------------------------------------------

    def graph_task_to_leo(self, graph_task: Dict, list_name: str, list_id: str) -> Task:
        body = graph_task.get("body") or {}
        content = body.get("content") or ""
        if body.get("contentType") == "html" and content:
            content = self._html_to_text(content)

        tags = [c for c in (graph_task.get("categories") or []) if c]

        return Task(
            title=graph_task.get("title") or "（无标题）",
            description=content,
            status=_MS_STATUS_TO_LEO.get(graph_task.get("status"), STATUS_TODO),
            priority=_MS_IMPORTANCE_TO_PRIORITY.get(
                graph_task.get("importance"), PRIORITY_MEDIUM
            ),
            project=list_name or "",
            tags=tags,
            source=SOURCE_MICROSOFT,
            source_id=graph_task.get("id") or "",
            source_list_id=list_id or "",
            due_date=self._graph_due_to_iso(graph_task.get("dueDateTime")),
            created_at=normalize_ts(graph_task.get("createdDateTime")),
            updated_at=normalize_ts(graph_task.get("lastModifiedDateTime")),
            sync_status=SYNC_SYNCED,
        )

    @staticmethod
    def _graph_due_to_iso(due: Optional[Dict]) -> str:
        """dateTimeTimeZone -> UTC ISO 字符串。"""
        if not due:
            return ""
        date_time = due.get("dateTime") or ""
        if not date_time:
            return ""
        tz = due.get("timeZone") or "UTC"
        # dateTime 通常无时区后缀（微软以 timeZone 字段标明）
        if date_time.endswith(("Z", "+00:00")):
            return normalize_ts(date_time)
        return normalize_ts(date_time + "Z")  # 统一按 UTC 存储

    @staticmethod
    def _html_to_text(html: str) -> str:
        """极简 HTML -> 文本（微软 body 的 HTML 足够简单）。"""
        import re

        text = html
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Leo -> Microsoft
    # ------------------------------------------------------------------

    def leo_to_graph_create(self, leo: Task) -> Dict:
        return {
            "title": leo.title or "（无标题）",
            "status": _LEO_STATUS_TO_MS.get(leo.status, "notStarted"),
            "importance": _PRIORITY_TO_MS_IMPORTANCE.get(
                leo.priority, "normal"
            ),
            "categories": list(leo.tags),
            "dueDateTime": self._iso_to_graph_due(leo.due_date),
            "body": {
                "contentType": "text",
                "content": leo.description or "",
            },
        }

    def leo_to_graph_update(self, leo: Task) -> Dict:
        """增量更新：只提交用户可编辑字段（不提交时间戳 / id 等只读字段）。"""
        return {
            "title": leo.title or "（无标题）",
            "status": _LEO_STATUS_TO_MS.get(leo.status, "notStarted"),
            "importance": _PRIORITY_TO_MS_IMPORTANCE.get(
                leo.priority, "normal"
            ),
            "categories": list(leo.tags),
            "dueDateTime": self._iso_to_graph_due(leo.due_date),
            "body": {
                "contentType": "text",
                "content": leo.description or "",
            },
        }

    @staticmethod
    def _iso_to_graph_due(iso: str) -> Optional[Dict]:
        if not iso:
            return None
        dt = normalize_ts(iso)
        if not dt:
            return None
        return {"dateTime": dt, "timeZone": "UTC"}

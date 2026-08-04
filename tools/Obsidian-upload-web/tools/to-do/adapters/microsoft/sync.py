"""Microsoft To Do 同步适配器（实现 core.sync_engine.TodoAdapter 接口）。

职责：把 Microsoft Graph 数据转换成 Leo Task（经 mapper），
并提供双向同步所需的 create / update / delete / attachments 能力。
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Dict, List, Optional

from core.models import (
    SOURCE_MICROSOFT, Task, TaskAttachment, normalize_ts,
)
from core.sync_engine import TodoAdapter
from .auth import MicrosoftAuth, MicrosoftAuthError
from .client import GraphClient, GraphError
from .mapper import Mapper

log = logging.getLogger(__name__)


class MicrosoftAdapter(TodoAdapter):
    """Microsoft To Do 适配器。"""

    source = SOURCE_MICROSOFT

    def __init__(
        self,
        auth: Optional[MicrosoftAuth] = None,
        client: Optional[GraphClient] = None,
        mapper: Optional[Mapper] = None,
        max_attachment_mb: int = 10,
    ):
        self._auth = auth
        self._graph = client
        self._mapper = mapper or Mapper()
        self._max_attachment_mb = max_attachment_mb
        self._list_name_cache: Dict[str, str] = {}
        self._list_by_name_cache: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 列表解析
    # ------------------------------------------------------------------

    def _client(self) -> GraphClient:
        if self._graph is None:
            raise MicrosoftAuthError("Microsoft 适配器未初始化 client（未登录？）")
        return self._graph

    def _resolve_list_id(self, project: str) -> str:
        """按项目名解析 Microsoft 任务列表 id；不存在则创建。"""
        project = (project or "").strip()
        if project:
            if project in self._list_by_name_cache:
                return self._list_by_name_cache[project]
            found = self._client().find_list_by_name(project)
            if found:
                self._list_by_name_cache[project] = found["id"]
                return found["id"]
            created = self._client().create_todo_list(project)
            self._list_by_name_cache[project] = created["id"]
            return created["id"]
        default = self._client().default_list()
        return default["id"]

    # ------------------------------------------------------------------
    # TodoAdapter: 拉取
    # ------------------------------------------------------------------

    def list_tasks(self) -> List[Task]:
        client = self._client()
        tasks: List[Task] = []
        for lst in client.todo_lists():
            list_id = lst.get("id", "")
            list_name = lst.get("displayName", "")
            self._list_name_cache[list_id] = list_name
            try:
                for g in client.todo_tasks(list_id):
                    tasks.append(self._mapper.graph_task_to_leo(g, list_name, list_id))
            except GraphError as exc:
                log.warning("拉取列表 %s 任务失败：%s", list_name, exc)
        return tasks

    # ------------------------------------------------------------------
    # TodoAdapter: 附件（外部 -> 本地）
    # ------------------------------------------------------------------

    def list_attachments(self, task: Task) -> List[dict]:
        if not task.source_list_id or not task.source_id:
            return []
        try:
            metas = self._client().task_attachments(task.source_list_id, task.source_id)
        except GraphError as exc:
            log.warning("读取任务附件失败 %s: %s", task.id, exc)
            return []
        result = []
        for m in metas:
            result.append({
                "id": m.get("id", ""),
                "name": m.get("name", "attachment"),
                "content_type": m.get("contentType", ""),
                "size": m.get("size", 0) or 0,
                "content_bytes": m.get("contentBytes", ""),
                "source_url": (
                    f"graph://todo/lists/{task.source_list_id}/tasks/"
                    f"{task.source_id}/attachments/{m.get('id', '')}"
                ),
            })
        return result

    def download_attachment(self, task: Task, meta: dict, dest_path: str) -> int:
        content = meta.get("content_bytes") or ""
        if not content:
            raise ValueError("附件内容为空（contentBytes 缺失）")
        try:
            data = base64.b64decode(content)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"附件 base64 解码失败：{exc}") from exc
        if len(data) > self._max_attachment_mb * 1024 * 1024:
            raise ValueError(f"附件超过大小限制 {self._max_attachment_mb}MB")
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return len(data)

    # ------------------------------------------------------------------
    # TodoAdapter: 推送（本地 -> 外部）
    # ------------------------------------------------------------------

    def create_task(self, task: Task) -> Task:
        client = self._client()
        list_id = self._resolve_list_id(task.project)
        payload = self._mapper.leo_to_graph_create(task)
        created = client.create_task(list_id, payload)
        task.source_id = created.get("id", "")
        task.source_list_id = list_id
        task.updated_at = normalize_ts(created.get("lastModifiedDateTime"))
        log.info("创建 Microsoft 任务：%s", task.title)
        return task

    def update_task(self, task: Task) -> Task:
        client = self._client()
        if not task.source_list_id:
            task.source_list_id = self._resolve_list_id(task.project)
        payload = self._mapper.leo_to_graph_update(task)
        try:
            client.update_task(task.source_list_id, task.source_id, payload)
        except GraphError as exc:
            # 外部任务已不存在 -> 重新创建
            if exc.status_code == 404:
                log.info("Microsoft 任务已删除，重新创建：%s", task.title)
                created = client.create_task(task.source_list_id, payload)
                task.source_id = created.get("id", "")
                task.updated_at = normalize_ts(created.get("lastModifiedDateTime"))
            else:
                raise
        log.info("更新 Microsoft 任务：%s", task.title)
        return task

    def delete_task(self, task: Task) -> None:
        if not task.source_list_id or not task.source_id:
            return
        self._client().delete_task(task.source_list_id, task.source_id)
        log.info("删除 Microsoft 任务：%s", task.title)

    def push_attachment(self, task: Task, attachment: TaskAttachment) -> str:
        """把本地附件文件上传到 Microsoft 任务，返回 graph source_url。"""
        if not attachment.local_path or not os.path.isfile(attachment.local_path):
            raise ValueError(f"本地附件文件不存在：{attachment.local_path}")
        with open(attachment.local_path, "rb") as fh:
            content = fh.read()
        content_type = attachment.file_type or "application/octet-stream"
        created = self._client().create_file_attachment(
            task.source_list_id, task.source_id,
            attachment.file_name, content, content_type,
        )
        att_id = created.get("id", "")
        return (
            f"graph://todo/lists/{task.source_list_id}/tasks/"
            f"{task.source_id}/attachments/{att_id}"
        )

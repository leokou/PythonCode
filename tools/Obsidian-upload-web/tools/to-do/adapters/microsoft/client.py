"""Microsoft Graph API 请求封装（To Do 任务相关端点）。

只做 HTTP 请求与 JSON 解析，不做业务映射（映射在 mapper.py）。
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import requests

from .auth import MicrosoftAuth, MicrosoftAuthError

log = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


class GraphError(Exception):
    """Graph API 请求错误。"""

    def __init__(self, message: str, status_code: int = 0, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class GraphClient:
    def __init__(self, auth: MicrosoftAuth, timeout: int = 30):
        self._auth = auth
        self._timeout = timeout

    # ------------------------------------------------------------------
    # 基础请求
    # ------------------------------------------------------------------

    def _headers(self, use_form: bool = False) -> Dict:
        token = self._auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if not use_form:
            headers["Content-Type"] = "application/json"
        return headers

    def _request(self, method: str, url: str, **kwargs) -> Any:
        try:
            resp = requests.request(
                method, url, headers=self._headers(),
                timeout=self._timeout, **kwargs,
            )
        except MicrosoftAuthError:
            raise
        except requests.RequestException as exc:
            raise GraphError(f"网络请求失败：{exc}", response=exc)

        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                detail = resp.text[:300]
            if resp.status_code == 401:
                # 令牌可能过期，尝试退出让用户重新登录
                log.warning("Graph 401：%s", detail)
            raise GraphError(
                f"Graph API {resp.status_code}：{detail}",
                status_code=resp.status_code,
                response=resp,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def _paged(self, url: str) -> List[Dict]:
        """自动翻页收集 Graph 列表结果。"""
        items: List[Dict] = []
        next_url: Optional[str] = url
        while next_url:
            data = self._request("GET", next_url)
            if isinstance(data, dict):
                items.extend(data.get("value", []))
                next_url = data.get("@odata.nextLink")
            else:
                break
        return items

    # ------------------------------------------------------------------
    # To Do 列表
    # ------------------------------------------------------------------

    def todo_lists(self) -> List[Dict]:
        return self._paged(f"{_GRAPH_BASE}/me/todo/lists?$top=100")

    def default_list(self) -> Dict:
        """返回账号的默认任务列表（第一个），没有则创建一个。"""
        lists = self.todo_lists()
        if lists:
            return lists[0]
        return self.create_todo_list("Tasks")

    def find_list_by_name(self, name: str) -> Optional[Dict]:
        for lst in self.todo_lists():
            if lst.get("displayName", "").lower() == name.lower():
                return lst
        return None

    def create_todo_list(self, name: str) -> Dict:
        return self._request(
            "POST", f"{_GRAPH_BASE}/me/todo/lists",
            json={"displayName": name},
        )

    # ------------------------------------------------------------------
    # 任务
    # ------------------------------------------------------------------

    def todo_tasks(self, list_id: str) -> List[Dict]:
        # 注意：不能使用 $select（Graph 对 todoTask 的 $select=title 会 400），
        # 用默认全量返回（含 title / body / status 等全部字段）。
        return self._paged(
            f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks?$top=100"
        )

    def create_task(self, list_id: str, payload: Dict) -> Dict:
        return self._request(
            "POST", f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks", json=payload
        )

    def update_task(self, list_id: str, task_id: str, payload: Dict) -> Dict:
        return self._request(
            "PATCH",
            f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}",
            json=payload,
        )

    def delete_task(self, list_id: str, task_id: str) -> None:
        self._request(
            "DELETE", f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}"
        )

    def get_task(self, list_id: str, task_id: str) -> Dict:
        return self._request(
            "GET",
            f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}",
        )

    # ------------------------------------------------------------------
    # 附件
    # ------------------------------------------------------------------

    def task_attachments(self, list_id: str, task_id: str) -> List[Dict]:
        """返回附件元数据 + contentBytes（base64）。

        不能使用 $select：attachmentBase 基类没有 contentBytes（它在
        taskFileAttachment 派生类型上），select 会 400。用默认全量返回。
        """
        return self._paged(
            f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}/attachments"
        )

    def create_file_attachment(
        self, list_id: str, task_id: str, name: str, content: bytes,
        content_type: str = "image/png",
    ) -> Dict:
        payload = {
            "@odata.type": "#microsoft.graph.taskFileAttachment",
            "name": name,
            "contentType": content_type,
            "contentBytes": base64.b64encode(content).decode("ascii"),
        }
        return self._request(
            "POST",
            f"{_GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}/attachments",
            json=payload,
        )

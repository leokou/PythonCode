"""Leo Todo 核心数据模型（与外部来源完全解耦）。

所有外部任务来源（Microsoft To Do / GitHub Issues / Obsidian Tasks / ...）
必须通过 adapters 层转换成这里的 Task 模型，外部结构不得越过 adapters 层。
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量定义
# ---------------------------------------------------------------------------

# 任务状态（Leo 原生语义，与外部来源的 status 一一映射在 adapters 层完成）
STATUS_TODO = "todo"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_DELETED = "deleted"
ALL_STATUSES = [STATUS_TODO, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_DELETED]

# 优先级
PRIORITY_LOW = "low"
PRIORITY_MEDIUM = "medium"
PRIORITY_HIGH = "high"
ALL_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]

# 同步状态
SYNC_LOCAL = "local"                 # 仅本地，尚未同步到外部
SYNC_SYNCED = "synced"               # 已与外部来源一致
SYNC_PENDING_PUSH = "pending_push"   # 本地有变更，待推送外部
SYNC_PENDING_DELETE = "pending_delete"  # 已软删除，待推送删除到外部
SYNC_ERROR = "error"                 # 推送失败，等待重试
ALL_SYNC_STATUSES = [
    SYNC_LOCAL, SYNC_SYNCED, SYNC_PENDING_PUSH, SYNC_PENDING_DELETE, SYNC_ERROR,
]

# 任务来源
SOURCE_LEO = "leo"
SOURCE_MICROSOFT = "microsoft"

# 支持预览的图片扩展名
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------

_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)


def now_iso() -> str:
    """当前 UTC 时间，ISO 毫秒精度，如 2026-08-01T12:34:56.123Z。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_ts(value: Any) -> Optional[datetime]:
    """宽容解析 ISO 时间字符串，返回 UTC aware datetime；解析失败返回 None。"""
    if not value:
        return None
    m = _TS_RE.match(str(value).strip())
    if not m:
        return None
    base, frac, tz = m.group(1), m.group(2) or "", m.group(3) or ""
    if frac:
        # 统一为微秒精度（最多 6 位），保证比较稳定
        frac = frac.ljust(7, "0")[:7]
    iso = base + frac + (tz if tz else "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_ts(value: Any) -> str:
    """把任意 ISO 时间规范化为统一的 UTC 毫秒格式（保证字典序可比）。"""
    dt = parse_ts(value)
    if dt is None:
        return str(value) if value else ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_id(prefix: str = "leo_task") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def new_attachment_id() -> str:
    return f"leo_att_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Task 数据模型
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """Leo Todo 任务模型。

    字段说明：
      id            本地唯一 id（UUID）
      title         任务标题
      description   任务描述
      status        todo / in_progress / completed / deleted
      priority      low / medium / high
      project       所属项目（对 Microsoft 来源即为任务列表名）
      tags          标签列表（list[str]；数据库中以 JSON 字符串保存）
      source        任务来源（leo / microsoft / ...）
      source_id     外部来源的任务 id（用于同步路由判断）
      source_list_id 外部来源的容器/列表 id（同步时路由到正确列表）
      due_date      截止时间（ISO UTC 字符串）
      created_at    创建时间（ISO UTC）
      updated_at    最后修改时间（ISO UTC，冲突解决 Last-Write-Wins 依据）
      sync_status   local / synced / pending_push / pending_delete / error
    """

    id: str = ""
    title: str = ""
    description: str = ""
    status: str = STATUS_TODO
    priority: str = PRIORITY_MEDIUM
    project: str = ""
    tags: list = field(default_factory=list)
    source: str = SOURCE_LEO
    source_id: str = ""
    source_list_id: str = ""
    due_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    sync_status: str = SYNC_LOCAL

    def __post_init__(self) -> None:
        if not self.id:
            self.id = new_id()
        if not self.created_at:
            self.created_at = now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at
        if isinstance(self.tags, str):
            self.tags = json.loads(self.tags) if self.tags else []
        if not isinstance(self.tags, list):
            self.tags = []
        self.updated_at = normalize_ts(self.updated_at)
        self.created_at = normalize_ts(self.created_at)
        self.due_date = normalize_ts(self.due_date)

    def touch(self) -> None:
        self.updated_at = now_iso()

    @property
    def is_deleted(self) -> bool:
        return self.status == STATUS_DELETED

    @property
    def is_completed(self) -> bool:
        return self.status == STATUS_COMPLETED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "project": self.project,
            "tags": list(self.tags),
            "source": self.source,
            "source_id": self.source_id,
            "source_list_id": self.source_list_id,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sync_status": self.sync_status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        clean = {k: data.get(k) for k in (
            "id", "title", "description", "status", "priority", "project",
            "tags", "source", "source_id", "source_list_id", "due_date",
            "created_at", "updated_at", "sync_status",
        )}
        # 只保留非 None 字段，让 dataclass 默认值生效（前端可能只传部分字段）
        clean = {k: v for k, v in clean.items() if v is not None}
        return cls(**clean)


# ---------------------------------------------------------------------------
# 附件数据模型
# ---------------------------------------------------------------------------


@dataclass
class TaskAttachment:
    """任务附件（图片 / 文件）。

    source_url 对外部来源而言是该附件的唯一标识（用于去重），
    例如 Microsoft 的 graph://todo/lists/{listId}/tasks/{taskId}/attachments/{attId}。
    """

    id: str = ""
    task_id: str = ""
    file_name: str = ""
    file_type: str = ""
    source: str = ""
    source_url: str = ""
    local_path: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = new_attachment_id()
        if not self.created_at:
            self.created_at = now_iso()
        self.created_at = normalize_ts(self.created_at)

    @property
    def is_image(self) -> bool:
        ext = _ext_of(self.file_name)
        return ext.lower() in IMAGE_EXTS

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "source": self.source,
            "source_url": self.source_url,
            "local_path": self.local_path,
            "created_at": self.created_at,
            "is_image": self.is_image,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskAttachment":
        clean = {k: data.get(k) for k in (
            "id", "task_id", "file_name", "file_type", "source",
            "source_url", "local_path", "created_at",
        )}
        return cls(**clean)


def _ext_of(file_name: str) -> str:
    idx = file_name.rfind(".")
    if idx == -1:
        return ""
    return file_name[idx:]


# ---------------------------------------------------------------------------
# 统计 / 同步报告
# ---------------------------------------------------------------------------


@dataclass
class TaskStats:
    total: int = 0
    active: int = 0
    in_progress: int = 0
    completed: int = 0
    deleted: int = 0
    overdue: int = 0
    project_count: int = 0
    tag_count: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class SyncReport:
    """一次同步的执行报告。"""

    source: str = ""
    started_at: str = ""
    finished_at: str = ""
    pulled: int = 0          # 外部拉取到的任务数
    created: int = 0         # 本地新增
    updated: int = 0         # 本地更新（外部版本较新）
    deleted_local: int = 0   # 外部已删除，本地软删除
    pushed_create: int = 0   # 推送外部新增
    pushed_update: int = 0   # 推送外部更新
    pushed_delete: int = 0   # 推送外部删除
    attachments_pulled: int = 0
    attachments_pushed: int = 0
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

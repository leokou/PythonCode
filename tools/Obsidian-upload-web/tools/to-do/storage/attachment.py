"""附件文件管理：把外部附件下载/缓存到 data/attachments/，供 UI 本地预览。

只负责文件落盘与路径解析；数据库记录由 TaskManager 维护。
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional

from core.models import IMAGE_EXTS

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n\t]')


class AttachmentStore:
    """附件存储目录管理器。"""

    def __init__(self, dir_path: str, image_exts=IMAGE_EXTS):
        self._dir = os.path.abspath(dir_path)
        self._image_exts = tuple(e.lower() for e in (image_exts or IMAGE_EXTS))
        os.makedirs(self._dir, exist_ok=True)

    @property
    def dir_path(self) -> str:
        return self._dir

    def is_image_ext(self, file_name: str) -> bool:
        _, ext = os.path.splitext(file_name)
        return ext.lower() in self._image_exts

    def safe_file_name(self, file_name: str) -> str:
        """清理文件名中的非法字符，防止路径穿越。"""
        name = _SAFE_NAME_RE.sub("_", file_name or "attachment")
        name = name.strip(". ")
        return name or "attachment"

    def resolve_path(self, task_id: str, file_name: str) -> str:
        """生成附件落盘路径（task_id 子目录 + 短 uuid 前缀，避免重名覆盖）。"""
        safe = self.safe_file_name(file_name)
        sub = os.path.join(self._dir, task_id)
        os.makedirs(sub, exist_ok=True)
        return os.path.join(sub, f"{uuid.uuid4().hex[:8]}_{safe}")

    def save_bytes(self, task_id: str, file_name: str, data: bytes) -> str:
        """把字节内容写入附件目录，返回绝对路径。"""
        path = self.resolve_path(task_id, file_name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def save_file(self, task_id: str, src_path: str, file_name: Optional[str] = None) -> str:
        """把本地文件复制进附件目录，返回绝对路径。"""
        import shutil

        name = file_name or os.path.basename(src_path)
        dest = self.resolve_path(task_id, name)
        shutil.copyfile(src_path, dest)
        return dest

    def delete_file(self, local_path: str) -> bool:
        """删除单个附件文件（不存在返回 False，不抛异常）。"""
        try:
            if local_path and os.path.isfile(local_path):
                os.remove(local_path)
                return True
        except OSError:
            return False
        return False

    def clean_orphan_files(self, keep_paths: set) -> int:
        """删除附件目录中不在 keep_paths 集合里的文件（清理孤儿附件），返回删除数。"""
        removed = 0
        if not os.path.isdir(self._dir):
            return 0
        for root, _dirs, files in os.walk(self._dir):
            for name in files:
                full = os.path.join(root, name)
                if full not in keep_paths:
                    try:
                        os.remove(full)
                        removed += 1
                    except OSError:
                        pass
        return removed

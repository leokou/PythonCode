"""附件存储测试：路径解析 / 保存 / 孤儿清理。"""
from __future__ import annotations

import os
import tempfile
import unittest

from storage.attachment import AttachmentStore


class AttachmentStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="leo_todo_att_")
        self.store = AttachmentStore(os.path.join(self.tmpdir, "attachments"))

    def test_is_image_ext(self):
        self.assertTrue(self.store.is_image_ext("a.png"))
        self.assertTrue(self.store.is_image_ext("A.JPG"))
        self.assertTrue(self.store.is_image_ext("b.webp"))
        self.assertFalse(self.store.is_image_ext("doc.pdf"))
        self.assertFalse(self.store.is_image_ext("noext"))

    def test_safe_file_name(self):
        self.assertEqual(self.store.safe_file_name('a/b:c*.png'), "a_b_c_.png")
        # 反斜杠替换 + 前置点清理（防止路径穿越）
        self.assertEqual(self.store.safe_file_name("..\\..\\evil.png"), "_.._evil.png")
        self.assertNotIn("\\", self.store.safe_file_name("..\\..\\evil.png"))

    def test_save_bytes_and_read(self):
        data = b"\x89PNG\r\n\x1a\n1234"
        path = self.store.save_bytes("task_1", "shot.png", data)
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), data)
        # 重名不覆盖（带 uuid 前缀）
        path2 = self.store.save_bytes("task_1", "shot.png", b"other")
        self.assertNotEqual(path, path2)

    def test_save_file_copy(self):
        src = os.path.join(self.tmpdir, "orig.txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("hello")
        dest = self.store.save_file("task_2", src, "copy.txt")
        self.assertTrue(os.path.isfile(dest))
        with open(dest, "r", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "hello")

    def test_delete_file(self):
        path = self.store.save_bytes("t", "x.png", b"1")
        self.assertTrue(self.store.delete_file(path))
        self.assertFalse(self.store.delete_file(path))
        self.assertFalse(self.store.delete_file("C:/not/exist.png"))

    def test_clean_orphan_files(self):
        keep = self.store.save_bytes("t1", "keep.png", b"1")
        orphan = self.store.save_bytes("t1", "orphan.png", b"2")
        removed = self.store.clean_orphan_files({keep})
        self.assertEqual(removed, 1)
        self.assertTrue(os.path.isfile(keep))
        self.assertFalse(os.path.isfile(orphan))


if __name__ == "__main__":
    unittest.main()

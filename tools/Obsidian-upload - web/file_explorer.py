# -*- coding: utf-8 -*-
"""工作区资源管理器后端（file_explorer.py V1.0）。

职责：
- 文件夹管理：folders() / add_folder() / remove_folder()（复用 workspace.py，workspace.json 持久化）
- 文件扫描：scan(path, sort, cfg)（复用 file_tree.py 懒加载扫描 + 时间/名称排序）
- 文件打开：open_file(path)（读取内容 + record_open 记录最近打开，复用 history.py）
- 排序偏好：get_sort_pref() / set_sort_pref()（复用 layout_store.py，存 config.json layout.explorer_sort）

设计原则：
- 只做编排与薄转发，复用 workspace / file_tree / history / layout_store，
  不复制底层逻辑（公共能力抽离）。
- 不依赖 UI / 网络，可独立测试。main.py 的 js_api 只做薄转发。
"""
import os

import file_ops
import file_tree
import history
import layout_store
import workspace

SORT_TIME = "time"
SORT_NAME = "name"
DEFAULT_SORT = SORT_TIME


def folders():
    """当前工作区文件夹列表（副本）。"""
    return workspace.folders()


def add_folder(path):
    """添加工作区文件夹。返回 (ok, msg, folders)。"""
    return workspace.add_folder(path)


def remove_folder(path):
    """移除工作区文件夹。返回 (ok, msg, folders)。"""
    return workspace.remove_folder(path)


def scan(path, sort=DEFAULT_SORT, cfg=None):
    """扫描目录 path 的直接子项（懒加载，前端展开目录时调用）。

    sort: "time" 最近修改时间倒序（默认，最新在前）| "name" 名称 A-Z。
    返回 [{name, path, type, ext, mtime}]，无效 sort 回退默认。
    """
    if sort not in (SORT_TIME, SORT_NAME):
        sort = DEFAULT_SORT
    return file_tree.scan_dir(path, cfg or {}, sort=sort)


def open_file(path):
    """文件打开接口：读取文件内容 + 记录最近打开。

    返回 {"ok": True, "content", "title", "path"}；文件不存在或读取失败返回 ok=False。
    """
    if not path or not os.path.exists(path):
        return {"ok": False, "msg": "文件不存在或已移动"}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        history.record_open(path)
        return {"ok": True, "content": content,
                "title": os.path.basename(path), "path": os.path.normpath(path)}
    except Exception as e:
        return {"ok": False, "msg": "打开文件失败：%s" % e}


def get_sort_pref():
    """当前资源树排序偏好（默认时间倒序）。"""
    return layout_store.load_layout().get("explorer_sort", DEFAULT_SORT)


def set_sort_pref(sort):
    """保存资源树排序偏好到 config.json layout 字段。成功返回 True。"""
    if sort not in (SORT_TIME, SORT_NAME):
        return False
    layout = layout_store.load_layout()
    layout["explorer_sort"] = sort
    return layout_store.save_layout(layout)


def all_dirs(cfg=None):
    """工作区内所有目录（含子目录，跳过隐藏目录）。返回 [{path, level, name, rel}]。

    - level：相对所属工作区根的层级（0=根目录）
    - name：目录名；rel：相对所属工作区根的路径（根为 "."）
    按路径排序（父子相邻，供移动弹窗树形展示）。
    """
    roots = [f["path"] for f in folders()]
    out = []
    for d in file_tree.iter_dirs(roots, cfg or {}):
        root = None
        level = 0
        relpath = "."
        for r in roots:
            try:
                rel = os.path.relpath(d, r)
            except Exception:
                continue
            if rel == ".":
                root, level, relpath = r, 0, "."
                break
            if not rel.startswith(".."):
                root, level, relpath = r, rel.count(os.sep) + 1, rel
                break
        out.append({
            "path": os.path.normpath(d),
            "level": level,
            "name": os.path.basename(d) or d,
            "rel": relpath,
        })
    out.sort(key=lambda x: x["path"].lower())
    return out


def duplicate(path):
    """复制文件副本到当前目录。返回 (ok, msg, new_path)。"""
    return file_ops.duplicate_file(path)


def new_folder(parent):
    """在指定目录内新建文件夹。返回 (ok, msg, new_path)。"""
    return file_ops.create_folder(parent)


def new_file(parent):
    """在指定目录内新建 Markdown 文件。返回 (ok, msg, new_path)。"""
    return file_ops.create_file(parent)


def move(path, dest_dir):
    """移动文件/文件夹到目标目录，同步历史记录。返回 (ok, msg, new_path)。"""
    return file_ops.move_item(path, dest_dir)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sort = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SORT
    print("sort=%s  folders=%s" % (sort, [f["path"] for f in folders()]))
    for it in scan(root, sort):
        print("%s\t%s\t%s" % (it["type"], it["name"], round(it["mtime"], 1)))

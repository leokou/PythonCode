# -*- coding: utf-8 -*-
"""图片保存模块：base64 / 网络 URL / 剪贴板位图 → attachments 目录。

支持三种图片来源（对应任务情况 A/B/C）：
- data:image/...;base64,... → 直接解码保存（情况 A）
- http(s)://... → requests 下载保存（情况 B）
- 剪贴板位图 CF_BITMAP/CF_DIB/CF_DIBV5 → Pillow 保存（情况 C）

命名规则：Pasted-image-yyyyMMdd-HHmmss.png，重名自动 -001/-002。
设计原则：无 UI 依赖，可独立测试；失败返回 None，不影响文字粘贴。
"""
import base64
import io
import os
from datetime import datetime

from PIL import Image, ImageGrab

from commands.logger import log_info, log_error, log_warn
from lib.backend import markdown as mdlib

# 支持的图片扩展名（用于从 URL/文件名推断扩展名）
_IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")


def attachments_dir(cfg=None, log_dir=None):
    """取附件保存目录：config.json attachments_dir 优先，否则默认保存路径/attachments。

    目录不存在自动创建。
    """
    if cfg and cfg.get("attachments_dir"):
        d = cfg["attachments_dir"]
    else:
        from lib.core import settings as settings_store
        root = settings_store.get_default_save_path(cfg)
        d = os.path.join(root, "attachments")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as e:
        log_error("创建附件目录失败(%s): %s" % (d, e))
    return d


def _pasted_base_name():
    """生成 Pasted-image-yyyyMMdd-HHmmss 基名。"""
    return "Pasted-image-%s" % datetime.now().strftime("%Y%m%d-%H%M%S")


def _unique_filename(directory, base, ext):
    """生成不冲突的文件路径：base.ext / base-001.ext / base-002.ext ..."""
    ext = ext.lower() if ext else ".png"
    if ext and not ext.startswith("."):
        ext = "." + ext
    candidate = os.path.join(directory, base + ext)
    if not os.path.exists(candidate):
        return candidate
    i = 1
    while True:
        candidate = os.path.join(directory, "%s-%03d%s" % (base, i, ext))
        if not os.path.exists(candidate):
            return candidate
        i += 1


def _save_pil_image(img, directory, ext=".png"):
    """把 PIL 图片保存为附件，返回文件路径。"""
    os.makedirs(directory, exist_ok=True)
    path = _unique_filename(directory, _pasted_base_name(), ext)
    fmt = "PNG"
    if ext in (".jpg", ".jpeg"):
        fmt = "JPEG"
    elif ext == ".gif":
        fmt = "GIF"
    elif ext == ".webp":
        fmt = "WEBP"
    elif ext == ".bmp":
        fmt = "BMP"
    if fmt in ("JPEG", "PNG", "BMP"):
        img = img.convert("RGB")
    img.save(path, format=fmt)
    return path


def save_base64(data_url, directory, log_dir=None):
    """保存 data:image/xxx;base64,... 图片。返回文件名或 None。"""
    try:
        if not data_url or "," not in data_url:
            log_warn("base64 图片格式无效（缺少逗号）")
            return None
        os.makedirs(directory, exist_ok=True)
        header, raw = data_url.split(",", 1)
        ext = _ext_from_mime(header)
        data = base64.b64decode(raw)
        if ext == ".svg":
            # SVG 是矢量文本，直接写文件
            path = _unique_filename(directory, _pasted_base_name(), ".svg")
            with open(path, "wb") as f:
                f.write(data)
        else:
            img = Image.open(io.BytesIO(data))
            # 统一转 PNG 避免格式/颜色模式问题
            path = _save_pil_image(img, directory, ".png")
        log_info("已保存 base64 图片: %s" % os.path.basename(path))
        return os.path.basename(path)
    except Exception as e:
        log_error("保存 base64 图片失败: %s" % e)
        mdlib.log_debug("保存 base64 图片失败: %s" % e, log_dir)
        return None


def save_url(url, directory, log_dir=None):
    """下载并保存网络图片。返回文件名或 None。"""
    try:
        import requests
        os.makedirs(directory, exist_ok=True)
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": url,
        })
        if resp.status_code != 200:
            log_warn("下载图片失败 HTTP %s: %s" % (resp.status_code, url))
            mdlib.log_debug("下载图片失败 HTTP %s: %s" % (resp.status_code, url), log_dir)
            return None
        ext = _ext_from_url(url, resp.headers.get("Content-Type", ""))
        data = resp.content
        if ext == ".svg":
            path = _unique_filename(directory, _pasted_base_name(), ".svg")
            with open(path, "wb") as f:
                f.write(data)
        else:
            try:
                img = Image.open(io.BytesIO(data))
                path = _save_pil_image(img, directory, ".png")
            except Exception:
                # Pillow 无法解码，按原始字节保存
                path = _unique_filename(directory, _pasted_base_name(), ext)
                with open(path, "wb") as f:
                    f.write(data)
        log_info("已下载网络图片: %s <- %s" % (os.path.basename(path), url))
        return os.path.basename(path)
    except Exception as e:
        log_error("下载网络图片失败(%s): %s" % (url, e))
        mdlib.log_debug("下载网络图片失败(%s): %s" % (url, e), log_dir)
        return None


def save_clipboard_bitmap(directory, log_dir=None):
    """保存剪贴板位图（截图 CF_BITMAP/CF_DIB）。返回文件名或 None。

    ImageGrab.grabclipboard() 返回：
    - PIL.Image：截图位图 → 直接保存
    - list[str]：文件路径列表 → 取第一个图片文件复制保存
    - None：剪贴板无图片
    """
    try:
        os.makedirs(directory, exist_ok=True)
        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        if isinstance(img, Image.Image):
            path = _save_pil_image(img, directory, ".png")
            log_info("已保存剪贴板位图: %s" % os.path.basename(path))
            return os.path.basename(path)
        if isinstance(img, list) and img:
            # 文件列表：取第一个图片文件
            for f in img:
                fstr = str(f)
                if fstr.lower().endswith(_IMG_EXTS) and os.path.isfile(fstr):
                    try:
                        im = Image.open(fstr)
                        path = _save_pil_image(im, directory, ".png")
                        log_info("已保存剪贴板图片文件: %s" % os.path.basename(path))
                        return os.path.basename(path)
                    except Exception as e:
                        log_warn("读取剪贴板图片文件失败(%s): %s" % (fstr, e))
                        continue
        return None
    except Exception as e:
        log_error("保存剪贴板位图失败: %s" % e)
        mdlib.log_debug("保存剪贴板位图失败: %s" % e, log_dir)
        return None


def save_image(src, directory, log_dir=None):
    """根据 src 类型分派保存。返回文件名或 None。

    分派规则：
    - data:image/...;base64,... → save_base64（情况 A）
    - http(s)://... → save_url（情况 B）
    - blob:... → 无法下载（浏览器内部引用），返回 None
    - file:///... 或本地路径 → 复制保存
    - 其他 → None
    """
    if not src:
        return None
    src = src.strip()
    if not src:
        return None
    if src.startswith("data:"):
        return save_base64(src, directory, log_dir)
    if src.startswith(("http://", "https://")):
        return save_url(src, directory, log_dir)
    if src.startswith("blob:"):
        log_warn("blob: URL 图片无法直接下载（浏览器运行时引用）: %s" % src[:80])
        mdlib.log_debug("blob: URL 图片无法下载: %s" % src, log_dir)
        return None
    if src.startswith("file://"):
        local = src[7:].lstrip("/")
        return _save_local_file(local, directory)
    # Windows 绝对路径（D:\...）
    if len(src) > 2 and src[1] == ":":
        return _save_local_file(src, directory)
    log_warn("未知图片 src 格式: %s" % src[:80])
    return None


def _save_local_file(path, directory):
    """复制本地图片文件到附件目录，返回文件名或 None。"""
    try:
        if not path or not os.path.isfile(path):
            return None
        os.makedirs(directory, exist_ok=True)
        ext = os.path.splitext(path)[1].lower() or ".png"
        if ext not in _IMG_EXTS:
            ext = ".png"
        try:
            im = Image.open(path)
            saved = _save_pil_image(im, directory, ".png")
        except Exception:
            import shutil
            saved = _unique_filename(directory, _pasted_base_name(), ext)
            shutil.copy2(path, saved)
        log_info("已复制本地图片: %s" % os.path.basename(saved))
        return os.path.basename(saved)
    except Exception as e:
        log_error("复制本地图片失败(%s): %s" % (path, e))
        return None


def _ext_from_mime(header):
    """从 data URL 头（data:image/xxx;base64）推断扩展名。"""
    h = (header or "").lower()
    if "image/jpeg" in h or "image/jpg" in h:
        return ".jpg"
    if "image/gif" in h:
        return ".gif"
    if "image/webp" in h:
        return ".webp"
    if "image/svg+xml" in h:
        return ".svg"
    if "image/bmp" in h:
        return ".bmp"
    return ".png"


def _ext_from_url(url, content_type):
    """从 URL 路径或 Content-Type 推断图片扩展名。"""
    url_clean = url.lower().split("?")[0].split("#")[0]
    for ext in _IMG_EXTS:
        if url_clean.endswith(ext):
            return ext
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "gif" in ct:
        return ".gif"
    if "webp" in ct:
        return ".webp"
    if "svg" in ct:
        return ".svg"
    if "bmp" in ct:
        return ".bmp"
    return ".png"


if __name__ == "__main__":
    # 简单自测：保存剪贴板位图
    d = os.path.join(os.path.dirname(__file__), "_test_attachments")
    fn = save_clipboard_bitmap(d)
    print("save_clipboard_bitmap:", fn)

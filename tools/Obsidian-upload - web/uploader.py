# -*- coding: utf-8 -*-
"""图片上传模块：剪贴板图片 → PicGo HTTP API → Cloudflare R2 → Markdown 链接。

无 GUI 依赖，供 main.py（pywebview）调用。
"""
import io
import os
import time
from datetime import datetime

from PIL import Image, ImageGrab


def clipboard_image():
    """读取剪贴板图片，返回 (PIL.Image | None, error)"""
    try:
        img = ImageGrab.grabclipboard()
    except Exception as e:
        return None, "读取剪贴板失败：%s" % e
    if img is None:
        return None, "剪贴板没有图片（检测到的是文字或其他内容）"
    if not isinstance(img, Image.Image):
        return None, "剪贴板内容不是图片"
    return img, None


def image_to_png_bytes(img):
    """把 PIL 图片编码为 PNG 字节"""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def picgo_filename():
    return "Pasted-image-%s.png" % datetime.now().strftime("%Y%m%d-%H%M%S")


def upload_to_picgo(png_bytes, filename, picgo_url):
    """调用 PicGo HTTP API 上传。

    返回 (ok, url, debug_dict)。
    PicGo 上传接口为 multipart 字段名 files（multer upload.array("files")）。
    """
    import requests

    debug = {}
    try:
        resp = requests.post(
            picgo_url,
            files={"files": (filename, png_bytes, "image/png")},
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        debug["service_status"] = "PicGo 服务未启动（连接失败）"
        return False, None, debug
    except requests.exceptions.Timeout:
        debug["service_status"] = "PicGo 服务超时"
        return False, None, debug
    except Exception as e:
        debug["service_status"] = "请求异常：%s" % e
        return False, None, debug

    debug["status"] = resp.status_code
    debug["body"] = None
    try:
        data = resp.json()
        debug["body"] = data
    except Exception:
        return False, None, debug

    ok_flag = bool(data.get("success"))
    result = data.get("result") or []
    if not ok_flag or not result:
        debug["hint"] = "PicGo 返回 success=%s，result=%r" % (ok_flag, result)
        return False, None, debug
    url = str(result[0]).strip()
    if not url.startswith("http"):
        debug["hint"] = "PicGo 返回的 URL 不合法：%r" % url
        return False, None, debug
    debug["service_status"] = "PicGo 正常"
    return True, url, debug


def generate_markdown(url):
    return "![image](%s)" % url


def decode_base64_png(data_url):
    """把前端传回的 data:image/xxx;base64,... 解码为 PIL 图片"""
    import base64
    if "," not in data_url:
        raise ValueError("图片数据格式不正确")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return Image.open(io.BytesIO(raw))

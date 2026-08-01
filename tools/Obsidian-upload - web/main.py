# -*- coding: utf-8 -*-
"""LeoDiary Capture —— Markdown + 图片上传 + Obsidian 快速记录工具。

技术栈：Python + HTML/CSS/JS + Edge WebView2（pywebview 6.x）
界面：深色主题（Obsidian 风格），左 50% Markdown 编辑（CodeMirror 6）+ 右 50% 实时预览（marked.js），按比例双向同步滚动
托盘：pystray 常驻，点 X 隐藏到托盘
热键：Alt+S 呼出主窗口
上传：Ctrl+V 剪贴板图片 → PicGo HTTP API → Cloudflare R2 → 插入 ![](URL)
保存：#### yyyy-MM-dd HH:mm:ss + 正文 + ---，追加到目标 md 文件
日志：追加到日志目录下 yyyy-MM-dd 周X.md（自动按系统日期命名）

打包：
    pyinstaller --onefile --windowed --add-data "web;web" --add-data "config.json;." main.py
"""
import ctypes
import json
import os
import sys
import threading
from datetime import datetime

import webview

import markdown as mdlib
import uploader

APP_TITLE = "LeoDiary Capture"
DEFAULT_CONFIG = {
    "picgo_api": "http://127.0.0.1:36677/upload",
    "cloudflare_domain": "",
    "inbox_file": r"D:\Obsidian\LeoDiary\My-Inbox.md",
    "flashnote_file": r"D:\Obsidian\LeoDiary\🧠 FlashNote.md",
    "log_dir": r"D:\Obsidian\LeoDiary\Journals",
    "vault_name": "LeoDiary",
}

_exit_lock = threading.Lock()


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_config():
    """优先读取 EXE/脚本旁 config.json，缺省用内置默认值并补全缺键。"""
    cfg = dict(DEFAULT_CONFIG)
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "config.json"))
    candidates.append(resource_path("config.json"))
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                cfg.update(loaded)
            except Exception:
                pass
            break
    return cfg


def show_error_box(title, msg):
    """错误弹窗（不使用 Tkinter）"""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(msg), str(title), 0x10)
    except Exception:
        pass


def log_dir():
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "Obsidian-upload")


class Api:
    """pywebview js_api：前端通过 pywebview.api.xxx() 调用。"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.log = os.path.join(log_dir(), "upload_debug.log")
        self._init_log_dir()

    def _init_log_dir(self):
        try:
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
        except Exception:
            pass

    def _target_file(self, target):
        if target == "inbox":
            return self.cfg["inbox_file"]
        return self.cfg["flashnote_file"]

    # ---- 图片上传 ----
    def upload_image(self, data_url):
        try:
            img = uploader.decode_base64_png(data_url)
            png = uploader.image_to_png_bytes(img)
            name = uploader.picgo_filename()
            ok, url, debug = uploader.upload_to_picgo(
                png, name, self.cfg["picgo_api"])
            if not ok:
                msg = debug.get("hint") or debug.get("service_status") or "上传失败"
                mdlib.log_debug(
                    "==================\nUpload Failed\n==================\n%s"
                    % json.dumps(debug, ensure_ascii=False, indent=2),
                    log_dir())
                return {"ok": False, "msg": msg}
            link = uploader.generate_markdown(url)
            mdlib.log_debug(
                "==================\nUpload Success\n==================\n"
                "Original File:\n%s\n\nRemote URL:\n%s\n\nMarkdown:\n%s\n"
                "==================" % (name, url, link),
                log_dir())
            return {"ok": True, "url": url, "markdown": link}
        except Exception as e:
            return {"ok": False, "msg": "图片处理失败：%s" % e}

    # ---- 保存 ----
    def save(self, content, target):
        if not content or not content.strip():
            return {"ok": False, "msg": "没有内容可保存"}
        path = self._target_file(target)
        try:
            ts = mdlib.append_note(path, content)
        except Exception as e:
            return {"ok": False, "msg": "保存失败：%s" % e}
        return {"ok": True,
                "msg": "已保存到 %s · %s" % (os.path.basename(path), ts)}

    # ---- 保存日志（日志目录\yyyy-MM-dd 周X.md，追加写入） ----
    def save_log(self, content):
        if not content or not content.strip():
            return {"ok": False, "msg": "没有内容可保存"}
        now = datetime.now()
        weekday = "周" + "一二三四五六日"[now.weekday()]
        name = "%s %s.md" % (now.strftime("%Y-%m-%d"), weekday)
        d = self.cfg.get("log_dir") or r"D:\Obsidian\LeoDiary\Journals"
        try:
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, name)
            ts = mdlib.append_note(path, content)
        except Exception as e:
            return {"ok": False, "msg": "日志保存失败：%s" % e}
        return {"ok": True,
                "msg": "已保存日志 %s · %s" % (name, ts)}

    # ---- 前端弹窗 ----
    def show_error(self, title, msg):
        show_error_box(title, msg)
        return True


def make_tray_icon():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(52, 120, 246, 255))
    d.polygon(
        [(32, 14), (20, 30), (27, 30), (27, 46), (37, 46), (37, 30), (44, 30)],
        fill="white")
    return img


def main():
    cfg = load_config()
    api = Api(cfg)
    state = {"quitting": False}

    index_path = os.path.abspath(resource_path(os.path.join("web", "index.html")))
    if not os.path.exists(index_path):
        show_error_box(APP_TITLE, "找不到界面文件：%s\n请重新打包（--add-data \"web;web\"）。" % index_path)
        return 1

    try:
        # 获取屏幕尺寸，居中显示
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        ww, wh = 1600, 950
        wx = max(0, (sw - ww) // 2)
        wy = max(0, (sh - wh) // 2)

        window = webview.create_window(
            APP_TITLE,
            url=index_path,
            js_api=api,
            width=ww,
            height=wh,
            x=wx,
            y=wy,
            min_size=(1280, 720),
        )
    except Exception as e:
        show_error_box(APP_TITLE, "创建窗口失败（需要 Edge WebView2 Runtime）：\n%s" % e)
        return 1

    # ---- 点 X：隐藏到托盘而不是退出 ----
    def on_closing(*_args):
        if state["quitting"]:
            return True
        try:
            window.hide()
        except Exception:
            pass
        return False

    window.events.closing += on_closing

    # ---- 托盘常驻 ----
    def tray_run():
        try:
            import pystray
        except ImportError:
            return
        menu = pystray.Menu(
            pystray.MenuItem("打开窗口", lambda i, it: window.show(), default=True),
            pystray.MenuItem("退出程序", lambda i, it: exit_app()),
        )
        icon = pystray.Icon("obsidian-upload", make_tray_icon(), APP_TITLE, menu)
        icon.run()

    def exit_app():
        with _exit_lock:
            if state["quitting"]:
                return
            state["quitting"] = True
        try:
            window.destroy()
        except Exception:
            os._exit(0)

    threading.Thread(target=tray_run, daemon=True).start()

    # ---- 全局热键：Alt+S 呼出主窗口（pywebview 方法线程安全） ----
    def summon():
        try:
            window.show()
        except Exception:
            pass

    try:
        import keyboard
        try:
            keyboard.add_hotkey("alt+s", summon, suppress=False)
        except Exception:
            pass
    except ImportError:
        pass

    try:
        webview.start(debug=False, gui="edgechromium")
    except Exception as e:
        show_error_box(APP_TITLE, "启动失败：%s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

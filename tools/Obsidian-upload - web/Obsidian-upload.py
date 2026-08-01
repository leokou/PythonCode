# -*- coding: utf-8 -*-
r"""
Obsidian-upload —— Obsidian 笔记快速上传工具（PicGo 图床版）

职责
    Markdown Capture   : 快速抓取 Markdown 笔记，写入 LeoDiary（FlashNote / Inbox）
    Image Upload       : Ctrl+V 剪贴板图片 → PicGo HTTP API → Cloudflare R2 图床 → 返回 URL → 生成 Markdown 引用
    Preview            : HTML 渲染预览（Markdown → HTML，远程图片自动缓存显示）
    Obsidian 快捷呼出  : Alt+S 呼出窗口并打开 My-Inbox.md，Alt+E 呼出窗口并打开 🧠 FlashNote.md（obsidian:// URI）
    系统托盘常驻       : 点击窗口 X 隐藏到托盘，后台继续运行；保存后自动隐藏

快捷键
    Ctrl+V     粘贴剪贴板图片并上传 PicGo → Cloudflare R2，生成 ![](URL)
    Ctrl+Enter 保存笔记到当前目标（FlashNote / Inbox），保存后自动隐藏到托盘
    Alt+S      全局热键：呼出工具窗口 + 打开 My-Inbox.md（obsidian:// URI）
    Alt+E      全局热键：呼出工具窗口 + 打开 🧠 FlashNote.md（obsidian:// URI）

图片上传流程
    剪贴板图片
        ↓
    Obsidian-upload.exe
        ↓
    PicGo HTTP API   http://127.0.0.1:36677/upload（multipart/form-data，字段 files）
        ↓
    Cloudflare R2 图床
        ↓
    返回图片 URL（result[0]）
        ↓
    生成 Markdown 引用   ![](https://cdn.xxx.com/Pasted-image-xxxx.png)

说明
    · 不保存图片到本地（禁止本地 PNG 永久保存，不再使用本地 attachments 目录）
    · 职责分离：Obsidian 编辑 / Image Auto Upload 触发 / PicGo 上传 / Cloudflare R2 存储
    · 代码不直接操作 Cloudflare，只调用本地 PicGo 服务

文件结构
    Obsidian-upload.py

    D:\Obsidian\LeoDiary
    ├── 🧠 FlashNote.md
    └── My-Inbox.md

运行
    python Obsidian-upload.py

打包 EXE
    pyinstaller -F -w Obsidian-upload.py

生成
    dist
    └── Obsidian-upload.exe

依赖
    Pillow     读取剪贴板图片
    requests   调用 PicGo API / 缓存预览远程图片
    pyperclip  复制 Markdown 链接到剪贴板
    pystray    系统托盘图标
    keyboard   全局热键（Alt+S / Alt+E）
    markdown   Markdown → HTML 渲染预览
    tkinterweb HTML 预览组件（HtmlFrame）
    缺少时自动提示安装。

调试日志
    上传成功 / 失败均写入：
    %APPDATA%\Obsidian-upload\upload_debug.log
    成功日志格式：
    ==================
    Upload Success
    ==================
    Original File: xxx.png
    Remote URL:    https://xxx
    Markdown:      ![](https://xxx)
    ==================

建议后续改进
    Obsidian-upload.exe
    ├── OCR
    ├── AI 摘要
    └── 自动标签
"""

import hashlib
import io
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.parse
from datetime import datetime
from tkinter import ttk, messagebox

VAULT = r"D:\Obsidian\LeoDiary"
FLASHNOTE = os.path.join(VAULT, "🧠 FlashNote.md")
INBOX = os.path.join(VAULT, "My-Inbox.md")
PICGO_URL = "http://127.0.0.1:36677/upload"
VAULT_NAME = "LeoDiary"
LOG_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Obsidian-upload",
)
LOG_PATH = os.path.join(LOG_DIR, "upload_debug.log")

FONT_BODY = ("Microsoft YaHei", 11)

DEP_PACKAGES = {
    "PIL": "Pillow",
    "requests": "requests",
    "pyperclip": "pyperclip",
    "pystray": "pystray",
    "keyboard": "keyboard",
    "markdown": "markdown",
    "tkinterweb": "tkinterweb",
}


def importable(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def ensure_deps():
    missing = [n for n in DEP_PACKAGES if not importable(n)]
    if not missing:
        return
    names = ", ".join(DEP_PACKAGES[n] for n in missing)
    if getattr(sys, "frozen", False):
        messagebox.showwarning(
            "缺少依赖",
            "打包版缺少以下库，请重新打包时包含：\n" + names,
        )
        return
    if not messagebox.askyesno("缺少依赖", "缺少：%s\n是否自动安装？" % names):
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install"]
            + [DEP_PACKAGES[n] for n in missing],
            check=True,
        )
        messagebox.showinfo("安装完成", "依赖安装完成，请重启工具。")
    except Exception as e:
        messagebox.showerror(
            "安装失败",
            "自动安装失败：%s\n请手动执行：pip install %s" % (e, names),
        )


def timestamp_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_note(path, content):
    content = content.strip()
    if not content:
        return
    entry = "\n#### %s\n\n%s\n\n---\n" % (timestamp_str(), content)
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def log_debug(text):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s]\n%s\n\n" % (timestamp_str(), text))
    except Exception:
        pass
    if not getattr(sys, "frozen", False):
        print(text)


def generate_markdown(url):
    return "![](%s)" % url


def open_obsidian_file(filename):
    encoded = urllib.parse.quote(filename)
    uri = "obsidian://open?vault=%s&file=%s" % (VAULT_NAME, encoded)
    os.startfile(uri)
    return uri


def clipboard_image():
    try:
        from PIL import Image, ImageGrab
    except ImportError:
        return None, "未安装 Pillow，无法读取剪贴板图片（pip install Pillow）"
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            return img, None
        return None, None
    except Exception as e:
        return None, "读取剪贴板失败：%s" % e


def image_to_png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def picgo_filename():
    return datetime.now().strftime("Pasted-image-%Y%m%d-%H%M%S.png")


def upload_to_picgo(png_bytes, filename):
    debug = {
        "detected": False,
        "service_status": "未知",
        "status": None,
        "body": None,
        "hint": None,
    }
    try:
        import requests
    except ImportError:
        debug["service_status"] = "缺少依赖"
        debug["hint"] = "未安装 requests 库，请 pip install requests"
        return False, None, debug
    try:
        resp = requests.post(
            PICGO_URL,
            files={"files": (filename, png_bytes, "image/png")},
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        debug["service_status"] = "PicGo 连接失败"
        debug["hint"] = "请确认 %s 是否启动。" % PICGO_URL
        return False, None, debug
    except Exception as e:
        debug["service_status"] = "请求异常"
        debug["hint"] = str(e)
        return False, None, debug
    debug["status"] = resp.status_code
    debug["service_status"] = "已连接（HTTP %s）" % resp.status_code
    try:
        data = resp.json()
    except Exception:
        data = None
    debug["body"] = data if data is not None else resp.text
    if resp.status_code != 200:
        debug["hint"] = "PicGo 返回非 200 状态码"
        return False, None, debug
    if data is None or not data.get("success"):
        debug["hint"] = "PicGo 返回 success=false，上传未成功"
        return False, None, debug
    result = data.get("result") or []
    if not result:
        debug["hint"] = "PicGo 未返回图片 URL（result 为空）"
        return False, None, debug
    url = str(result[0]).strip()
    if not url.startswith("http"):
        debug["hint"] = "PicGo 返回的 URL 不合法：%r" % url
        return False, None, debug
    return True, url, debug


class ObsidianUploadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Obsidian-upload")
        self.geometry("960x640")
        self.minsize(720, 480)

        self.target = tk.StringVar(value="flash")
        self.status = tk.StringVar(value="就绪 · PicGo 图床（%s）" % PICGO_URL)
        self.tray = None
        self._last_upload_filename = None
        self._preview_cache = {}
        self._cache_dir = None
        self._hotkeys = []
        self._cmd_queue = queue.Queue()

        self._build_toolbar()
        self._build_editor()
        self._build_bottom_bar()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.bind_all("<Control-Return>", lambda e: self.save_note())
        self._setup_hotkeys()
        self._start_tray()
        self.after(200, self._poll_cmd_queue)

    def _build_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=6, pady=6)

        ttk.Radiobutton(toolbar, text=" FlashNote", variable=self.target,
                        value="flash").pack(side="left")
        ttk.Radiobutton(toolbar, text=" Inbox", variable=self.target,
                        value="inbox").pack(side="left", padx=(10, 0))
        ttk.Label(toolbar, text="Alt+S 呼出 Inbox · Alt+E 呼出 FlashNote",
                  foreground="#666666").pack(side="right")

    def _build_bottom_bar(self):
        style = ttk.Style(self)
        style.configure("Big.TButton", font=("Microsoft YaHei", 13, "bold"),
                        padding=(24, 12))
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_save = ttk.Button(bar, text="保存 (Ctrl+Enter)", style="Big.TButton",
                                   command=self.save_note)
        self.btn_save.pack(side="left", expand=True, fill="x")
        self.btn_clear = ttk.Button(bar, text="清空", style="Big.TButton",
                                    command=self.clear_editor)
        self.btn_clear.pack(side="left", expand=True, fill="x", padx=(10, 0))

    def _build_editor(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        left = ttk.Frame(paned)
        ttk.Label(left, text="Markdown 编辑（Ctrl+V 粘贴图片 → PicGo 图床）").pack(anchor="w")
        self.editor = tk.Text(left, wrap="word", undo=True, font=FONT_BODY)
        self.editor.pack(fill="both", expand=True)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        ttk.Label(right, text="预览").pack(anchor="w")
        from tkinterweb import HtmlFrame
        self.preview = HtmlFrame(right, messages_enabled=False)
        self.preview.pack(fill="both", expand=True)
        paned.add(right, weight=1)

        self.editor.bind("<<Paste>>", self.on_paste)
        self.editor.bind("<KeyRelease>", lambda e: self.update_preview())

    def _build_statusbar(self):
        ttk.Label(self, textvariable=self.status, anchor="w",
                  relief="sunken").pack(fill="x", side="bottom")

    def set_status(self, msg):
        self.status.set(msg)
        self.update_idletasks()

    def open_inbox(self, event=None):
        open_obsidian_file(os.path.basename(INBOX))
        self.set_status("已打开 My-Inbox.md")
        return "break"

    def open_flashnote(self, event=None):
        open_obsidian_file(os.path.basename(FLASHNOTE))
        self.set_status("已打开 🧠 FlashNote.md")
        return "break"

    def summon_inbox(self, event=None):
        self.summon_window()
        return self.open_inbox(event)

    def summon_flashnote(self, event=None):
        self.summon_window()
        return self.open_flashnote(event)

    def summon_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _setup_hotkeys(self):
        self._hotkeys = []
        try:
            import keyboard
        except ImportError:
            self._use_inapp_hotkeys()
            return
        try:
            self._hotkeys.append(keyboard.add_hotkey(
                "alt+s", self._enqueue_summon_inbox, suppress=False))
            self._hotkeys.append(keyboard.add_hotkey(
                "alt+e", self._enqueue_summon_flashnote, suppress=False))
        except Exception:
            self._use_inapp_hotkeys()

    def _enqueue_summon_inbox(self):
        self._cmd_queue.put(("summon_inbox",))

    def _enqueue_summon_flashnote(self):
        self._cmd_queue.put(("summon_flashnote",))

    def _poll_cmd_queue(self):
        try:
            while True:
                cmd = self._cmd_queue.get_nowait()
                if cmd[0] == "summon_inbox":
                    self.summon_inbox()
                elif cmd[0] == "summon_flashnote":
                    self.summon_flashnote()
        except queue.Empty:
            pass
        self.after(200, self._poll_cmd_queue)

    def _use_inapp_hotkeys(self):
        self.bind_all("<Alt-s>", self.summon_inbox)
        self.bind_all("<Alt-e>", self.summon_flashnote)

    def _teardown_hotkeys(self):
        try:
            import keyboard
        except ImportError:
            return
        for handle in self._hotkeys:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkeys = []

    def minimize_to_tray(self):
        if getattr(self, "tray", None) is not None:
            self.withdraw()
            self.set_status("已最小化到托盘，程序继续运行")
        else:
            self.iconify()
            self.set_status("已最小化，程序继续运行")

    def restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.set_status("已恢复窗口")

    def exit_app(self):
        self._teardown_hotkeys()
        self._stop_tray()
        self._clean_preview_cache()
        self.destroy()
        sys.exit(0)

    def _make_tray_icon(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(52, 120, 246, 255))
        d.polygon(
            [(32, 14), (20, 30), (27, 30), (27, 46), (37, 46), (37, 30), (44, 30)],
            fill="white",
        )
        return img

    def _start_tray(self):
        try:
            import pystray
        except ImportError:
            self.tray = None
            return
        menu = pystray.Menu(
            pystray.MenuItem("打开窗口", self._on_tray_open, default=True),
            pystray.MenuItem("退出程序", self._on_tray_exit),
        )
        self.tray = pystray.Icon(
            "obsidian-upload",
            self._make_tray_icon(),
            "Obsidian-upload（运行中）",
            menu,
        )
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _on_tray_open(self, icon, item):
        self.after(0, self.restore_window)

    def _on_tray_exit(self, icon, item):
        self.after(0, self.exit_app)

    def _stop_tray(self):
        tray = getattr(self, "tray", None)
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
            self.tray = None

    def on_paste(self, event):
        img, err = clipboard_image()
        if img is not None:
            self.paste_image()
            return "break"
        if err:
            messagebox.showerror("粘贴图片", err)
            return "break"
        return None

    def paste_image(self):
        img, err = clipboard_image()
        if img is None:
            messagebox.showerror("图片上传", err or "剪贴板没有检测到图片")
            return
        try:
            png_bytes = image_to_png_bytes(img)
        except Exception as e:
            messagebox.showerror("图片编码失败", str(e))
            return
        filename = picgo_filename()
        self._last_upload_filename = filename
        ok, url, debug = upload_to_picgo(png_bytes, filename)
        debug["detected"] = True
        if not ok:
            self.show_upload_failure(debug)
            return
        self.on_upload_success(url)

    def on_upload_success(self, url):
        link = generate_markdown(url)
        original = self._last_upload_filename or "unknown.png"
        self.editor.insert("insert", link + "\n")
        copied, msg = self.copy_to_clipboard(link)
        self.update_preview()
        self.set_status("上传成功：%s · %s" % (url, msg))
        block = (
            "==================\n"
            "Upload Success\n"
            "==================\n"
            "Original File:\n%s\n\n"
            "Remote URL:\n%s\n\n"
            "Markdown:\n%s\n"
            "=================="
        ) % (original, url, link)
        log_debug(block)

    def copy_to_clipboard(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return True, "已复制到剪贴板"
        except Exception:
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
                return True, "已复制到剪贴板（pyperclip 不可用，使用系统剪贴板）"
            except Exception as e:
                return False, "复制失败：%s" % e

    def show_upload_failure(self, debug):
        body = debug.get("body")
        if isinstance(body, dict):
            body = str(body)
        lines = [
            "上传失败，调试信息：",
            "",
            "1. 剪贴板图片：%s" % ("已检测到" if debug.get("detected") else "未检测到"),
            "2. PicGo 服务状态：%s" % debug.get("service_status", "未知"),
            "3. HTTP 返回状态：%s" % (debug.get("status") if debug.get("status") is not None else "无"),
            "4. 返回内容：%s" % (body if body is not None else "无"),
        ]
        if debug.get("hint"):
            lines.append("")
            lines.append("提示：%s" % debug["hint"])
        log_debug("==================\nUpload Failed\n==================\n%s" % "\n".join(lines))
        messagebox.showerror("图片上传失败", "\n".join(lines))

    def save_note(self):
        content = self.editor.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("保存笔记", "没有内容可保存")
            return
        path = FLASHNOTE if self.target.get() == "flash" else INBOX
        try:
            append_note(path, content)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        self.clear_editor()
        self.set_status("已保存到 %s，已隐藏到托盘" % os.path.basename(path))
        self.minimize_to_tray()

    def clear_editor(self):
        self.editor.delete("1.0", "end")
        self.update_preview()

    def update_preview(self):
        src = self.editor.get("1.0", "end-1c")
        if not src.strip():
            self.preview.load_html("<html><body></body></html>")
            return
        try:
            import markdown
            html = markdown.markdown(
                src,
                extensions=["extra", "codehilite", "sane_lists", "tables"],
            )
        except Exception:
            html = "<pre>" + src + "</pre>"
        body = self._rewrite_image_src(html)
        full = (
            "<html><head><meta charset='utf-8'>"
            "<style>body{font-family:'Microsoft YaHei';font-size:13px;"
            "line-height:1.6;padding:6px}img{max-width:100%}</style>"
            "</head><body>" + body + "</body></html>"
        )
        self.preview.load_html(full)

    def _rewrite_image_src(self, html):
        def _one(m):
            url = m.group(1).strip()
            cached = self._cache_remote_image(url)
            return 'src="%s"' % cached
        return re.sub(r'src="(https?://[^"]+)"', _one, html)

    def _preview_cache_dir(self):
        if not getattr(self, "_cache_dir", None):
            self._cache_dir = tempfile.mkdtemp(prefix="obs-upload-preview-")
        return self._cache_dir

    def _cache_remote_image(self, url):
        if not url.startswith("http"):
            return url
        if url in self._preview_cache:
            return self._preview_cache[url]
        try:
            import requests
            key = hashlib.md5(url.encode("utf-8")).hexdigest()
            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
            if ext.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                ext = ".png"
            path = os.path.join(self._preview_cache_dir(), key + ext)
            if not os.path.exists(path):
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(resp.content)
            self._preview_cache[url] = path
            return path
        except Exception:
            return url

    def _clean_preview_cache(self):
        if hasattr(self, "_cache_dir"):
            try:
                import shutil
                shutil.rmtree(self._cache_dir, ignore_errors=True)
            except Exception:
                pass
            self._cache_dir = None
        self._preview_cache = {}


def _show_fatal(e):
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Obsidian-upload 启动失败",
                             str(e) or repr(e))
    except Exception:
        pass


def main():
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        root = None
    ensure_deps()
    if root is not None:
        root.destroy()
    try:
        app = ObsidianUploadApp()
    except Exception as e:
        _show_fatal(e)
        sys.exit(1)
    try:
        app.mainloop()
    except Exception as e:
        _show_fatal(e)
        sys.exit(1)


if __name__ == "__main__":
    main()

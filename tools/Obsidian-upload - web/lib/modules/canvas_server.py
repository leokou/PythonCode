# -*- coding: utf-8 -*-
"""Drawnix 画布本地 HTTP 服务器。

Drawnix（tools/drawnix）是 Vite + React 构建的 ES Module 单页应用，
直接用 file:// 加载会被浏览器 CORS 拦截导致白屏，必须通过 HTTP 提供服务。
本模块用标准库 ThreadingHTTPServer 在 127.0.0.1 随机端口提供静态目录，
随程序启动、随程序退出关闭；无第三方依赖、不依赖 UI 与网络，可独立测试。
"""

import functools
import http.server
import json
import os
import socketserver
import threading

from commands.logger import log_info, log_error

# Vite 产物扩展名 → MIME（确保 ES Module / CSS / 图标类型正确，避免浏览器拒绝）
_EXTRA_MIME = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

_IMPORT_PATH = "/api/import"


class _Handler(http.server.SimpleHTTPRequestHandler):
    """静默日志 + 精确 MIME 的静态文件处理器，附带画布导入接口。

    画布导入由 tools/drawnix/canvas-bridge.js 轮询消费：
    - GET /api/import  → 返回待导入的画布数据（一次性，取走后清空）；
    - POST /api/import → 提交待导入内容（来自编辑器窗口）。
      body 支持两种：
        {"markdown": "..."}           → 交给 Drawnix 官方 parseMarkdownToDrawnix 生成思维导图；
        {"data": <board-data>}        → 直接覆盖画布内容。
    数据经 CanvasServer.submit_import / take_import 中转，线程安全。
    """

    def log_message(self, fmt, *args):
        pass

    def guess_type(self, path):
        base, ext = os.path.splitext(path)
        if ext.lower() in _EXTRA_MIME:
            return _EXTRA_MIME[ext.lower()]
        return super().guess_type(path)

    # ---- 画布导入接口 ----
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _canvas_server(self):
        # ThreadingTCPServer 会把自身挂到 handler.server，start() 时绑定 canvas 引用
        return getattr(self.server, "canvas", None)

    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == _IMPORT_PATH:
            canvas = self._canvas_server()
            if canvas is None:
                self._send_json({"error": "server not ready"}, 500)
                return
            self._send_json({"data": canvas.take_import()})
            return
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") == _IMPORT_PATH:
            canvas = self._canvas_server()
            if canvas is None:
                self._send_json({"error": "server not ready"}, 500)
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if "markdown" in payload:
                    canvas.submit_import({"markdown": payload["markdown"]})
                else:
                    canvas.submit_import(payload.get("data"))
                self._send_json({"ok": True})
            except Exception as e:
                log_error("画布导入 POST 失败: %s" % e)
                self._send_json({"error": str(e)}, 500)
            return
        self.send_error(404, "Not Found")


class CanvasServer:
    """为 Drawnix 构建产物提供本地 HTTP 服务。

    start() 返回可访问的 URL（http://127.0.0.1:<随机端口>/），
    stop() 关闭服务器；重复调用 start 前必须先 stop。
    """

    def __init__(self, root_dir):
        self.root_dir = os.path.abspath(root_dir)
        self._httpd = None
        self._thread = None
        self._import_lock = threading.Lock()
        self._pending_import = None

    @property
    def url(self):
        if self._httpd is None:
            return None
        return "http://127.0.0.1:%d/" % self._httpd.server_address[1]

    # ---- 画布导入：提交 / 消费（线程安全，一次性） ----
    def submit_import(self, data):
        with self._import_lock:
            self._pending_import = data
        log_info("画布导入数据已提交")

    def take_import(self):
        with self._import_lock:
            data, self._pending_import = self._pending_import, None
        return data

    def start(self):
        if self._httpd is not None:
            return self.url
        if not os.path.isdir(self.root_dir):
            raise OSError("画布构建产物目录不存在: %s" % self.root_dir)
        handler = functools.partial(_Handler, directory=self.root_dir)
        self._httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        self._httpd.canvas = self
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name="canvas-http-server",
        )
        self._thread.start()
        log_info("画布 HTTP 服务已启动: %s (%s)" % (self.url, self.root_dir))
        return self.url

    def stop(self):
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            try:
                httpd.shutdown()
                httpd.server_close()
                log_info("画布 HTTP 服务已关闭")
            except Exception as e:
                log_error("关闭画布 HTTP 服务失败: %s" % e)

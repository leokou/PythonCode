# -*- coding: utf-8 -*-
"""To Do 窗口管理（复用 tools/to-do 独立模块）。

把 tools/to-do 任务系统接入主程序工具箱，完全复用其自身后端：
- core.manager / core.sync_engine / storage.database / core.api（TodoApi 作为 js_api）
- 窗口模式与画布一致：main.py 启动时预创建 hidden 窗口，open 时 show 复用，退出时销毁。
- Microsoft 适配器按 to-do 自身 config.json 初始化；失败降级为纯本地模式，不影响窗口。

不依赖 to-do 之外的业务逻辑；本模块只做窗口编排。
"""
from __future__ import annotations

import logging
import os
import sys

from commands.logger import log_info, log_warn, log_error

log = logging.getLogger(__name__)

_window = None   # pywebview 窗口引用
_api = None      # TodoApi 实例（js_api）
_db = None       # to-do 的 Database 实例（退出时关闭落盘）


def _todo_root():
    from lib.core import main as _main
    return os.path.abspath(_main.resource_path(os.path.join("tools", "to-do")))


class _TodoLogFilter(logging.Filter):
    """只放行 to-do 相关模块的日志。"""

    def filter(self, record):
        name = record.name
        return name.startswith(("core.", "adapters.", "storage."))


def _setup_todo_logging(log_file):
    """宿主环境绕过 to-do 的 main.py，这里补上文件日志（记录同步/错误）。

    只记录 to-do 相关 logger（core.* / adapters.* / storage.*），
    不干扰宿主自身的 commands.logger。
    """
    try:
        if not log_file:
            return
        log_file = os.path.abspath(log_file)
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        for h in list(logging.getLogger().handlers):
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == log_file:
                return
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        fh.addFilter(_TodoLogFilter())
        # Python root logger 默认 WARNING，会丢弃同步 INFO 日志
        logging.getLogger("core").setLevel(logging.INFO)
        logging.getLogger("adapters").setLevel(logging.INFO)
        logging.getLogger("storage").setLevel(logging.INFO)
        logging.getLogger().addHandler(fh)
    except Exception as exc:
        log_warn("To Do 日志配置失败: %s" % exc)


def _build_api():
    """构建 to-do 后端组件，返回 TodoApi 实例（单例复用）。"""
    global _api, _db
    if _api is not None:
        return _api
    root = _todo_root()
    if root not in sys.path:
        sys.path.insert(0, root)

    from core.config import load_config
    from core.manager import TaskManager
    from core.sync_engine import SyncEngine
    from core.api import TodoApi
    from storage.database import Database
    from storage.attachment import AttachmentStore

    config = load_config()
    _redirect_exe_data_paths(config)
    _setup_todo_logging(config.get("log_file"))
    # 合并用户覆盖（设置窗口保存的自定义 Microsoft client_id）
    try:
        from lib.core import settings as settings_store
        ms_override = settings_store.get_microsoft_config()
        if ms_override.get("client_id"):
            config.setdefault("microsoft", {})["client_id"] = ms_override["client_id"]
        if ms_override.get("tenant"):
            config.setdefault("microsoft", {})["tenant"] = ms_override["tenant"]
    except Exception as exc:
        log_warn("To Do 用户配置合并失败: %s" % exc)
    _db = Database(config["db_file"])
    store = AttachmentStore(config["attachments_dir"], config.get("image_exts"))
    manager = TaskManager(_db, store)
    engine = SyncEngine(manager)

    auth = None
    ms_cfg = config.get("microsoft") or {}
    if ms_cfg.get("enabled"):
        try:
            from adapters.microsoft.auth import MicrosoftAuth
            from adapters.microsoft.client import GraphClient
            from adapters.microsoft.sync import MicrosoftAdapter
            auth = MicrosoftAuth(
                client_id=ms_cfg.get("client_id", ""),
                tenant=ms_cfg.get("tenant", "consumers"),
                scopes=ms_cfg.get("scopes"),
                cache_path=ms_cfg.get("token_cache_file"),
                timeout=ms_cfg.get("timeout", 30),
            )
            adapter = MicrosoftAdapter(
                auth=auth,
                client=GraphClient(auth, ms_cfg.get("timeout", 30)),
                max_attachment_mb=ms_cfg.get("max_attachment_mb", 10),
            )
            engine.register_adapter(adapter)
        except Exception as exc:
            log_warn("To Do Microsoft 适配器初始化失败（降级本地模式）: %s", exc)
    _api = TodoApi(manager, engine, auth, config)
    if auth is not None:
        try:
            log_info("To Do 微软适配器就绪: client_id=%s logged_in=%s"
                     % (ms_cfg.get("client_id"), auth.is_logged_in()))
        except Exception as exc:
            log_warn("To Do 登录状态检查异常: %s" % exc)
    log_info("To Do 后端初始化完成（来源: tools/to-do）")
    return _api


def _redirect_exe_data_paths(config):
    """打包（frozen）环境：把 to-do 数据路径重定向到用户可写目录。

    _MEIPASS 是程序临时解包目录，退出即删——数据库/附件/令牌放那里会丢失。
    源码运行不受影响（保留 to-do 模块内 data/ 目录）。
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        user_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "Obsidian-upload", "todo",
        )
        os.makedirs(user_dir, exist_ok=True)
        # 顶层数据路径
        for key, name in (
            ("db_file", "todo.db"),
            ("attachments_dir", "attachments"),
            ("log_file", "todo.log"),
        ):
            if key in config:
                config[key] = os.path.join(user_dir, name)
        # microsoft.token_cache_file 是嵌套 key（config.json 里在 microsoft 对象下）
        ms_cfg = config.get("microsoft") or {}
        if ms_cfg.get("token_cache_file"):
            ms_cfg["token_cache_file"] = os.path.join(user_dir, "token_cache.json")
            config["microsoft"] = ms_cfg
        log_info("To Do 数据目录重定向到: %s" % user_dir)
    except Exception as exc:
        log_warn("To Do 数据目录重定向失败（沿用模块内路径）: %s" % exc)


def create():
    """main.py 启动时调用：预创建 hidden 窗口（失败不阻塞主流程）。"""
    global _window
    if _window is not None:
        return _window
    try:
        import webview
        from commands.app_utils import get_center_position
        from lib.core import main as _main

        api = _build_api()
        root = _todo_root()
        html_path = os.path.join(root, "ui", "todo.html")
        if not os.path.isfile(html_path):
            raise FileNotFoundError("找不到 To Do UI: %s" % html_path)

        wx, wy = get_center_position(1200, 800)
        w = webview.create_window(
            "✅ Leo Todo",
            url=html_path,
            js_api=api,
            width=1200,
            height=800,
            x=wx,
            y=wy,
            min_size=(900, 600),
            hidden=True,
        )

        # 窗口加载完成后强制启动前端 boot()（确保 JS API 已就绪）
        def on_loaded():
            import time
            time.sleep(0.3)
            try:
                w.evaluate_js('if(typeof boot==="function") boot();')
            except Exception as exc:
                log_warn("启动 To Do 前端失败: %s" % exc)

        w.events.loaded += on_loaded

        def on_closing(*_args):
            if _main._state.get("quitting"):
                return True
            try:
                w.hide()
                log_info("To Do 窗口已隐藏（X 按钮）")
            except Exception as exc:
                log_error("隐藏 To Do 窗口异常: %s" % exc)
            return False

        w.events.closing += on_closing
        _window = w
        log_info("To Do 窗口创建成功")
    except Exception as exc:
        log_error("创建 To Do 窗口失败: %s" % exc)
        _window = None
    return _window


def show():
    """显示 To Do 窗口（ToolApi/编辑窗口调用），返回是否成功。"""
    try:
        from lib.core import main as _main
        if _window is None:
            create()
        if _window is None:
            log_error("To Do 窗口不可用")
            return False
        _main._safe_show_window(_window)
        log_info("打开 To Do 窗口")
        return True
    except Exception as exc:
        log_error("打开 To Do 窗口失败: %s" % exc)
        return False


def close():
    """main.py 退出时调用：销毁窗口 + 关闭数据库 + 保存令牌缓存。"""
    global _window, _api, _db
    # 强制保存 Microsoft 令牌缓存到磁盘，保证下次启动免登录
    if _api is not None and _api._auth is not None:
        try:
            _api._auth.save_cache()
            log_info("To Do 令牌缓存已保存")
        except Exception as exc:
            log_warn("保存 To Do 令牌缓存异常: %s" % exc)
    if _window is not None:
        try:
            _window.destroy()
        except Exception as exc:
            log_error("销毁 To Do 窗口异常: %s" % exc)
        _window = None
    if _db is not None:
        try:
            _db.close()
        except Exception as exc:
            log_error("关闭 To Do 数据库异常: %s" % exc)
        _db = None
    _api = None

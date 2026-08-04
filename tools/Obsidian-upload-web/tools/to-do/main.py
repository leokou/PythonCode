"""Leo Todo 入口：pywebview 桌面应用 + 轻量 CLI（自测用）。

用法：
    1. 桌面应用：python main.py
    2. CLI 自测：python main.py --cli sync
                python main.py --cli list
                python main.py --cli stats
                python main.py --cli create --title "..." [--project xxx] [--priority high]

只做编排：加载配置 -> 初始化各层 -> 创建窗口 / 执行 CLI。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# 让本模块以包方式 import（tools/to-do/ 是包根）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config, MODULE_ROOT  # noqa: E402
from core.manager import TaskManager  # noqa: E402
from core.sync_engine import SyncEngine  # noqa: E402
from core.api import TodoApi  # noqa: E402
from storage.database import Database  # noqa: E402
from storage.attachment import AttachmentStore  # noqa: E402

log = logging.getLogger(__name__)


def setup_logging(log_file: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def build_app(config: dict):
    """装配各层组件，返回 (manager, engine, api)。"""
    db = Database(config["db_file"])
    store = AttachmentStore(config["attachments_dir"], config.get("image_exts"))
    manager = TaskManager(db, store)

    engine = SyncEngine(manager)

    ms_cfg = config.get("microsoft") or {}
    auth = None
    if ms_cfg.get("enabled"):
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

    api = TodoApi(manager, engine, auth, config)
    return manager, engine, api


# ---------------------------------------------------------------------------
# CLI 自测
# ---------------------------------------------------------------------------

def run_cli(args) -> int:
    config = load_config()
    setup_logging(config["log_file"])
    manager, engine, api = build_app(config)

    if args.command == "sync":
        try:
            reports = engine.sync()
        except Exception as exc:
            print(f"同步失败：{exc}")
            return 1
        print(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2))
        return 0
    if args.command == "list":
        tasks = manager.list_tasks(include_deleted=True)
        print(json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2))
        return 0
    if args.command == "stats":
        print(json.dumps(manager.stats().to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "create":
        from core.models import Task

        task = Task(
            title=args.title,
            description=args.description or "",
            priority=args.priority or "medium",
            project=args.project or config.get("default_project", ""),
        )
        task = manager.create_task(task)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "login":
        auth = _build_auth(config)
        if auth is None:
            print("Microsoft 未启用（config.json 的 microsoft.enabled=false）")
            return 1
        try:
            import sys
            print("正在初始化 MSAL 应用...", flush=True)
            app = auth._get_app()
            print(f"MSAL 应用就绪, client_id={auth._client_id[:8]}...", flush=True)
            print("正在获取设备码...", flush=True)
            flow = app.initiate_device_flow(scopes=auth._scopes)
            if "error" in flow:
                print(f"设备码初始化失败: {flow.get('error_description')}", flush=True)
                return 1
            uri = flow.get("verification_uri", "")
            code = flow.get("user_code", "")
            print(f"\n请在浏览器中打开: {uri}", flush=True)
            print(f"输入验证码: {code}", flush=True)
            print(f"(或直接访问: {flow.get('user_message', '')})", flush=True)
            # 保存 flow 引用
            auth._device_flow = flow
            print("\n等待授权中...", flush=True)
            result = auth.wait_device_flow()
            print("登录成功", flush=True)
        except Exception as exc:
            print(f"登录失败：{exc}", flush=True)
            import traceback
            traceback.print_exc()
            return 1
        return 0
    if args.command == "logout":
        auth = _build_auth(config)
        if auth is not None:
            auth.logout()
        print("已退出登录")
        return 0
    if args.command == "ms-status":
        auth = _build_auth(config)
        if auth is None:
            print("Microsoft 未启用")
            return 0
        print("已登录" if auth.is_logged_in() else "未登录")
        return 0
    print(f"未知命令：{args.command}")
    return 1


def _build_auth(config: dict):
    ms_cfg = config.get("microsoft") or {}
    if not ms_cfg.get("enabled"):
        return None
    from adapters.microsoft.auth import MicrosoftAuth

    return MicrosoftAuth(
        client_id=ms_cfg.get("client_id", ""),
        tenant=ms_cfg.get("tenant", "consumers"),
        scopes=ms_cfg.get("scopes"),
        cache_path=ms_cfg.get("token_cache_file"),
        timeout=ms_cfg.get("timeout", 30),
    )


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leo-todo", description="Leo Todo Engine")
    parser.add_argument(
        "--cli", dest="command",
        help="CLI 模式：sync / list / stats / create / login / logout / ms-status",
    )
    parser.add_argument("--title", help="create 命令的标题")
    parser.add_argument("--description", help="create 命令的描述")
    parser.add_argument("--project", help="create 命令的项目")
    parser.add_argument("--priority", choices=["low", "medium", "high"], help="create 命令的优先级")
    return parser


# ---------------------------------------------------------------------------
# 桌面应用
# ---------------------------------------------------------------------------

def run_gui(config: dict, api: TodoApi) -> None:
    import webview

    html_path = os.path.abspath(os.path.join(MODULE_ROOT, "ui", "todo.html"))
    if not os.path.isfile(html_path):
        raise FileNotFoundError(f"UI 文件不存在：{html_path}")

    window = webview.create_window(
        config.get("app_name", "Leo Todo"),
        url=html_path,
        js_api=api,
        width=1200,
        height=800,
        min_size=(900, 600),
    )

    # 窗口加载完成后强制启动前端（确保 API 已就绪）
    def on_loaded():
        log.info("GUI 窗口已加载")
        import time
        time.sleep(0.3)  # 等待 JS 初始化
        try:
            window.evaluate_js('if(typeof boot==="function") boot();')
        except Exception as exc:
            log.warning(f"启动前端失败: {exc}")

    window.events.loaded += on_loaded

    webview.start(debug=False)


def main() -> None:
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.command:
        sys.exit(run_cli(args))

    config = load_config()
    setup_logging(config["log_file"])
    manager, engine, api = build_app(config)

    log.info("Leo Todo 启动：%s", config["app_name"])
    try:
        run_gui(config, api)
    finally:
        # 强制保存 Microsoft 令牌缓存，保证下次启动免登录
        if api._auth is not None:
            try:
                api._auth.save_cache()
                log.info("令牌缓存已保存")
            except Exception as exc:
                log.warning("保存令牌缓存失败: %s", exc)
        manager._db.close()
        log.info("Leo Todo 退出")


if __name__ == "__main__":
    main()

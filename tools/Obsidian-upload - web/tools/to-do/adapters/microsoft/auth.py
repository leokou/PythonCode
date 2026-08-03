"""Microsoft OAuth 认证（msal）。

- 交互式登录：acquire_token_interactive（Authorization Code + PKCE，系统浏览器）
- 兜底登录：设备码流（acquire_token_by_device_flow）
- 令牌缓存：msal SerializableTokenCache → data/token_cache.json
- 登录状态：独立 JSON 文件 → data/login_state.json（双保险，不依赖 MSAL 内部状态）
- 禁止保存用户密码；access token 过期后静默刷新（refresh token）
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable, Dict, Optional

import msal

log = logging.getLogger(__name__)

_AUTHORITY = "https://login.microsoftonline.com/{tenant}"
_LOGIN_STATE_FILENAME = "login_state.json"


class MicrosoftAuth:
    """封装 msal PublicClientApplication 的登录与令牌获取。"""

    def __init__(
        self,
        client_id: str,
        tenant: str = "consumers",
        scopes: Optional[list] = None,
        cache_path: Optional[str] = None,
        timeout: int = 30,
    ):
        self._client_id = client_id
        self._tenant = tenant or "consumers"
        self._scopes = [
            s for s in (scopes or ["Tasks.ReadWrite", "offline_access"])
            if s not in ("openid", "offline_access", "profile")
        ] or ["Tasks.ReadWrite"]
        self._cache_path = cache_path
        self._timeout = timeout
        self._lock = threading.RLock()
        self._app: Optional[msal.PublicClientApplication] = None
        # 派生登录状态文件路径（与 token_cache 同目录）
        self._state_path = self._derive_state_path(cache_path)

    @staticmethod
    def _derive_state_path(cache_path: Optional[str]) -> Optional[str]:
        if not cache_path:
            return None
        parent = os.path.dirname(os.path.abspath(cache_path))
        return os.path.join(parent, _LOGIN_STATE_FILENAME)

    # ------------------------------------------------------------------
    # 登录状态文件（双保险持久化）
    # ------------------------------------------------------------------

    def _read_login_state(self) -> Dict:
        """读取登录状态文件。"""
        if not self._state_path or not os.path.isfile(self._state_path):
            return {}
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError, json.JSONDecodeError):
            log.warning("登录状态文件读取异常，将重新验证")
            return {}

    def _write_login_state(self, logged_in: bool, account_id: str = "", username: str = "") -> None:
        """写入登录状态文件。"""
        if not self._state_path:
            return
        parent = os.path.dirname(os.path.abspath(self._state_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = {
            "logged_in": logged_in,
            "account_id": account_id,
            "username": username,
            "timestamp": time.time(),
            "version": 2,
        }
        try:
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            log.info("登录状态已写入: logged_in=%s → %s", logged_in, self._state_path)
        except OSError:
            log.warning("登录状态文件写入失败: %s", self._state_path)

    def _clear_login_state(self) -> None:
        """清除登录状态文件（退出登录时调用）。"""
        if self._state_path and os.path.isfile(self._state_path):
            try:
                os.remove(self._state_path)
                log.info("登录状态文件已清除")
            except OSError:
                pass

    # ------------------------------------------------------------------
    # msal 实例与缓存
    # ------------------------------------------------------------------

    def _authority(self) -> str:
        return _AUTHORITY.format(tenant=self._tenant)

    def _load_cache(self) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if self._cache_path and os.path.isfile(self._cache_path):
            try:
                with open(self._cache_path, "r", encoding="utf-8") as fh:
                    data = fh.read()
                if data.strip():
                    cache.deserialize(data)
                    log.info("令牌缓存已从磁盘加载: %s", self._cache_path)
                else:
                    log.warning("令牌缓存文件为空: %s", self._cache_path)
            except (OSError, ValueError):
                log.warning("令牌缓存读取失败，重新登录")
        return cache

    def _save_cache(self, cache: msal.SerializableTokenCache, force: bool = False) -> None:
        """保存令牌缓存到磁盘。"""
        if not self._cache_path:
            return
        should_save = force or cache.has_state_changed
        if not should_save:
            try:
                has_accounts = bool(cache and hasattr(cache, "_accounts") and cache._accounts)
            except Exception:
                has_accounts = False
            should_save = has_accounts
        if not should_save:
            return
        parent = os.path.dirname(os.path.abspath(self._cache_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            with open(self._cache_path, "w", encoding="utf-8") as fh:
                fh.write(cache.serialize())
            log.info("令牌缓存已写入: %s", self._cache_path)
        except OSError:
            log.warning("令牌缓存写入失败：%s", self._cache_path)

    def save_cache(self) -> None:
        """公开接口：强制保存当前 MSAL 令牌缓存 + 登录状态到磁盘。"""
        with self._lock:
            if self._cache is not None:
                self._save_cache(self._cache, force=True)
            # 如果当前有账号，同时写入登录状态文件
            try:
                app = self._app
                if app is not None and app.get_accounts():
                    self._write_login_state(True)
            except Exception:
                pass

    def _get_app(self, create: bool = True) -> Optional[msal.PublicClientApplication]:
        with self._lock:
            if self._app is not None:
                return self._app
            if not create:
                return None
            if not self._client_id:
                raise MicrosoftAuthError(
                    "未配置 Microsoft client_id。注册步骤：Azure 门户 "
                    "(portal.azure.com) → 应用注册 → 新注册 → 平台选「移动与桌面应用程序」，"
                    "重定向 URI 填 http://localhost → 添加委派权限 Tasks.ReadWrite 和 "
                    "offline_access → 复制应用（客户端）ID，填入 config.json 的 "
                    "microsoft.client_id。"
                )
            cache = self._load_cache()
            self._app = msal.PublicClientApplication(
                self._client_id,
                authority=self._authority(),
                token_cache=cache,
                timeout=self._timeout,
            )
            self._cache = cache
            return self._app

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    def is_logged_in(self) -> bool:
        """检查登录状态（以状态文件为主，MSAL 验证为辅）。"""
        log.info("is_logged_in: 开始检查")
        # 第一层：检查独立状态文件
        state = self._read_login_state()
        state_logged_in = state.get("logged_in", False)
        log.info("is_logged_in: 状态文件显示 logged_in=%s", state_logged_in)

        if not state_logged_in:
            log.info("is_logged_in: 状态文件说未登录，直接返回 False")
            return False

        # 状态文件说已登录，用 MSAL 验证令牌
        try:
            app = self._get_app(create=True)
            if app is None:
                log.warning("is_logged_in: app 为空")
                return True  # 信任状态文件
            accounts = app.get_accounts()
            log.info("is_logged_in: MSAL accounts=%d", len(accounts))
            if accounts:
                token = app.acquire_token_silent(self._scopes, account=accounts[0])
                if token and "access_token" in token:
                    self._save_cache(self._cache, force=True)
                    log.info("is_logged_in: 令牌验证成功 → 已登录")
                    return True
                elif token and token.get("error") == "invalid_grant":
                    log.info("is_logged_in: refresh token 过期，清除状态")
                    self._clear_login_state()
                    return False
                else:
                    log.info("is_logged_in: 令牌刷新失败但保留登录状态")
                    return True
            else:
                # 尝试不带 account 的 silent
                try:
                    token = app.acquire_token_silent(self._scopes, account=None)
                    if token and "access_token" in token:
                        self._save_cache(self._cache, force=True)
                        log.info("is_logged_in: 无账号但 silent 成功 → 已登录")
                        return True
                except Exception:
                    pass
                # 仍然信任状态文件
                log.info("is_logged_in: MSAL 无账号，但信任状态文件 → 已登录")
                return True
        except MicrosoftAuthError:
            log.info("is_logged_in: client_id 未配置")
            return False
        except Exception as exc:
            log.warning("is_logged_in: 验证异常: %s", exc)
            # 验证异常但状态文件说已登录，保持信任
            log.info("is_logged_in: 验证异常，但信任状态文件 → 已登录")
            return True

    def initiate_device_flow(self) -> Dict:
        """设备码流第一步：返回含 user_code / verification_uri 的 flow。"""
        app = self._get_app()
        flow = app.initiate_device_flow(scopes=self._scopes)
        if "error" in flow:
            raise MicrosoftAuthError(f"设备码流初始化失败：{flow.get('error_description')}")
        self._device_flow = flow
        return flow

    def wait_device_flow(self) -> Dict:
        """设备码流第二步：阻塞轮询用户授权。"""
        app = self._get_app()
        flow = getattr(self, "_device_flow", None)
        if flow is None:
            raise MicrosoftAuthError("尚未初始化设备码流，请先调用 ms_device_start")
        try:
            result = app.acquire_token_by_device_flow(flow)
        except Exception:
            result = {}
        if "access_token" in result:
            self._save_cache(self._cache, force=True)
            self._write_login_state(True)
            log.info("Microsoft 设备码流登录成功")
            return result
        accounts = app.get_accounts()
        if accounts:
            silent = app.acquire_token_silent(self._scopes, account=accounts[0])
            if silent and "access_token" in silent:
                self._save_cache(self._cache, force=True)
                self._write_login_state(True)
                log.info("设备码已被使用，静默令牌续期成功")
                return silent
        raise MicrosoftAuthError(
            f"设备码流授权失败：{result.get('error_description') or result.get('error')}"
        )

    def login(
        self,
        mode: str = "interactive",
        device_message: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """登录并返回令牌。mode: interactive（默认）| device。"""
        app = self._get_app()
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(self._scopes, account=accounts[0])
            if result and "access_token" in result:
                self._save_cache(self._cache, force=True)
                self._write_login_state(True)
                return result

        if mode == "device":
            flow = app.initiate_device_flow(scopes=self._scopes)
            if "user_message" in flow and device_message:
                device_message(flow["user_message"])
            result = app.acquire_token_by_device_flow(flow)
        else:
            try:
                result = app.acquire_token_interactive(scopes=self._scopes)
            except Exception as exc:
                log.warning("交互式登录失败：%s，回退设备码流", exc)
                flow = app.initiate_device_flow(scopes=self._scopes)
                if "user_message" in flow and device_message:
                    device_message(flow["user_message"])
                result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self._save_cache(self._cache, force=True)
            self._write_login_state(True)
            log.info("Microsoft 登录成功")
            return result
        raise MicrosoftAuthError(
            f"Microsoft 登录失败：{result.get('error_description') or result.get('error')}"
        )

    # ------------------------------------------------------------------
    # 令牌
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        """返回有效的 access_token（静默刷新）。"""
        with self._lock:
            app = self._get_app()
            accounts = app.get_accounts()
            if not accounts:
                # 没有账号但状态文件说已登录，尝试直接 silent
                state = self._read_login_state()
                if state.get("logged_in"):
                    token = app.acquire_token_silent(self._scopes, account=None)
                    if token and "access_token" in token:
                        self._save_cache(self._cache, force=True)
                        return token["access_token"]
                raise MicrosoftAuthError("尚未登录 Microsoft，请先调用 login()")

            token = app.acquire_token_silent(self._scopes, account=accounts[0])
            if token and "access_token" in token:
                self._save_cache(self._cache, force=True)
                self._write_login_state(True)
                return token["access_token"]
            if token and "error" in token:
                if token.get("error") == "invalid_grant":
                    self._clear_login_state()
                raise MicrosoftAuthError(
                    f"获取令牌失败：{token.get('error_description') or token.get('error')}"
                )

            # 尝试交互续签
            result = self.login(mode="interactive")
            if "access_token" in result:
                return result["access_token"]
            raise MicrosoftAuthError("无法获取 Microsoft access token")

    def logout(self) -> None:
        with self._lock:
            app = self._get_app(create=False)
            if app is not None:
                for account in app.get_accounts():
                    app.remove_account(account)
            self._app = None
            if self._cache_path and os.path.isfile(self._cache_path):
                try:
                    os.remove(self._cache_path)
                except OSError:
                    pass
            self._clear_login_state()
            log.info("Microsoft 已退出登录")


class MicrosoftAuthError(Exception):
    """认证相关错误。"""

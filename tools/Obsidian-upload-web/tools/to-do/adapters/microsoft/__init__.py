"""Microsoft To Do 适配器（Microsoft Graph API）。

auth.py   OAuth 登录（msal，Authorization Code + PKCE / 设备码流）
client.py Graph API 请求封装
mapper.py Microsoft Task <-> Leo Task 转换
sync.py   实现 TodoAdapter 接口（同步双向数据转换）

权限要求（Azure 应用注册，委派权限）：
  - Tasks.Read
  - Tasks.ReadWrite
  - offline_access

禁止保存用户密码；只保存 OAuth 令牌缓存（data/token_cache.json）。
"""

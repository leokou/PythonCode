# Leo Todo Engine 开发规范

> Leo 自己的任务管理系统（SQLite 本地核心）。Microsoft To Do **只是外部任务同步来源**（经 Graph API），不是存储本体。宿主应用：LeoDiary Capture（`Obsidian-upload - web`），通过 `lib/modules/todo_window.py` 以独立窗口接入工具箱「✅ To Do」。

---

## 一、架构与原则

```
Microsoft To Do
     ↕
Microsoft Graph API（msal OAuth）
     ↕
core/sync_engine.py（TodoAdapter 接口，LWW 冲突处理）
     ↕
core/manager.py + core/models.py（Leo Task 模型）
     ↕
storage/database.py（SQLite：tasks / task_attachments / sync_meta）
     ↕
ui/todo.html + ui/todo.js（pywebview 承载）
```

核心原则：

- **外部数据一律经 Adapter（adapters/microsoft/mapper.py）转换为 Leo Task 模型**，不直接使用 Microsoft 数据结构；mapper.py 是外部结构转换的唯一出现处。
- **本模块独立于宿主程序**：不依赖 LeoDiary Capture 的 UI / 网络 / 全局状态，可单独运行与离线测试。
- 同步用 `source_id` 增量：不存在 → 新增，存在 → 更新；删除一律**软删除**（`status=deleted`）；冲突 `updated_at` Last-Write-Wins（UTC ISO 毫秒，字典序可比）。

## 二、目录结构

```
to-do/
├── main.py                 入口：pywebview 桌面应用 + CLI 自测（只做编排）
├── config.json             配置（microsoft.client_id / 数据路径 / 同步）
├── requirements.txt        依赖（pywebview / requests / msal）
├── adapters/microsoft/     Microsoft 适配层
│   ├── auth.py             msal OAuth（交互式 / 设备码流 / 令牌缓存，禁存密码）
│   ├── client.py           Graph API 请求封装
│   ├── mapper.py           Microsoft Task <-> Leo Task 双向转换
│   └── sync.py             实现 TodoAdapter 接口
├── core/
│   ├── models.py           Task / TaskAttachment 数据模型 + 时间工具
│   ├── manager.py          任务 CRUD / 查询 / 统计 / 软删除
│   ├── sync_engine.py      双向同步引擎（TodoAdapter + LWW）
│   ├── api.py              TodoApi 桥接层（宿主 js_api 与 UI 调用入口）
│   └── config.py           配置加载（相对路径解析）
├── storage/
│   ├── database.py         SQLite（tasks / task_attachments / sync_meta）
│   └── attachment.py       附件文件管理（下载缓存 / 图片预览 / 孤儿清理）
├── ui/                     todo.html / todo.css / todo.js
├── test/                   离线测试（42 项，无需网络）
└── data/                   运行时生成（todo.db / attachments/ / token_cache.json，gitignore）
```

## 三、Microsoft 同步配置（必经步骤）

**Microsoft 同步没有免注册方式**，必须用户注册 Azure 应用获取 `client_id`：

1. Azure 门户 → 应用注册 → 新注册
2. 平台配置：**移动与桌面应用程序**，重定向 URI：`http://localhost`
3. 添加委派权限：`Tasks.ReadWrite`、`offline_access`
4. 把「应用（客户端）ID」填入 `config.json` 的 `microsoft.client_id`

配置项（`config.json`）：

| 字段 | 说明 |
|------|------|
| `microsoft.client_id` | Azure 应用客户端 ID（**必须**，空则登录报 `未配置 Microsoft client_id`） |
| `microsoft.tenant` | 个人账号 `consumers`；企业/教育租户填对应 ID |
| `microsoft.scopes` | `Tasks.ReadWrite`、`offline_access` |
| `microsoft.token_cache_file` | 令牌缓存路径（相对 data_dir） |
| `sync.auto_sync_on_start` | 启动自动同步开关 |

**登录链路**：UI「Microsoft 登录」= 交互式 OAuth（系统浏览器）→ 失败自动回退设备码流（`ms_device_start` 返回 `user_code` + `verification_uri`，`ms_device_wait` 轮询授权）。令牌缓存不保存密码。

## 四、数据路径规则（打包陷阱）

- **源码运行**：`data_dir` 默认 `data/`（相对模块目录），写 `data/todo.db`、`data/attachments/`、`data/token_cache.json`。
- **打包（EXE）运行**：PyInstaller 解压到 `_MEIPASS` 临时目录，**退出即删，禁止存放数据**。宿主 `lib/modules/todo_window.py` 的 `_redirect_exe_data_paths(config)` 必须把 `db_file` / `attachments_dir` / `token_cache_file` 重定向到 `%APPDATA%\Obsidian-upload\todo\`。
- 新增任何数据文件路径，都必须同时处理源码与 EXE 两种形态。

## 五、宿主集成（todo_window.py）

- `lib/modules/todo_window.py`：`create()` 在宿主启动时 hidden 预创建窗口（`webview.start()` 之前）；`show()` 复用窗口；`close()` 销毁窗口并关闭数据库。
- 宿主 js_api 暴露 `Api.open_todo()` → 前端工具箱「✅ To Do」→ `__runTool("todo")`。
- `todo_window._build_api()` 用 `sys.path.insert` 把 `tools\to-do` 加入路径后 `from core.api import TodoApi`。
- **禁止**在宿主与模块间改动公共接口签名（js_api 方法名）。

## 六、已知陷阱

1. **个人账号列表限制**：`GET /me/todo/lists` 在个人账号下可能**静默只返回内置列表**（自建列表被丢弃）。实测确认，如需支持需额外记录列表注册表。
2. **client.py 容错**：`todo_lists` / `list_tasks` 拉取失败必须 `log_warning` 并跳过该列表，不能整次同步崩溃。
3. **token_cache 序列化**：msal `SerializableTokenCache` 只在 `has_state_changed` 时写盘，避免频繁 IO。
4. **SQLite 线程安全**：数据库连接需支持多线程（宿主在后台线程调用 API），读写用锁。

## 七、常用命令

```bash
# 离线测试（42 项，无需网络）
python -m unittest discover test -v

# CLI 自测（需先填 client_id）
python main.py --cli login          # 设备码流登录
python main.py --cli ms-status      # 登录状态
python main.py --cli sync           # 手动双向同步
python main.py --cli list           # 全部任务
python main.py --cli create --title "任务" --project "项目" --priority high
python main.py --cli logout         # 清除令牌
```

## 八、规则红线

- **不删除已有功能 / 不修改公共接口**（TodoApi 方法名、js_api 签名）。
- **不引入外部依赖**：requests / msal / pywebview 之外的新依赖须确认。
- **软删除优先**：绝不物理删除任务。
- **测试必须保持全绿**：任何修改后 `python -m unittest discover test -v` 42 项全过。

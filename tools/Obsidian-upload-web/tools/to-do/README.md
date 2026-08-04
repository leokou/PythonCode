# Leo Todo Engine

> Leo 自己的任务管理系统。Microsoft To Do **只是外部任务同步来源**，Leo Todo 才是核心系统。

## 架构

```
Microsoft To Do
     ↕
Microsoft Graph API
     ↕
Leo Todo Sync Engine（core/sync_engine.py）
     ↕
Leo Todo Core（core/models.py + core/manager.py）
     ↕
SQLite 本地任务数据库（storage/database.py）
     ↕
Leo Todo UI（ui/todo.html，pywebview 承载）
```

核心原则：

- 外部数据一律经 **Adapter** 转换为 Leo Task 模型，**不直接使用 Microsoft 数据结构**。
- Adapter 可插拔：未来接入 GitHub Issues / Obsidian Tasks / Jira / LEO Native Task，只需实现 `core/sync_engine.py` 中的 `TodoAdapter` 接口。
- Microsoft 通过 `adapters/microsoft/`（auth + client + mapper + sync）接入。

## 目录结构

```
to-do/
├── main.py                 入口：pywebview 桌面应用 + CLI 自测（只做编排）
├── config.json             配置（Azure / 数据库 / 附件 / 同步）
├── requirements.txt        依赖（pywebview / requests / msal）
├── adapters/microsoft/     Microsoft 适配层
│   ├── auth.py             OAuth 登录（msal，交互式 / 设备码流，令牌缓存）
│   ├── client.py           Graph API 请求封装（To Do 任务 / 附件端点）
│   ├── mapper.py           Microsoft Task <-> Leo Task 转换（外部结构的唯一出现处）
│   └── sync.py             实现 TodoAdapter 接口（双向数据转换）
├── core/                   Leo 核心
│   ├── models.py           Task / TaskAttachment 数据模型 + 时间工具
│   ├── manager.py          任务 CRUD / 查询 / 统计 / 软删除 / 同步状态标记
│   ├── sync_engine.py      双向同步引擎（TodoAdapter 接口 + LWW 冲突处理）
│   ├── api.py              pywebview js_api 桥接层
│   └── config.py           配置加载（相对路径解析，禁止硬编码）
├── storage/
│   ├── database.py         SQLite（tasks / task_attachments / sync_meta）
│   └── attachment.py       附件文件管理（下载缓存 / 图片预览 / 孤儿清理）
├── ui/                     todo.html / todo.css / todo.js
├── test/                   离线测试（42 项，无需网络）
└── data/                   运行时生成（todo.db / attachments/ / token_cache.json，已 gitignore）
```

## 快速开始

```bash
# 1. 准备 Azure 应用（获取 client_id）
#    Azure 门户 → 应用注册 → 新注册 → 重定向类型选「移动与桌面应用程序」，重定向 URI：http://localhost
#    添加委派权限：Tasks.Read / Tasks.ReadWrite / offline_access

# 2. 把 client_id 写入 config.json 的 microsoft.client_id

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动桌面应用
python main.py

# 5. 命令行工具（自测用）
python main.py --cli login        # OAuth 登录（设备码流，打印网址+验证码）
python main.py --cli ms-status    # 查看登录状态
python main.py --cli sync         # 手动触发一次双向同步
python main.py --cli list         # 列出全部任务
python main.py --cli stats        # 统计
python main.py --cli create --title "任务" --project "项目" --priority high
python main.py --cli logout       # 清除令牌
```

> 登录方式：桌面 UI 点「Microsoft 登录」（交互式）；失败自动弹设备码窗口（打开网址 + 输入验证码）。
> 首次同步为全量；之后按 `source_id` 增量：不存在 → 新增，存在 → 更新。
> 删除一律**软删除**（`status=deleted`，绝不物理删除）；本地删除会推送 DELETE 到外部。
> 冲突处理：`updated_at` **Last-Write-Wins**（UTC ISO 毫秒，字典序可比）。

## 数据模型

`core/models.py` 定义 Leo Task，核心字段：

```
id / title / description / status / priority / project / tags /
source / source_id / source_list_id / due_date / created_at / updated_at / sync_status
```

| 字段 | 取值 |
|------|------|
| `status` | `todo` / `in_progress` / `completed` / `deleted`（软删除） |
| `priority` | `low` / `medium` / `high` |
| `source` | `leo` / `microsoft`（未来 `github` / `obsidian` / `jira`） |
| `sync_status` | `local`（仅本地）/ `synced` / `pending_push` / `pending_delete` / `error` |

- Microsoft 的 `status`（notStarted/inProgress/completed/...）、`importance`、`categories`、`dueDateTime` 由 `mapper.py` 映射到 Leo 语义；`project` 即 Microsoft 任务列表名。
- 本地新建任务 `source=leo`，推送成功后归属 `source=microsoft` 纳入双向同步。

## 同步规则

1. **拉取（Microsoft → Leo）**：按 `source_id` 判断，不存在则新增；存在且外部 `updated_at` 更新则覆盖本地。
2. **外部删除检测**：本地已同步任务不在外部列表 → 本地软删除（墓碑，不反向推送）。
3. **推送（Leo → Microsoft）**：`local` / `pending_push` / `error` 任务 → create/update；`pending_delete` → DELETE。
4. **附件（图片预览）**：同步时拉取任务图片附件 → 缓存到 `data/attachments/` → UI 直接显示缩略图；本地附件上传外部后同步记录归属。
5. **冲突**：`updated_at` 比较（Last-Write-Wins），后续可扩展 Conflict Resolver。

## 附件与图片预览

- 支持格式：`png / jpg / jpeg / gif / webp`（`config.json` 的 `image_exts`）。
- Microsoft 附件下载 → `data/attachments/{task_id}/` → UI 任务详情直接显示图片缩略图，点击放大。
- 本地任务详情面板「＋」上传图片，保存后同步时上传到 Microsoft。

## 测试

```bash
python -m unittest discover test -v
```

覆盖：数据库 CRUD / 任务管理器 / mapper 转换 / 同步引擎（含 LWW 冲突、外部删除检测）/ 附件存储 / API 桥接（含图片预览路径）。

## 安全

- OAuth 使用 msal（交互式 / 设备码流），**不保存密码**，仅保存令牌缓存于 `data/token_cache.json`。
- `--cli logout` 或 UI「退出登录」清除令牌。

## 未来扩展

1. AI 任务拆解（输入目标 → 自动生成子任务）
2. Daily Log 集成（任务完成 → 自动写入每日记录）
3. LEO OS 接入（Task → Context → Planner → Workflow）

# Obsidian EXE Launcher

Obsidian 插件，在左侧栏提供 ▶ 图标，点击弹出工具面板，调用 `D:\Python\dist\` 下的 EXE 工具。

## 11 个按钮（完整列表）

| # | 图标 | 按钮名 | 功能 | exeName | 弹窗 |
|---|------|--------|------|---------|------|
| 1 | � | 索引更新工具 | 更新所有目录索引 | `index-updater.exe` | 无 |
| 2 | 🔄 | Home修改同步目录 | Home→目录同步 + 移动文件 | `home-to-mulu-sync.exe` | 无 |
| 3 | 🔁 | 目录修改同步home | 目录→Home同步 + 重建 home | `mulu-to-home-sync.exe` | 无 |
| 4 | ✅ | 文件名标题检查 | 检查 .md 文件标题与文件名一致 | `rename-check.exe` | 无 |
| 5 | � | 备份笔记 | 备份 Obsidian 笔记库 | `leodiary-backup.exe` | 备注 |
| 6 | 🐍 | 备份python代码 | 备份 Python 代码到 GitHub | `python-code-sync-GitHub.exe` | 版本说明 |
| 7 | � | 备份Claude Skill | 备份 Skills 到本地 | `claude-skill-backup.exe` | 备注 |
| 8 | ☁️ | Skill同步GitHub | 同步 Skills 到 GitHub | `skill-sync-GitHub.exe` | 版本说明 |
| 9 | �️ | 备份Python代码本地 | 本地备份 Python 代码 | `python-local-backup.exe` | 备注 |
| 10 | 📤 | 文件合并上传GitHub | GUI 合并 文本/MD/Word → MD | `md_merger.exe` | 无 |
| 11 | 🔀 | Skill同步其他Agent | 同步 Claude Skills 到其他 Agent（Codex/Trae/Qoder/project） | `skill-sync-agentcode.exe` | 无 |

### 一键同步

弹窗头部「🚀 一键同步」按钮：按顺序运行 6 个备份/同步工具，共用同一个说明备注（输入框记忆上次内容，下次打开默认显示）：

```
备份笔记 → 备份Claude Skill → 备份Python代码本地 → Skill同步其他Agent → Skill同步GitHub → 备份python代码
```

> **弹窗输入记忆**：所有带弹窗的按钮（含一键同步）都会按按钮记忆上次输入的内容，下次打开弹窗默认显示在输入框并全选，可直接回车复用或重新输入。

## 链路说明

```
用户点击按钮
    ↓
main.ts: launchExe(config) / runSyncAll(remark)
    ├─ 一键同步 → 按顺序 runExe 6 个备份/同步工具，共用同一备注，最后汇总结果
    ├─ .exe  → exec(exeDir + exeName)            exeDir 默认 D:\Python\dist（按钮可用 exeDir 覆盖）
    └─ .py   → exec("python" + exeDir + exeName) 用系统 PATH 中的 python 运行脚本（当前无 .py 按钮，保留备用）
    ↓
目标进程启动（exe 或 python 脚本）
    ↓
弹窗输入参数（promptRequired=true 时，通过 --remark 传递；输入按按钮记忆，下次打开默认显示上次内容）
    ↓
执行逻辑 → 完成 / 报错
    · EXE 与 .py 统一逻辑：从 stdout 按优先级提取「❌xxx失败」→「✅xxx成功」→ 含「汇总」的行 → 最后一行，作为完成提示
    · 进程 error 分支显示「❌ {name} 失败」
```

**py 源码位置**：见 [D:\Python\CLAUDE.md](file:///D:/Python/CLAUDE.md) 第 2 节三方对照表

## 安装

1. 复制 `main.js` + `manifest.json` + `styles.css` 到：
   ```
   D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\
   ```
2. Obsidian 设置 → 第三方插件 → 启用 `EXE Launcher`
3. 左侧栏出现 ▶ 图标

## 构建

```bash
cd D:\Python\projects\obsidian-exe-launcher
npm install
npm run build
```

构建产物 `main.js` 在项目根目录。

### 构建后部署

```powershell
# 复制到 Obsidian 插件目录
Copy-Item "D:\Python\projects\obsidian-exe-launcher\main.js" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\main.js" -Force
Copy-Item "D:\Python\projects\obsidian-exe-launcher\manifest.json" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\manifest.json" -Force
Copy-Item "D:\Python\projects\obsidian-exe-launcher\styles.css" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\styles.css" -Force
```

复制后在 Obsidian 中重新加载插件（设置 → 第三方插件 → 关闭再打开）。

## 配置

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| EXE 目录 | `D:\Python\dist` | EXE 文件所在目录 |
| 按钮大小 | 140 | 按钮尺寸（像素） |
| 按钮顺序 | 默认顺序 | 可拖拽排序 |
| 备注历史 | 无 | 弹窗输入按按钮记忆（`promptHistory`），下次默认显示 |

## 技术栈

- TypeScript + esbuild + Obsidian Plugin API
- 入口：`src/main.ts`
- 配置数组：`EXE_CONFIGS`（11 个按钮定义）+ `SYNC_ALL_TARGETS` / `SYNC_ALL_CONFIG`（一键同步）
- 依赖：`child_process.exec`（调用 EXE）、`fs`（检查 EXE 存在）

## 文件结构

```
obsidian-exe-launcher/
├── src/main.ts             # ⭐ 源码（11 个按钮配置 + 一键同步 + 弹窗/拖拽逻辑）
├── main.js                 # 构建产物（Obsidian 加载）
├── manifest.json           # 插件清单
├── styles.css              # 样式
├── package.json            # 依赖配置
├── esbuild.config.mjs      # 构建配置
├── CLAUDE.md               # 项目级 AI 规则
├── README.md               # 本文件
└── .gitignore
```

## 修改按钮

编辑 `src/main.ts` 的 `EXE_CONFIGS` 数组：

```typescript
{
  name: '按钮名',           // 显示名称
  description: '功能描述',   // 悬停提示
  exeName: 'xxx.exe',       // exe 文件名（默认在 D:\Python\dist），或 .py 脚本名
  icon: ' emoji',           // 按钮 emoji
  exeDir: 'D:\\Python\\tools\\sync-GitHub', // 可选：覆盖默认 exe 目录（如脚本不在 dist）
  promptRequired: true,     // 是否弹窗输入（输入会按按钮记忆，下次默认显示）
  promptLabel: '字段名',    // 弹窗标签
  promptPlaceholder: '...', // 弹窗占位符
}
```

> **.py 脚本按钮**：`exeName` 以 `.py` 结尾时，`launchExe` 自动用系统 `python` 运行（常量 `PYTHON_EXE`）；无需 `promptRequired`。
>
> **完成提示逻辑**：EXE 与 .py 统一，`launchExe` 从子进程 stdout 按优先级提取提示行：`❌xxx失败` → `✅xxx成功` → 含「汇总」的行 → 最后一行；进程 error 分支显示 `❌ {name} 失败`。6 个 Python 脚本（备份笔记 / 备份 python 代码 / 备份 Claude Skill / Skill 同步 GitHub / 备份 Python 代码本地 / Skill 同步其他 Agent）已统一在启动/成功/失败时输出 `🔁 {TASK_NAME} 启动` / `✅ {TASK_NAME} 成功` / `❌ {TASK_NAME} 失败` 格式，便于 `launchExe` 提取。

改后 `npm run build` → 复制到插件目录 → 重新加载插件。

---

通用 AI 开发执行规则
## 1. 开发基本原则
**必须遵守：**
- **稳定性优先** – 任何改动不得降低系统稳定性。
- **数据安全优先** – 用户数据保护高于一切。
- **最小修改原则** – 仅改必需之处，避免大范围变动。
- **模块化设计** – 功能解耦，高内聚低耦合。
- **可维护性优先** – 代码清晰、注释充分、便于后续维护。
- **向后兼容优先** – 接口变更需保持旧版本兼容。
**严格禁止：**
- 未分析直接修改代码
- 大范围重构解决小问题
- 删除已有功能
- 修改未知影响范围的公共接口
- 引入无必要依赖
- 提交临时代码
---
## 2. AI 修改代码流程
### 修改前（必须完成以下步骤）
1. 阅读项目 `CLAUDE.md`（若存在）
2. 阅读 `README.md`，了解项目全貌
3. 理解目录结构，明确各模块定位
4. 查找并定位相关模块
5. 分析调用关系，评估影响范围
6. 确认具体修改范围，列出修改点清单
### 修改策略（按优先级选择）
- **首选**：新增独立模块
- **次选**：扩展已有模块（增加可插拔能力）
- **最后**：修改核心基础代码
### 修改后（必须验证）
- ✅ 功能正常运行
- ✅ 原有功能未被破坏（回归测试）
- ✅ 日志输出正常
- ✅ 配置文件加载正常
- ✅ 应用启动正常
- ✅ 打包/构建流程正常
---
## 3. 模块化设计
**原则**  
一个模块只负责一个主要职责，功能边界清晰。
**禁止事项**  
- ❌ 单文件持续堆积业务逻辑
- ❌ UI、业务、数据混合在同一层
- ❌ 复制粘贴重复代码（必须抽离）
**公共能力必须抽离到独立目录**（如 `utils/`、`common/`、`services/`），包括但不限于：
- 文件操作
- JSON 处理
- 日期时间处理
- 日志封装
- 路径管理
- 网络请求
- 配置读取
---
## 4. 职责分离
| 层级 | 职责 | 包含内容 |
|------|------|----------|
| **UI 层** | 展示与交互 | 页面布局、表单输入、按钮点击、视图更新 |
| **业务层** | 流程与规则 | 业务逻辑编排、数据处理、状态管理 |
| **数据层** | 持久化存储 | 文件读写、数据库操作、远程 API 调用 |
**禁止行为**  
按钮点击事件中直接编写核心业务逻辑（如计算、数据库查询等）——必须委托给业务层处理。
---
## 5. 配置管理
**核心要求**  
所有可变内容必须配置化，**严禁硬编码**。
❌ **错误示例**  
```python
PATH = "D:\data"
```
✅ **正确做法**  
统一使用 `config.json`（或 `yaml`/`env`）管理：
- 文件路径、目录
- 运行参数（超时、重试次数、阈值）
- 功能开关（feature flags）
- 用户偏好设置
- 第三方服务密钥（通过环境变量或加密配置）
**配置变更需记录变更日志，并考虑配置版本兼容性。**
---
## 6. 错误处理
**所有外部操作（不可靠来源）必须进行异常捕获**，包括：
- 文件读写
- 网络请求
- 系统调用
- 数据解析（JSON、XML 等）
- 数据库操作
**处理要求**：
- 捕获具体异常类型（避免笼统的 `Exception`）
- 写入日志（包含上下文信息）
- 向调用方返回明确结果（成功/失败 + 错误码或描述）
**禁止**  
- ❌ 静默失败（吞掉异常且不记录）
- ❌ 空 `except:` 块
---
## 7. 日志规范
**正式项目必须具备完善的日志系统。**
**必须记录的事件**：
- 应用启动与关闭
- 所有错误与异常（含堆栈）
- 核心业务操作（如数据修改、重要计算）
- 外部依赖调用（请求 URL、耗时、返回码）
**禁止事项**：
- ❌ 正式代码中大量使用 `print`（调试信息）
- ❌ 日志中打印敏感信息（密码、密钥、用户隐私）
**推荐使用结构化日志（如 JSON 格式）并配置日志轮转。**
---
## 8. 数据安全
**凡是涉及用户数据（增、删、改、迁移）的操作，必须遵循：**
- **避免覆盖**：修改前备份或使用临时副本
- **保留恢复能力**：提供回滚或撤销机制
- **明确影响范围**：在操作前向用户展示受影响的数据条数/文件列表
- **操作确认**：删除等危险操作需二次确认
**绝对禁止**  
未经用户确认擅自删除或批量覆盖用户数据。
---
## 9. 测试要求
**新增功能必须经过充分验证，涵盖以下场景：**
### 正常流程
- 正常输入 → 预期输出
- 标准路径执行
### 异常流程
- 空数据、缺失字段
- 错误格式（如非 JSON）
- 文件不存在
- 网络超时或断开
- 数据库连接失败
**修改核心模块（如公共库、数据库模型）时，必须对旧功能进行回归测试，确保无破坏。**
---
## 10. Git 规范
**Commit 类型（约定式提交）**：
- `feat:` – 新功能
- `fix:` – 缺陷修复
- `refactor:` – 代码重构（不改变功能）
- `docs:` – 文档更新
- `chore:` – 构建、工具、依赖等维护性更改
**禁止提交到仓库的内容**：
- 缓存文件（`__pycache__/`、`.DS_Store` 等）
- 密钥、证书、密码文件
- 临时文件、调试日志
- 编译产物（`.pyc`、`node_modules/` 视情况可忽略）
---
## 11. AI 禁止行为（红线）
**AI 在开发过程中绝对不得：**
- 未先阅读和理解现有规则即开始修改
- 自行改变项目整体架构（如切换框架、数据库）
- 自行替换技术栈（如从 Flask 换到 Django）
- 删除已有模块或功能（即使认为无用）
- 重写整个项目（除非明确授权）
- 修改与当前任务无关的文件
- 添加未经说明或未经用户确认的功能
---
## 12. 最终目标与开发节奏
**最终目标**  
每个项目都应达到：
- ✅ 模块清晰，边界明确
- ✅ 低耦合，高内聚
- ✅ 易于测试（单元测试覆盖核心逻辑）
- ✅ 易于扩展（新增功能不影响现有）
- ✅ 易于维护（代码可读、文档齐全）
- ✅ 支持长期演进
**开发节奏（小步迭代）**：
- **小步** – 每次改动尽可能小，聚焦单一职责
- **最小影响** – 改动局限在必需范围内
- **可验证** – 每次提交都经过本地验证
- **可回滚** – 保证每个版本可快速回退
---
> **本规则为强制性执行标准，所有 AI 辅助开发必须严格遵守。如有特殊需求，需与团队评审并修改本规则。**

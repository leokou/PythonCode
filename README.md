# D:\Python — Python 工具与项目仓库

本仓库集中管理日常 Python 小工具（`tools\`）、打包产物（`dist\`）与正式项目（`projects\`）。

## 目录结构

```
D:\Python
├── tools\           # 小工具目录（每个工具一个子目录）
│   ├── Obsidian-scripts\  # Obsidian 知识库结构维护脚本（obsidian_common + 4 入口）
│   ├── backup-code\       # Claude Skills / LeoDiary 本地备份
│   ├── chrome-go\         # ChromeGo 代理节点下载
│   ├── clash-clear\       # Clash 代理环境一键清除
│   ├── git-scripts\       # cnb.cool Git 快捷脚本（.bat/.ps1，无需打包，已移至 projects\Obsidian-upload-web\git-scripts）
│   ├── logseq-cleanup\    # Logseq 无用附件清理
│   ├── Merge-file\        # 文件合并桌面工具（md/txt/docx）
│   └── sync-GitHub\       # Skills / 代码 GitHub 同步与本地备份
├── dist\           # exe 打包统一输出目录
├── projects\       # 正式项目（obsidian-exe-launcher / Obsidian-upload-web）
├── build-all-exe.bat  # 一键打包所有小工具 exe 的总入口
├── README.md
└── CLAUDE.md
```

## 打包规范（统一约定）

- **每个含 Python 脚本的工具目录** 内都有一个 `build-exe.bat`，一键把该目录下的入口脚本打包为独立 exe。
- **exe 统一输出到 `D:\Python\dist`**。
- 依赖 PyInstaller（各脚本用到的 python 需已安装）：
  ```bash
  pip install pyinstaller
  ```
- 需指定 python 时设置环境变量：`set PY=你的python.exe` 后运行 `build-exe.bat`。
- `git-scripts\` 已移至 `projects\Obsidian-upload-web\git-scripts\`（纯 `.bat/.ps1`，不打包 exe）。
- 源码文件（.py/.md/.bat）一律 UTF-8 编码；`build-exe.bat` 必须保持 ASCII（中文注释会破坏 cmd 解析）。

### 一键打包所有工具

根目录 `build-all-exe.bat` 会自动遍历 `tools\` 下所有含 `build-exe.bat` 的目录并逐个打包，产物统一输出到 `D:\Python\dist`：

```bat
build-all-exe.bat                      :: 默认用 python
set PY=你的python.exe && build-all-exe.bat   :: 指定 python
```

- 跳过无 `build-exe.bat` 的目录（如已移出的 `git-scripts\`）。
- 某个工具打包失败会标记并在最后汇总报告，不中断其他工具。
- 首次使用前需安装 PyInstaller：`pip install pyinstaller`。

### 各工具打包产物

| 工具目录 | 入口脚本 | 产物 exe |
|----------|----------|----------|
| Obsidian-scripts | home-to-mulu-sync.py / index-updater.py / mulu-to-home-sync.py / rename-check.py | home-to-mulu-sync.exe / index-updater.exe / mulu-to-home-sync.exe / rename-check.exe（另复制 obsidian_common.py / README.md） |
| backup-code | claude-skill-backup.py / leodiary-backup.py | claude-skill-backup.exe / leodiary-backup.exe |
| chrome-go | ChromeGo - 节点爬取脚本 @ 代理节点下载.py | chrome-go.exe |
| clash-clear | 不用clash清除环境.py | clash-clear.exe |
| logseq-cleanup | Logseq - 附件清理脚本 @ 清理无用文件.py | logseq-cleanup.exe |
| Merge-file | md_merger.py | md_merger.exe |
| sync-GitHub | skill-sync-GitHub.py / skill-sync-agentcode.py / python-code-sync-GitHub.py / python-local-backup.py | 对应同名 exe |

## 使用方式

每个工具目录下的 README 有详细说明，含 Python 脚本的工具优先使用打包后的 exe（`D:\Python\dist\*.exe`）。

## Obsidian 插件 exe 依赖

`projects\obsidian-exe-launcher` 插件面板的 11 个按钮对应 `D:\Python\dist` 下 11 个 exe，全部来自 `tools\` 下 4 个工具目录的 `build-exe.bat`：

| 插件按钮 exe | 来源工具目录 |
|--------------|--------------|
| index-updater.exe / home-to-mulu-sync.exe / mulu-to-home-sync.exe / rename-check.exe | `tools\Obsidian-scripts` |
| leodiary-backup.exe / claude-skill-backup.exe | `tools\backup-code` |
| skill-sync-GitHub.exe / skill-sync-agentcode.exe / python-code-sync-GitHub.exe / python-local-backup.exe | `tools\sync-GitHub` |
| md_merger.exe | `tools\Merge-file` |

**快速打包**：根目录 `build-all-exe.bat` 一键打包全部工具（含插件所需 11 个 exe）；单个工具可进对应目录跑 `build-exe.bat`。详见根目录 `CLAUDE.md`。

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
PATH = "D:\\data"
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

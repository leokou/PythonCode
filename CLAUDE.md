# D:\Python - AI 速查手册
> 工作区级规则。项目级规则见各 `projects/*/CLAUDE.md`。
## 1. 目录结构
```
D:\Python/
├── projects/              # 正式项目（独立 Git）
│   ├── leodiarycode/      # LeoDiary 工具链（Python）
│   └── obsidian-exe-launcher/  # Obsidian 插件（TypeScript）
├── tools/                 # 独立工具
│   ├── Obsidian-upload/   # LeoDiary Capture（pywebview 快速记录工具）
│   ├── sync-GitHub/
│   ├── chrome-go/
│   └── logseq-cleanup/
├── experiments/           # 实验验证
├── archive/               # 历史归档
└── tmp/                   # 临时目录
```
## 2. CLAUDE.md 三层体系
| 层级 | 文件 | 职责 |
|------|------|------|
| 工作区 | `D:\Python\CLAUDE.md` | 项目容器、命名、编码、通用规则 |
| 项目 | `projects/*/CLAUDE.md` | 技术栈、import 方式、运行命令 |
| 目录 | （子目录自有规则） | 具体模块分工 |
## 3. 项目速查
### projects/leodiarycode（Python）
核心目录结构：
```
leodiarycode/
├── src/                   # importable 模块
│   ├── obsidian_common.py
│   ├── obsidian_skill_utils.py
│   ├── frontmatter_enrich.py
│   ├── health_check.py
│   └── check_*.py
├── scripts/               # CLI 入口
│   ├── ai_index_builder_v2.py    # ⭐ AI 检索 Builder（Router/Cache/Search/Domain）
│   ├── batch_skill_test.py       # ⭐ 25 查询批量测试脚本
│   ├── ai_retrieval_healthcheck.py  # ⭐ 58 项全链路健康检查
│   ├── ai_index_builder.py
│   ├── index-updater.py
│   ├── home-to-mulu-sync.py
│   ├── mulu-to-home-sync.py
│   ├── rename-check.py
│   ├── Obsidian -备份笔记.py
│   └── Obsidian -备份python代码.py
├── lib/                   # leo-os-tools 子包
├── tests/
└── docs/
```
### projects/obsidian-exe-launcher（TypeScript）
```
obsidian-exe-launcher/
├── src/main.ts
├── manifest.json
├── package.json
├── esbuild.config.mjs
└── main.js
```
## 4. 独立工具（tools/）
| 工具 | 路径 |
|------|------|
| LeoDiary Capture | `tools/Obsidian-upload/`（README.md 见其目录；打包 `build.bat`，规则见该目录 CLAUDE.md） |
| Skill 同步 | `tools/sync-GitHub/skill-sync-agentcode.py` |
| 代理节点爬取 | `tools/chrome-go/ChromeGo - 节点爬取脚本 @ 代理节点下载.py` |
| Logseq 附件清理 | `tools/logseq-cleanup/Logseq - 附件清理脚本 @ 清理无用文件.py` |
## 5. 历史归档（archive/）
原 `_archive_oneoff/` 内容迁移至此。不再维护，参考用。
## 6. Python 脚本 vs Obsidian Skills 分工（防死循环）
> Skills 位于 `C:\Users\leokou\.claude\skills\`。
| 维度 | Python 脚本 | Obsidian Skills |
|------|------------|-----------------|
| 驱动方式 | 手动运行 / EXE 点击 | AI 自然语言调用 |
| 核心能力 | 结构维护、批量操作、快、不用模型 | 内容理解、分类、摘要、语义判断 |
| 处理 🧩目录文件 | 仅删除失效链接 | 分类区域、✍️摘要、frontmatter、重排 |
| 处理 📖目录 索引.md | `目录结构树` + `统计摘要` | `按领域分组`（分类+✍️摘要+状态） |
| 处理文件标题 | 无 frontmatter 文件的标题修正 | 有 frontmatter 文件的标题（Python 跳过） |
**核心原则**：Python 只做行级增删，不重排、不分类、不加摘要；Skill 做内容加工，可以随意重排。
## 7. 常用运行命令
```bash
# AI 检索 - Router 分类
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py router "查询内容"
# AI 检索 - 搜索
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py search "查询内容" --top 5
# AI 检索 - 批量测试（25 查询）
python D:\Python\projects\leodiarycode\scripts\batch_skill_test.py
# AI 检索 - 全链路健康检查（58 项）
python D:\Python\projects\leodiarycode\scripts\ai_retrieval_healthcheck.py
# 索引更新
python D:\Python\projects\leodiarycode\scripts\index-updater.py
# Skill 一致性检查
python D:\Python\projects\leodiarycode\src\obsidian_skill_utils.py skill-health-check "C:\Users\leokou\.claude\skills\Obsidian" "D:\Obsidian\LeoDiary"
```
## 8. 打包 EXE
在 `D:\Python\projects\leodiarycode` 下运行：
```bash
pyinstaller --onefile --name "工具名" "scripts/脚本名.py"
```
EXE 输出到 `dist/`。

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
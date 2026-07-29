# projects/ — 正式项目目录

`D:\Python\projects\` 是 `D:\Python` 工作区下唯一存放业务代码的位置，每个子项目独立 Git。

## 子项目

| 项目 | 语言 | 用途 | 状态 |
|------|------|------|------|
| [leodiarycode](./leodiarycode/) | Python 3.14+ | LeoDiary 知识库工具链 | ⚠️ 大部分已废弃，仅 `scripts/` 4 个 EXE 打包脚本在用 |
| [obsidian-exe-launcher](./obsidian-exe-launcher/) | TypeScript | Obsidian 左侧栏 EXE 启动器插件 | ✅ 维护中 |

## 目录结构

```
D:\Python\projects\
├── README.md                  # 本文件（项目总览）
├── CLAUDE.md                  # 项目目录级 AI 规则
├── leodiarycode/              # LeoDiary Python 工具链
│   ├── src/                   #   importable 模块（v3.0 已废弃）
│   ├── scripts/               #   ⭐ 4 个 EXE 打包脚本（仍在用）
│   ├── lib/                   #   leo-os-tools 子包
│   ├── config/                #   配置（index_rules.yaml / synonyms.yaml）
│   ├── README.md
│   └── CLAUDE.md
└── obsidian-exe-launcher/     # Obsidian 插件
    ├── src/main.ts            #   ⭐ 11 个按钮配置 + 逻辑
    ├── main.js                #   构建产物（Obsidian 加载）
    ├── manifest.json
    ├── package.json
    ├── esbuild.config.mjs
    ├── styles.css
    ├── README.md
    └── CLAUDE.md
```

## 各项目详细说明

### leodiarycode（Python）

**当前实际价值**：仅 `scripts/` 下 4 个 EXE 打包脚本，由 Obsidian EXE Launcher 插件调用：

| 脚本 | 功能 |
|------|------|
| `scripts/index-updater.py` | 目录索引更新（生成 🧩目录、🏠home、📖索引文件） |
| `scripts/home-to-mulu-sync.py` | Home 文件修改后同步到目录 |
| `scripts/mulu-to-home-sync.py` | 目录文件修改后同步到 Home |
| `scripts/rename-check.py` | 确保 .md 文件标题格式正确 |

**v3.0 架构变化**：
- 9 个 Skill 均为纯 AI 执行（Read/Grep/Glob/LS），不再依赖 `src/obsidian_skill_utils.py`、`src/health_check.py` 等
- v3.0 唯一 AI 索引构建工具位于 vault 内：`D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py`
- `src/` 下的 `obsidian_skill_utils.py`、`health_check.py`、`check_*.py` 已废弃

详见 [leodiarycode/README.md](./leodiarycode/README.md)。

### obsidian-exe-launcher（TypeScript）

Obsidian 插件，左侧栏 ▶ 图标弹出工具面板，调用 `D:\Python\dist\` 下的 EXE 工具。

- 11 个按钮（索引更新、Home 同步、目录同步、文件名检查、备份笔记、备份代码、备份 Skill、Skill 同步 GitHub、本地备份、文件合并上传、Skill 同步其他 Agent）
- 入口：`src/main.ts` 的 `EXE_CONFIGS` 数组
- 部署目标：`D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\`

详见 [obsidian-exe-launcher/README.md](./obsidian-exe-launcher/README.md)。

## Git 策略

每个子项目独立 Git：
- `leodiarycode/.git` — 推送到 `leokou/PythonCode`
- `obsidian-exe-launcher/.git` — 单独管理

`projects/` 本身无 `.git`，仅作为容器目录。

## 上级文档

- 工作区总览：[D:\Python\README.md](file:///D:/Python/README.md)
- 工作区 AI 规则：[D:\Python\CLAUDE.md](file:///D:/Python/CLAUDE.md)

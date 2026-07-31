# LeoDiary 工具链

管理 LeoDiary Obsidian 知识库的 Python 自动化工具体系。**已归档（2026-07，LeoDiary v3.0 起 9 个 Skill 均为纯 AI 执行），仅 `scripts/` 下 4 个 EXE 打包脚本留用。**

## EXE 打包脚本（供 Obsidian EXE Launcher 插件调用）

| 脚本 | 功能 |
|------|------|
| `scripts/index-updater.py` | 目录索引更新（生成 🧩目录、🏠home-{dir_name}.md 文件） |
| `scripts/home-to-mulu-sync.py` | Home 文件修改后同步到目录 |
| `scripts/mulu-to-home-sync.py` | 目录文件修改后同步到 Home |
| `scripts/rename-check.py` | 确保 .md 文件标题格式正确 |

## v3.0 AI 索引构建

索引构建工具位于 `D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py`（vault 内），不在本 Python 项目中。

## 本项目的角色

已归档（2026-07）。LeoDiary v3.0 起 9 个 Skill 均为纯 AI 执行，不再调用任何外部 Python 工具模块：

1. `src/` — **不再维护**。v3.0 前被 SKILL.md 引用的 `obsidian_skill_utils.py` 已停用，等价逻辑由各 SKILL.md 的 AI 等价做法直接执行
2. `scripts/` — **仍留用**。4 个 EXE 打包脚本，供 Obsidian EXE Launcher 插件调用（目录索引更新、Home 同步、文件名检查）

## 目录结构

```
leodiarycode/
├── src/                     # 核心工具模块（不再维护，v3.0 前遗留）
│   ├── obsidian_skill_utils.py   # 已停用：等价逻辑由 SKILL.md 的 AI 做法直接执行
│   └── obsidian_common.py       # 公共常量/工具
├── lib/                     # 公共库（不再维护，v3.0 前遗留）
│   ├── leo_common.py            # 通用工具
│   └── lint.py                  # 代码检查
├── scripts/                 # CLI 入口（Obsidian EXE 插件）
│   ├── obsidian_common.py       # 公共常量/工具（VAULT_ROOT、跳过规则等）
│   ├── index-updater.py         # 🤖 AI指令 + 🏠 home + 🧩 目录文件生成/更新
│   ├── home-to-mulu-sync.py     # Home→目录同步
│   ├── mulu-to-home-sync.py     # 目录→Home同步
│   └── rename-check.py          # 文件名标题检查
├── config/                  # 配置文件（index_rules.yaml、synonyms.yaml）
├── docs/                    # 文档目录（当前为空）
├── tmp/                     # PyInstaller 构建临时目录
├── .gitignore
├── README.md
└── CLAUDE.md
```

## 打包 EXE

EXE 输出到 `D:\Python\dist\`（供 Obsidian EXE Launcher 插件读取）。

```bash
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian - 工具名" "scripts/脚本名.py"
```

构建产物说明：
- `D:\Python\dist\` — 最终 EXE（`*.exe`）
- `tmp\spec\` — PyInstaller spec 文件（`*.spec`）
- `tmp\build\` — 构建临时目录

## 模块依赖

- `scripts/` 下脚本通过 `sys.path.insert(0, os.path.dirname(__file__))` 导入同目录的 `scripts/obsidian_common.py`
- `src/obsidian_skill_utils.py` 不再被任何 Skill 调用（v3.0 起纯 AI 执行）

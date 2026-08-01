# LeoDiary 工具链

管理 LeoDiary Obsidian 知识库的 Python 自动化工具体系。

## EXE 打包脚本（供 Obsidian EXE Launcher 插件调用）

| 脚本 | 功能 |
|------|------|
| `scripts/index-updater.py` | 目录索引更新（生成 🧩目录、🏠home、📖索引文件） |
| `scripts/home-to-mulu-sync.py` | Home 文件修改后同步到目录 |
| `scripts/mulu-to-home-sync.py` | 目录文件修改后同步到 Home |
| `scripts/rename-check.py` | 确保 .md 文件标题格式正确 |

## v3.0 AI 索引构建

索引构建工具位于 `D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py`（vault 内），不在本 Python 项目中。

## ⚠️ 本项目的角色（务必知悉）

v3.0 起 9 个 Skill 均为纯 AI 执行，运行时不依赖本项目。本项目仅提供 `scripts/` 下 4 个 EXE 打包脚本，供 Obsidian EXE Launcher 插件调用（目录索引更新、Home 同步、文件名检查）。

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

`scripts/` 下脚本通过 `sys.path.insert(0, os.path.dirname(__file__))` 导入同目录的 `scripts/obsidian_common.py`。

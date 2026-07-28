# LeoDiary 工具链

管理 LeoDiary Obsidian 知识库的 Python 自动化工具体系。

## 包含脚本

| 脚本 | 功能 |
|------|------|
| `scripts/ai_index_builder.py` | AI_INDEX 构建器（全量/增量重建、搜索、缓存、健康检查） |
| `scripts/Obsidian - index_updater.py` | 索引更新（生成 🧩目录、🏠home、📖索引文件） |
| `scripts/Obsidian - Home修改同步移动文件.py` | Home 文件修改后同步到目录 |
| `scripts/Obsidian - 目录修改同步home.py` | 目录文件修改后同步到 Home |
| `scripts/Obsidian - renamepy.py` | 确保 .md 文件标题格式正确 |
| `scripts/Obsidian -备份笔记.py` | 备份 Obsidian 笔记 |
| `scripts/Obsidian -备份python代码.py` | 备份 Python 代码到 GitHub |

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

`src/` 下的模块通过 `import` 被 scripts 引用。任何 scripts 需要 import 的公共代码都应放在 `src/` 中。

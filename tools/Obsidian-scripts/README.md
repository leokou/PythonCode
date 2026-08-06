# Obsidian-scripts

LeoDiary 知识库的 Obsidian 结构维护 Python 脚本集。

## 目录结构
```
Obsidian-scripts/
├── obsidian_common.py     # 共享配置/常量/工具函数（所有脚本共用）
├── home-to-mulu-sync.py   # 🏠 Home 驱动整理（home → 🧩 反向同步 + 搬移 + 修正标题）
├── mulu-to-home-sync.py   # 🧩 目录驱动整理（🧩 搬移 + 重建 home + 修正标题）
├── index-updater.py  *    # 🏷️ 索引文件自动管理（🤖AI指令 / 🏠 home / 🧩 目录 / 📖总路由）
├── rename-check.py        # 🏷️ 文件名标题检查（frontmatter 后紧跟标题）
├── build-exe.bat          # 一键打包 exe 到 D:\Python\dist
├── README.md
└── CLAUDE.md
```

> 注意：文件名实际为 `index-updater.py`（文中展示带空格是因旧版命名历史，统一以仓库为准）。

## 依赖关系
- `obsidian_common.py` 定义所有脚本共享的 `VAULT_ROOT`、跳过白名单、标题修正等，各脚本 `from obsidian_common import ...`。**修改排路径/规则时只需改此文件。**

## 各脚本用途

### 1. `obsidian_common.py` — 共享配置模块
- `VAULT_ROOT` = `D:\Obsidian\LeoDiary`
- 跳过目录 `SKIP_DIRS`（隐藏目录、系统目录、logs、_trash、🤖AI_INDEX 等）
- 跳过文件 `SKIP_FILES_PREFIX` / `SKIP_FILES_EXACT`
- PARA 目录定义 `PARA_DIRS`
- 工具函数：`should_skip_dir` / `should_skip_file` / `read_text_safe` / `has_frontmatter` / `ensure_title_header` / `strip_frontmatter`

### 2. `home-to-mulu-sync.py` — Home 驱动整理
修改了 `🏠 home` 文件后运行：
1. home → 🧩 反向同步（把 home 的修改写回 🧩 目录文件，保留用户注释）
2. 🧩 目录驱动移动（把链接对应的文件移到对应文件夹）
3. 修正标题（确保 .md 第一行为 `# 文件名`）

### 3. `mulu-to-home-sync.py` — 目录驱动整理
修改了 `🧩 目录` 文件后运行：
1. 🧩 目录驱动移动（把链接对应文件移到对应文件夹）
2. 重建所有 home（从 🧩 文件重新生成，同步到 home）
3. 修正标题

### 4. `index-updater.py` — 索引文件自动管理
生成/更新 `🤖 AI指令.md`、一级目录 `🏠 home-*.md`、二至五级 `🧩 目录-*.md`、总路由索引 `📖目录 索引.md`。支持子命令 `record-access`（记录访问频率，供 Skill 调用）。

### 5. `rename-check.py` — 文件名标题检查
确保 frontmatter 在文件开头、紧跟标题（无多余空行）。

## 打包为 exe
运行 `build-exe.bat` 将 4 个入口脚本打包为独立 exe 到 `D:\Python\dist`，并复制 `obsidian_common.py` / `README.md`：
- `home-to-mulu-sync.exe`
- `index-updater.exe`
- `mulu-to-home-sync.exe`
- `rename-check.exe`
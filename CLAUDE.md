# D:\Python — 仓库级 AI 规则

> 本仓库集中管理日常 Python 小工具（`tools\`）、打包产物（`dist\`）与正式项目（`projects\`）。

## 1. 目录定位

| 目录 | 定位 | 说明 |
|------|------|------|
| `tools\` | 小工具集 | 每个工具一个子目录，含源码 + `build-exe.bat` + `README.md` |
| `dist\` | exe 统一输出目录 | 所有 `build-exe.bat` 打包产物集中输出到 `D:\Python\dist` |
| `projects\` | 正式项目 | 独立项目，各自有 CLAUDE.md / README.md |
| `build-all-exe.bat` | 一键打包总入口 | 遍历 `tools\` 下所有含 `build-exe.bat` 的目录并逐个执行，产物统一输出到 `D:\Python\dist` |

## 2. 工具目录规范（强制）

每个含 Python 脚本的工具目录必须包含：
- **入口脚本**（.py）
- **`build-exe.bat`**：一键把该目录入口脚本打包为独立 exe，输出到 `D:\Python\dist`
- **`README.md`**：说明功能 / 使用方式 / 注意事项
- `git-scripts\` 已移出 tools：现在是 `projects\Obsidian-upload-web\git-scripts\`（纯 `.bat/.ps1`，无 Python，不需要 build-exe.bat）

### 打包约定
- exe 统一输出到 `D:\Python\dist`，**禁止**各自散落 dist 目录。
- 根目录 `build-all-exe.bat` 为总入口：遍历 `tools\` 下所有含 `build-exe.bat` 的目录并逐个执行（`call "<目录>\build-exe.bat" < nul` 跳过子 bat 的 pause），任一失败会标记并继续，最后汇总报告。
- `build-exe.bat` 模板要点：
  - 用 `%PY%` 变量指定 python（默认为 `python`），可通过 `set PY=...` 覆盖
  - `--onefile --noconfirm --clean --distpath "%DIST%"`
  - **bat 文件必须保持 ASCII-only**（中文注释会被 cmd 以 GBK 读取导致解析错误）；若 py 文件名含中文，用 `for %%F in (*.py) do set "SRC=%%F"` 解析，不在 bat 里写中文字符
  - 依赖 PyInstaller：`pip install pyinstaller`
- 新增工具目录后，若含 Python 脚本，必须提供 `build-exe.bat`，以便纳入 `build-all-exe.bat` 一键打包。

### 修改规范
- **最小改动**：只改必要文件，不动无关代码。
- **编码 UTF-8**：所有 .py/.md/.bat 一律 UTF-8 保存。
- 新增/修改工具目录后，同步更新根目录 `README.md` 的目录结构与打包产物表。

## 2.5 Obsidian 插件 exe 打包指南（强制）

`projects\obsidian-exe-launcher` 插件（Obsidian EXE Launcher）面板共有 **11 个按钮**，各自调用 `D:\Python\dist` 下对应 exe。**修改工具脚本后必须重新打包对应 exe，否则插件按钮调用的是旧版本。**

### 插件需要打包哪些 exe

| 插件按钮（exeName） | 来源工具目录 | build-exe.bat 位置 |
|---------------------|--------------|--------------------|
| `index-updater.exe` / `home-to-mulu-sync.exe` / `mulu-to-home-sync.exe` / `rename-check.exe` | `tools\Obsidian-scripts` | `tools\Obsidian-scripts\build-exe.bat` |
| `leodiary-backup.exe` / `claude-skill-backup.exe` | `tools\backup-code` | `tools\backup-code\build-exe.bat` |
| `skill-sync-GitHub.exe` / `skill-sync-agentcode.exe` / `python-code-sync-GitHub.exe` / `python-local-backup.exe` | `tools\sync-GitHub` | `tools\sync-GitHub\build-exe.bat` |
| `md_merger.exe` | `tools\Merge-file` | `tools\Merge-file\build-exe.bat` |

> 插件面板按钮定义见 `projects\obsidian-exe-launcher\src\main.ts` 的 `EXE_CONFIGS`。11 个 exeName 必须与 `D:\Python\dist` 实际产物逐一对应，缺一不可。

### 怎么调用 bat 快速打包

- **一键打包全部工具（推荐，覆盖插件所需全部 11 个 exe）**：
  ```bat
  D:\Python\build-all-exe.bat
  ```
  或指定 python 后运行：
  ```bat
  set PY=你的python.exe
  D:\Python\build-all-exe.bat
  ```
- **只打包单个工具目录**（如只改动了 Obsidian-scripts）：
  ```bat
  D:\Python\tools\Obsidian-scripts\build-exe.bat
  ```
- 所有 exe 统一输出到 `D:\Python\dist`；打包依赖 PyInstaller（`pip install pyinstaller`）。
- 打包完成后核对 `D:\Python\dist` 产物齐全，必要时在 Obsidian 中重载插件。

## 3. 编码与路径

- **编码必须为 UTF-8**（所有 .py/.md/.bat）。
- bat 文件例外：内容保持 ASCII，中文说明放 README.md。
- 硬编码路径各工具自行维护（如 vault、备份目标），修改时注意一致性。

## 4. 通用开发规则

本仓库所有开发遵循“通用 AI 开发执行规则”（见根目录 README.md 末尾），核心红线：
- 未分析直接修改代码 / 大范围重构 / 删除已有功能 / 改动无关文件 —— 均禁止。
- 涉及用户数据（增删改迁移）必须备份 + 可回滚 + 二次确认。
- 新增功能必须自测验证（`--check` / `--help` 等防误触发机制保留）。

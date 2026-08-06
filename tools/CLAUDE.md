# tools/ — 小工具集 AI 规则

> 存放日常 Python 小工具，每个工具一个子目录。详见根目录 `D:\Python\CLAUDE.md`（工具目录规范 + 打包约定 + Obsidian 插件 exe 打包指南）。

## 目录定位

| 工具目录 | 定位 |
|----------|------|
| `Obsidian-scripts\` | Obsidian 知识库结构维护（共享模块 `obsidian_common.py` + 4 个入口脚本） |
| `backup-code\` | Claude Skills / LeoDiary 本地备份 |
| `chrome-go\` | ChromeGo 代理节点下载 |
| `clash-clear\` | Clash 代理环境一键清除 |
| `logseq-cleanup\` | Logseq 无用附件清理 |
| `Merge-file\` | 文件合并桌面工具（md/txt/docx） |
| `sync-GitHub\` | Skills / 代码 GitHub 同步与本地备份 |

## 强制规范

- **每个含 Python 脚本的工具目录必须包含**：入口脚本（.py）+ `build-exe.bat` + `README.md`；纯 `.bat/.ps1` 目录（如 `git-scripts\`，已移至 `projects\Obsidian-upload-web\`）例外。
- **编码 UTF-8**：所有 .py/.md/.bat 一律 UTF-8 保存；`build-exe.bat` 必须保持 ASCII-only（中文注释会被 cmd 以 GBK 读取导致解析错误）。
- **exe 统一输出到 `D:\Python\dist`**，禁止各自散落 dist 目录。
- 修改工具脚本后，若该工具被 Obsidian 插件（obsidian-exe-launcher）引用，必须重新打包对应 exe（见根 CLAUDE.md 第 2.5 节）。
- 新增/修改工具目录后，同步更新根目录 `README.md` 与本文件的目录表。

## 打包

- 单个工具：进对应目录跑 `build-exe.bat`（可用 `set PY=...` 指定 python）。
- 全部工具：根目录 `D:\Python\build-all-exe.bat`。

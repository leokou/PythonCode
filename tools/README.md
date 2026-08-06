# tools/ — 小工具集

存放日常 Python 小工具，每个工具一个子目录，含源码 + `build-exe.bat` + `README.md`。

## 目录列表

| 工具目录 | 说明 | 产物 exe |
|----------|------|----------|
| Obsidian-scripts | Obsidian 知识库结构维护（obsidian_common + 4 入口） | home-to-mulu-sync / index-updater / mulu-to-home-sync / rename-check |
| backup-code | Claude Skills / LeoDiary 本地备份 | claude-skill-backup / leodiary-backup |
| chrome-go | ChromeGo 代理节点下载 | chrome-go |
| clash-clear | Clash 代理环境一键清除 | clash-clear |
| logseq-cleanup | Logseq 无用附件清理 | logseq-cleanup |
| Merge-file | 文件合并桌面工具（md/txt/docx） | md_merger |
| sync-GitHub | Skills / 代码 GitHub 同步与本地备份 | skill-sync-GitHub / skill-sync-agentcode / python-code-sync-GitHub / python-local-backup |

## 打包规范

- 每个含 Python 脚本的工具目录内有一个 `build-exe.bat`，一键把入口脚本打包为独立 exe，输出到 `D:\Python\dist`。
- 根目录 `build-all-exe.bat` 遍历 `tools\` 下所有含 `build-exe.bat` 的目录并逐个打包。
- 各工具详细打包/使用说明见各自 README；插件依赖的 exe 打包方法见根目录 `CLAUDE.md` 第 2.5 节。

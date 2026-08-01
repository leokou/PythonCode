# projects/obsidian-exe-launcher — Obsidian EXE Launcher 插件

TypeScript Obsidian 插件，左侧栏 ▶ 图标弹出工具面板，快速启动桌面 exe / python 脚本。

## 技术栈

- TypeScript
- esbuild
- Obsidian Plugin API

## 目录结构

```
obsidian-exe-launcher/
├── src/main.ts           # ⭐ 源码（11 个按钮配置 EXE_CONFIGS + 一键同步 + 弹窗/拖拽逻辑）
├── manifest.json         # 插件清单（id: obsidian-exe-launcher）
├── package.json          # 依赖配置
├── esbuild.config.mjs    # 构建配置
├── main.js               # 编译产物（Obsidian 加载，esbuild 会把中文转义为 \u 序列，属正常）
├── styles.css            # 样式
├── CLAUDE.md             # 本文件
├── README.md             # 完整说明（按钮表 / 链路 / 安装 / 构建 / 修改）
└── .gitignore
```

## 核心结构

- **`EXE_CONFIGS`**：按钮定义数组（11 个）。字段：`name` / `description` / `exeName` / `icon` / `exeDir?` / `promptRequired?` / `promptLabel?` / `promptPlaceholder?`。
- **`PluginData.promptHistory`**：弹窗输入历史，按 `exeName` 存储上次输入；`PromptModal` 打开时默认回填上次内容（全选），确认/回车后写回，输入为空则清除该条记录。
- **`SYNC_ALL_TARGETS` / `SYNC_ALL_CONFIG`**：一键同步定义。`SYNC_ALL_TARGETS` 为按序执行的 6 个备份/同步工具（备份笔记 → 备份Claude Skill → 备份Python代码本地 → Skill同步其他Agent → Skill同步GitHub → 备份python代码）；`SYNC_ALL_CONFIG` 作为一键同步的备注输入配置（`exeName` 为 `__sync_all__`，仅作历史 key，不实际启动）。
- **`launchExe(config, arg?)` / `runExe(config, arg?)`**：`runExe` 返回 `Promise<结果文本>`（✅/❌ 前缀，不抛异常），`launchExe` 负责启动提示并展示结果。
  - `exeName` 以 `.exe` 结尾 → `exec(exeDir + exeName)`，可选 `--remark` 传参。
  - `exeName` 以 `.py` 结尾 → `exec("python" + exeDir + exeName)`，用系统 PATH 中 `python`（常量 `PYTHON_EXE`）运行。
  - **完成提示（EXE/.py 统一）**：从 stdout 按优先级提取 `❌xxx失败` → `✅xxx成功` → 含「汇总」的行 → 最后一行；进程 error 分支显示 `❌ {name} 失败`。6 个 Python 脚本已统一输出 `🔁 {TASK_NAME} 启动` / `✅ {TASK_NAME} 成功` / `❌ {TASK_NAME} 失败` 格式以便提取。
  - `exeDir` 默认 `D:\Python\dist`，按钮可覆盖（如脚本在 `D:\Python\tools\sync-GitHub`）。
- **`runSyncAll(remark)`**：一键同步，按 `SYNC_ALL_TARGETS` 顺序依次 `runExe`，共用同一备注，最后汇总各工具结果。
- **`ExeLauncherModal`**：弹窗，头部「🚀 一键同步」按钮 + 网格按钮 + 拖拽排序 + 设置入口。
- **`PromptModal` / `SettingsModal`**：备注输入（记忆上次内容并回填）/ 按钮大小与顺序设置。

## 构建

```bash
npm install
npm run build
```

构建产物 `main.js` 在项目根目录。

## 部署（已知路径，勿再询问）

- **源仓库**：`D:\Python`（git 根），本插件源码在此。
- **部署目标**：Obsidian vault `D:\Obsidian\LeoDiary`，社区插件目录
  `D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\`。
  覆盖 `main.js`（必要时 `manifest.json` / `styles.css`）即生效；Obsidian 内需重载/重启该插件。
- **注意**：vault 仓库中 `.obsidian/` 被 gitignore，部署文件不进 vault git；
  git 同步仅针对源仓库 `D:\Python`（改完 `npm run build` 后提交 `main.js` + `src/main.ts`）。

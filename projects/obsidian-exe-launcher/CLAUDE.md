# projects/obsidian-exe-launcher — Obsidian EXE Launcher 插件

TypeScript Obsidian 插件，左侧栏 ▶ 图标弹出工具面板，快速启动桌面 exe / python 脚本。

## 技术栈

- TypeScript
- esbuild
- Obsidian Plugin API

## 目录结构

```
obsidian-exe-launcher/
├── src/main.ts           # ⭐ 源码（11 个按钮配置 EXE_CONFIGS + 弹窗/拖拽逻辑）
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
- **`launchExe(config, arg?)`**：启动逻辑。
  - `exeName` 以 `.exe` 结尾 → `exec(exeDir + exeName)`，可选 `--remark` 传参。
  - `exeName` 以 `.py` 结尾 → `exec("python" + exeDir + exeName)`，用系统 PATH 中 `python`（常量 `PYTHON_EXE`）运行；点击即弹「同步中...」，完成取 stdout 含「汇总」的一行作提示。
  - `exeDir` 默认 `D:\Python\dist`，按钮可覆盖（如脚本在 `D:\Python\tools\skill-sync`）。
- **`ExeLauncherModal`**：弹窗，网格按钮 + 拖拽排序 + 设置入口。
- **`PromptModal` / `SettingsModal`**：备注输入 / 按钮大小与顺序设置。

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

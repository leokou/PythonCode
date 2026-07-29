# Obsidian EXE Launcher

Obsidian 插件，在左侧栏提供 ▶ 图标，点击弹出工具面板，调用 `D:\Python\dist\` 下的 EXE 工具。

## 11 个按钮（完整列表）

| # | 图标 | 按钮名 | 功能 | exeName | 弹窗 |
|---|------|--------|------|---------|------|
| 1 | � | 索引更新工具 | 更新所有目录索引 | `index-updater.exe` | 无 |
| 2 | 🔄 | Home修改同步目录 | Home→目录同步 + 移动文件 | `home-to-mulu-sync.exe` | 无 |
| 3 | 🔁 | 目录修改同步home | 目录→Home同步 + 重建 home | `mulu-to-home-sync.exe` | 无 |
| 4 | ✅ | 文件名标题检查 | 检查 .md 文件标题与文件名一致 | `rename-check.exe` | 无 |
| 5 | � | 备份笔记 | 备份 Obsidian 笔记库 | `leodiary-backup.exe` | 备注 |
| 6 | 🐍 | 备份python代码 | 备份 Python 代码到 GitHub | `python-code-sync-GitHub.exe` | 版本说明 |
| 7 | � | 备份Claude Skill | 备份 Skills 到本地 | `claude-skill-backup.exe` | 备注 |
| 8 | ☁️ | Skill同步GitHub | 同步 Skills 到 GitHub | `skill-sync-GitHub.exe` | 版本说明 |
| 9 | �️ | 备份Python代码本地 | 本地备份 Python 代码 | `python-local-backup.exe` | 备注 |
| 10 | 📤 | 文件合并上传GitHub | GUI 合并 文本/MD/Word → MD | `md_merger.exe` | 无 |
| 11 | 🔀 | Skill同步其他Agent | 同步 Claude Skills 到其他 Agent（Codex/Trae/WorkBuddy/Qoder/project） | `skill-sync-agentcode.exe` | 无 |

## 链路说明

```
用户点击按钮
    ↓
main.ts: launchExe(config)
    ├─ .exe  → exec(exeDir + exeName)            exeDir 默认 D:\Python\dist（按钮可用 exeDir 覆盖）
    └─ .py   → exec("python" + exeDir + exeName) 用系统 PATH 中的 python 运行脚本（当前无 .py 按钮，保留备用）
    ↓
目标进程启动（exe 或 python 脚本）
    ↓
弹窗输入参数（promptRequired=true 时，通过 --remark 传递）
    ↓
执行逻辑 → 完成 / 报错
    · EXE 与 .py 统一逻辑：从 stdout 按优先级提取「❌xxx失败」→「✅xxx成功」→ 含「汇总」的行 → 最后一行，作为完成提示
    · 进程 error 分支显示「❌ {name} 失败」
```

**py 源码位置**：见 [D:\Python\CLAUDE.md](file:///D:/Python/CLAUDE.md) 第 2 节三方对照表

## 安装

1. 复制 `main.js` + `manifest.json` + `styles.css` 到：
   ```
   D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\
   ```
2. Obsidian 设置 → 第三方插件 → 启用 `EXE Launcher`
3. 左侧栏出现 ▶ 图标

## 构建

```bash
cd D:\Python\projects\obsidian-exe-launcher
npm install
npm run build
```

构建产物 `main.js` 在项目根目录。

### 构建后部署

```powershell
# 复制到 Obsidian 插件目录
Copy-Item "D:\Python\projects\obsidian-exe-launcher\main.js" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\main.js" -Force
Copy-Item "D:\Python\projects\obsidian-exe-launcher\manifest.json" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\manifest.json" -Force
Copy-Item "D:\Python\projects\obsidian-exe-launcher\styles.css" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\styles.css" -Force
```

复制后在 Obsidian 中重新加载插件（设置 → 第三方插件 → 关闭再打开）。

## 配置

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| EXE 目录 | `D:\Python\dist` | EXE 文件所在目录 |
| 按钮大小 | 140 | 按钮尺寸（像素） |
| 按钮顺序 | 默认顺序 | 可拖拽排序 |

## 技术栈

- TypeScript + esbuild + Obsidian Plugin API
- 入口：`src/main.ts`
- 配置数组：`EXE_CONFIGS`（11 个按钮定义）
- 依赖：`child_process.exec`（调用 EXE）、`fs`（检查 EXE 存在）

## 文件结构

```
obsidian-exe-launcher/
├── src/main.ts             # ⭐ 源码（11 个按钮配置 + 逻辑）
├── main.js                 # 构建产物（Obsidian 加载）
├── manifest.json           # 插件清单
├── styles.css              # 样式
├── package.json            # 依赖配置
├── esbuild.config.mjs      # 构建配置
├── CLAUDE.md               # 项目级 AI 规则
├── README.md               # 本文件
└── .gitignore
```

## 修改按钮

编辑 `src/main.ts` 的 `EXE_CONFIGS` 数组：

```typescript
{
  name: '按钮名',           // 显示名称
  description: '功能描述',   // 悬停提示
  exeName: 'xxx.exe',       // exe 文件名（默认在 D:\Python\dist），或 .py 脚本名
  icon: ' emoji',           // 按钮 emoji
  exeDir: 'D:\\Python\\tools\\sync-GitHub', // 可选：覆盖默认 exe 目录（如脚本不在 dist）
  promptRequired: true,     // 是否弹窗输入
  promptLabel: '字段名',    // 弹窗标签
  promptPlaceholder: '...', // 弹窗占位符
}
```

> **.py 脚本按钮**：`exeName` 以 `.py` 结尾时，`launchExe` 自动用系统 `python` 运行（常量 `PYTHON_EXE`）；无需 `promptRequired`。
>
> **完成提示逻辑**：EXE 与 .py 统一，`launchExe` 从子进程 stdout 按优先级提取提示行：`❌xxx失败` → `✅xxx成功` → 含「汇总」的行 → 最后一行；进程 error 分支显示 `❌ {name} 失败`。6 个 Python 脚本（备份笔记 / 备份 python 代码 / 备份 Claude Skill / Skill 同步 GitHub / 备份 Python 代码本地 / Skill 同步其他 Agent）已统一在启动/成功/失败时输出 `🔁 {TASK_NAME} 启动` / `✅ {TASK_NAME} 成功` / `❌ {TASK_NAME} 失败` 格式，便于 `launchExe` 提取。

改后 `npm run build` → 复制到插件目录 → 重新加载插件。

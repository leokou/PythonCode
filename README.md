# Python 工具集 & Obsidian 插件

个人自研的 Python 脚本工具集和 Obsidian 插件，用于笔记管理、文件整理和代码备份。

## 目录结构

```
D:\Python/
├── Obsidian自研插件/
│   └── obsidian-exe-launcher/       # Obsidian EXE 启动器插件
│       ├── src/main.ts               # 插件源码（TypeScript）
│       ├── esbuild.config.mjs        # 构建配置
│       ├── manifest.json             # 插件清单
│       ├── package.json              # 依赖配置
│       ├── main.js                   # 编译产物（插件入口）
│       └── styles.css                # 插件样式
├── python代码备份/                    # 脚本备份副本
│   ├── ChromeGo - 节点爬取脚本 @ 代理节点下载.py
│   ├── Logseq - 附件清理脚本 @ 清理无用文件.py
│   ├── Obsidian - Home修改同步移动文件.py
│   ├── Obsidian - index_updater.py
│   ├── Obsidian - renamepy.py
│   ├── Obsidian - 目录修改同步home.py
│   └── Obsidian -备份笔记.py
├── .gitignore                        # Git忽略配置
├── ChromeGo - 节点爬取脚本 @ 代理节点下载.py
├── Logseq - 附件清理脚本 @ 清理无用文件.py
├── Obsidian - Home修改同步移动文件.py
├── Obsidian - index_updater.py
├── Obsidian - renamepy.py
├── Obsidian - 目录修改同步home.py
├── Obsidian -同步GitHub.py
├── Obsidian -备份python代码.py
├── Obsidian -备份笔记.py
└── README.md
```

## Python 脚本说明

### Obsidian 笔记管理工具

| 脚本 | 功能 | 说明 |
|------|------|------|
| `Obsidian - index_updater.py` | 索引更新工具 | 扫描 `D:\Obsidian\LeoDiary`，自动生成/更新各级目录的索引文件（🧩目录-*.md、🏠home-*.md、🤖AI指令.md），支持失效链接清理和新链接追加 |
| `Obsidian - Home修改同步移动文件.py` | Home→目录同步 | 修改了 home 文件后运行，将 home 内容同步到对应的🧩目录文件，并执行文件移动操作 |
| `Obsidian - 目录修改同步home.py` | 目录→Home同步 | 修改了🧩目录文件后运行，将🧩目录内容反向同步到 home 文件，并执行文件移动操作 |
| `Obsidian - renamepy.py` | 文件名标题检查 | 扫描所有 .md 文件，确保第一行为 `# 文件名` 格式，自动修正不符合的文件 |

### 备份与同步工具

| 脚本 | 功能 | 说明 |
|------|------|------|
| `Obsidian -备份笔记.py` | 备份Obsidian笔记 | 将 `D:\Obsidian\LeoDiary` 备份到 `D:\Obsidian\Backup\LeoDiary_时间戳`，自动跳过隐藏文件夹 |
| `Obsidian -同步GitHub.py` | 同步GitHub | 自动同步两个仓库（PythonCode + ObsidianLeoDiary）到 GitHub |
| `Obsidian -备份python代码.py` | 备份Python代码 | 将 `D:\Python` 同步到 `https://github.com/leokou/PythonCode` |

### 其他工具

| 脚本 | 功能 | 说明 |
|------|------|------|
| `ChromeGo - 节点爬取脚本 @ 代理节点下载.py` | 代理节点爬取 | 从订阅地址下载代理节点配置 |
| `Logseq - 附件清理脚本 @ 清理无用文件.py` | Logseq附件清理 | 清理 Logseq 中未被引用的附件文件 |

## Obsidian 插件说明

### EXE Launcher（obsidian-exe-launcher）

一个 Obsidian 插件，提供可视化界面快速启动桌面工具 exe。

#### 功能

点击 Obsidian 左侧栏的 ▶ 图标，弹出工具面板，包含 7 个快捷按钮：

| 按钮 | 图标 | 功能 | 启动的exe |
|------|------|------|-----------|
| 索引更新工具 | 📋 | 更新所有目录索引 | `D:\Python\dist\索引更新工具.exe` |
| Home修改同步目录 | 🔄 | Home→目录同步 | `D:\Python\dist\Home修改同步目录.exe` |
| 目录修改同步home | 🔁 | 目录→Home同步 | `D:\Python\dist\目录修改同步home.exe` |
| 文件名标题检查 | ✏️ | 检查.md文件标题 | `D:\Python\dist\文件名标题检查.exe` |
| 备份笔记 | 📦 | 备份Obsidian笔记 | `D:\Python\dist\Obsidian -备份笔记.exe` |
| 同步GitHub | 🚀 | 同步两个仓库到GitHub | `D:\Python\dist\Obsidian -同步GitHub.exe` |
| 备份python代码 | 🐍 | 备份Python代码到GitHub | `D:\Python\dist\Obsidian -备份python代码.exe` |

#### 安装方式

1. 将 `obsidian-exe-launcher` 文件夹复制到 `D:\Obsidian\LeoDiary\.obsidian\plugins\`
2. 在 Obsidian 设置 → 第三方插件中启用 "EXE Launcher"
3. 左侧栏出现 ▶ 图标即可使用

#### 开发与构建

```bash
cd Obsidian自研插件\obsidian-exe-launcher
npm install        # 安装依赖
npm run build      # 编译 TypeScript → main.js
```

#### 技术栈

- **语言**：TypeScript
- **构建工具**：esbuild
- **插件API**：Obsidian Plugin API
- **exe路径**：统一从 `D:\Python\dist\` 目录加载

## 打包说明

所有 Python 脚本通过 PyInstaller 打包为 exe：

```bash
cd D:\Python
pyinstaller --onefile --console --name "脚本名" "脚本名.py"
```

生成的 exe 位于 `D:\Python\dist\` 目录下。

## Git 仓库

| 仓库 | 地址 | 内容 |
|------|------|------|
| PythonCode | https://github.com/leokou/PythonCode | Python 脚本和 Obsidian 插件源码 |
| ObsidianLeoDiary | https://github.com/leokou/ObsidianLeoDiary | Obsidian 笔记库 |

## 环境

- **操作系统**：Windows 11
- **Python**：3.14
- **Node.js**：用于插件构建
- **Obsidian**：0.15.0+

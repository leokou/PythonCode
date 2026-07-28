# projects/obsidian-exe-launcher — Obsidian EXE Launcher 插件

TypeScript Obsidian 插件，提供可视化界面快速启动桌面工具 exe。

## 技术栈

- TypeScript
- esbuild
- Obsidian Plugin API

## 目录结构

```
obsidian-exe-launcher/
├── src/main.ts           # 源码
├── manifest.json         # 插件清单
├── package.json          # 依赖配置
├── esbuild.config.mjs    # 构建配置
├── main.js               # 编译产物
└── styles.css            # 样式
```

## 构建

```bash
npm install
npm run build
```

# Obsidian-upload（LeoDiary Capture）

> 目录级规则。技术栈、结构、运行命令、关键约定。

## 1. 项目定位

LeoDiary 快速记录工具：Markdown + 图片上传 + Obsidian 保存。
`Python + HTML/CSS/JS + Edge WebView2（pywebview 6）`，禁止 Tkinter / PyQt 默认控件界面。

## 2. 技术栈与依赖

| 组件 | 用途 |
|------|------|
| pywebview 6 | WebView2 桌面窗口（EdgeChromium 后端） |
| CodeMirror 6 | Markdown 编辑器（行号/折叠/高亮，esbuild 打包 IIFE） |
| marked.js | 右侧实时预览渲染 |
| pystray | 系统托盘（点 X 隐藏） |
| keyboard | 全局热键 Alt+S 呼出窗口 |
| requests | PicGo HTTP API 上传 |
| Pillow | 剪贴板图片解码 |

前端库必须**本地化**到 `web/vendor/`（file:// 加载，ESM 不可用，需 IIFE/UMD）。

## 3. 项目结构

```
Obsidian-upload/
├── main.py          入口：窗口 / js_api（upload_image·save·save_log）/ 托盘 / 热键
├── uploader.py      剪贴板图片 → PicGo HTTP API → Cloudflare R2 → ![](URL)
├── markdown.py      保存「#### 时间戳+正文+---」/ obsidian:// 打开 / 调试日志
├── config.json      picgo_api / inbox_file / flashnote_file / log_dir / vault_name
├── build.bat        PyInstaller 单文件打包
├── web/
│   ├── index.html   顶部标题栏 + 左50%编辑 + 右50%预览 + 底部三保存按钮
│   ├── app.js       CM6 编辑器 + 按比例双向同步滚动 + 图片粘贴 + saveNote/saveLog
│   ├── style.css    深色 Obsidian 风格
│   └── vendor/      cm6.min.js（CodeMirror 6 bundle）、marked.min.js
└── dist/Obsidian-upload.exe
```

## 4. 关键约定

- 所有文件 **UTF-8** 编码。
- 默认窗口 **1800×1400**，min_size 1280×720，可缩放/最大化。
- 保存逻辑统一 `append_note(path, content)`，格式 `#### yyyy-MM-dd HH:mm:ss` + 正文 + `---` 追加，不覆盖。
- 日志文件：`log_dir\yyyy-MM-dd 周X.md`（周X 由系统日期计算）。
- 图片上传：PicGo 字段名必须为 `files`（multer `upload.array("files")`），返回 `result[0]` 为 URL。
- 图片粘贴拦截在 **document 捕获阶段**（`e.preventDefault()+stopPropagation()`），检测 `clipboardData.items` + `files` 兜底；文字粘贴放行。
- 同步滚动：按 `scrollTop/(scrollHeight-clientHeight)` 比例双向同步，`syncing` 标志防回环。
- Alt+S 全局热键需**管理员身份**运行 EXE 才生效（keyboard 库限制）。

## 5. 运行命令

```bash
# 源码运行
python main.py

# 打包 EXE（单文件无控制台，web 资源 + config.json 一并打入）
build.bat
# 等价命令：
pyinstaller --onefile --windowed --name Obsidian-upload --add-data "web;web" --add-data "config.json;." main.py

# 核心模块单测
python C:\Users\leokou\AppData\Local\Temp\opencode\test_obs_upload_v2.py
```

## 6. 修改前端库（CodeMirror 6 重新打包）

```bash
cd C:\Users\leokou\AppData\Local\Temp\opencode\cm6-build
npm install @codemirror/state @codemirror/view @codemirror/language @codemirror/commands @codemirror/autocomplete @codemirror/search @codemirror/lang-markdown @codemirror/theme-one-dark
npx esbuild bundle.js --bundle --minify --format=iife --platform=browser --target=chrome110 --outfile=D:\Python\tools\Obsidian-upload\web\vendor\cm6.min.js
```

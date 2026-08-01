# LeoDiary Capture（Obsidian-upload）

> Obsidian + PicGo + Cloudflare R2 专用快速记录工具。
> Markdown 编辑、图片一键上传、Obsidian 笔记/日志保存，托盘常驻。

## 功能

- **Markdown 编辑**：CodeMirror 6 专业编辑器（行号、折叠、语法高亮、自动补全）
- **实时预览**：右侧 marked.js 渲染，与编辑区**按比例双向同步滚动**
- **图片粘贴上传**：`Ctrl+V` 剪贴板图片 → PicGo HTTP API → Cloudflare R2 → 自动插入 `![图片](URL)`，预览立即显示
- **快速保存**：
  - 保存 Inbox → `D:\Obsidian\LeoDiary\My-Inbox.md`
  - 保存 FlashNote → `D:\Obsidian\LeoDiary\🧠 FlashNote.md`
  - 保存日志 → `D:\Obsidian\LeoDiary\Journals\yyyy-MM-dd 周X.md`（自动按日期命名，追加不覆盖）
- **托盘常驻**：点窗口 X 隐藏到后台继续运行
- **全局热键**：`Alt+S` 呼出主窗口（需管理员身份运行才全局生效）

保存格式统一为：

```markdown
#### 2026-08-01 19:31:53

内容...

---
```

## 使用流程

1. 以管理员身份运行 `Obsidian-upload.exe`（双击或放启动目录）
2. `Alt+S` 呼出窗口（或点击托盘图标）
3. 输入 Markdown，`Ctrl+V` 粘贴图片自动上传 Cloudflare
4. 点击底部「保存 Inbox」/「保存 FlashNote」/「保存日志」

## 快捷键

| 按键 | 功能 |
|------|------|
| `Alt+S` | 呼出主窗口 |
| `Ctrl+V` | 剪贴板图片 → 上传 → 插入 `![](URL)`（文字则正常粘贴） |
| `Ctrl+Enter` | 保存到 Inbox |

## 项目结构

```
Obsidian-upload/
├── main.py          入口：pywebview 窗口 + js_api + 托盘 + 全局热键
├── uploader.py      剪贴板图片 → PicGo HTTP API → Cloudflare R2 → Markdown 链接
├── markdown.py      保存逻辑 / obsidian:// 打开 / 调试日志
├── config.json      配置文件（PicGo / 文件路径 / 日志目录）
├── build.bat        打包脚本
├── web/
│   ├── index.html   界面结构
│   ├── style.css    深色主题（Obsidian 风格）
│   ├── app.js       编辑器 / 预览 / 同步滚动 / 图片粘贴 / 保存
│   └── vendor/      cm6.min.js、marked.min.js（本地化，离线可用）
└── dist/Obsidian-upload.exe
```

## 配置（config.json）

```json
{
  "picgo_api": "http://127.0.0.1:36677/upload",
  "cloudflare_domain": "https://pub-xxx.r2.dev",
  "inbox_file": "D:\\Obsidian\\LeoDiary\\My-Inbox.md",
  "flashnote_file": "D:\\Obsidian\\LeoDiary\\🧠 FlashNote.md",
  "log_dir": "D:\\Obsidian\\LeoDiary\\Journals",
  "vault_name": "LeoDiary"
}
```

> 把 `config.json` 复制到 EXE 同目录即可自定义，无需重新打包。

## 依赖

- Python 3.10+（实测 3.14）
- `pywebview`（含 WebView2 Runtime，Win10/11 自带）
- `Pillow`、`requests`、`pystray`、`keyboard`
- Node.js（仅重新打包 CodeMirror 时用到，运行/使用 EXE 不需要）
- 本地 [PicGo](https://picgo.github.io/PicGo-Doc/) 服务（端口默认 36677，R2 图床）

## 打包

```bash
build.bat
# 等价命令：
pyinstaller --onefile --windowed --name Obsidian-upload ^
  --add-data "web;web" --add-data "config.json;." main.py
```

输出：`dist\Obsidian-upload.exe`（单文件，约 40MB）。

## 日志

- 调试日志：`%APPDATA%\Obsidian-upload\upload_debug.log`（上传成功/失败）
- 笔记日志：`log_dir\yyyy-MM-dd 周X.md`（保存日志按钮生成，默认 `D:\Obsidian\LeoDiary\Journals`）

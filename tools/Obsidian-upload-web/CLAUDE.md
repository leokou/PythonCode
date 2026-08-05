# LeoDiary Capture 项目开发规范

项目名称：LeoDiary Capture（Obsidian-upload-web）
技术栈：Python + HTML/CSS/JS + Edge WebView2（pywebview 6.x）+ CodeMirror 6 + marked.js
打包：PyInstaller onedir 单文件夹 EXE（由用户手动运行 build.bat 打包，AI 禁止自动执行打包命令）

> 本文档仅记录项目特定约束与陷阱。通用编程原则（错误处理、日志、测试、Git 规范等）AI 本身已掌握，不再赘述。功能介绍详见 README.md。

---

## 一、最高开发原则（AI 禁止行为红线）

- **不删除已有功能**：即使认为「无用」「冗余」，删除前必须确认。
- **不修改未知影响范围的公共接口**：js_api 暴露给前端 JS 的方法签名不得改名/改参。
- **不大范围重构**：为小需求不修改大量无关代码、不重写历史模块。
- **不堆积 main.py**：业务逻辑必须落到 lib/backend 或 lib/modules，main.py 只做编排。
- **不往旧大文件堆代码（新增功能必须独立成文件）**：新功能必须新建独立模块文件，**禁止把代码追加进现有的 `script.js` / `*.html` / `*.py` 等大文件**。前端：新功能写到 `frontend/xxx.js` 独立文件并在 `editor.html` 按序引入（全局函数需先于 `script.js` 定义）；后端：在 `lib/modules/` 或 `lib/backend/` 新建独立 `.py`。已有功能扩展优先新增函数/模块而非膨胀旧文件（详见「十一、3」代码修改规则）。
- **不改变技术栈**：禁止用 Tkinter / PyQt / AutoHotkey 替代 Web UI；旧入口 `Obsidian-upload.py`（Tkinter）已删除，禁止恢复。
- **不随意修改 to-do 模块**：`tools/to-do/` 是独立子模块，无用户明确指令**禁止修改**其中任何文件（auth / api / sync / ui 等）。该模块登录状态持久化机制经过多轮调试才稳定，改动极易引入回归。**尤其警惕"保存"相关逻辑**（`token_cache.json` / `login_state.json` / `save_cache()` / `is_logged_in()`），这是多轮调试才稳定的核心机制，任何改动都可能导致「每次重启都要重新登录」的回归。
- **不随意修改预览区代码（除非用户明确要求）**：预览区（contenteditable `#preview`）与编辑器↔预览区双向同步（`script.js` 中的 `_syncPreviewToEditor` / `_highlightLine` / 预览区 `beforeinput`/`keydown`/`input` 监听 / 滚动同步 等）代码高度纠缠，根因是「双真相源 + markdown→HTML 有损非双射映射」，历史上经历 13+ 轮修复仍易回归。**无用户明确需求，禁止改动该区域任何代码**。相关既有机制说明见「十三、编辑区与预览区联动机制」，仅供理解、不构成改动许可。
- **新增功能原则**：独立模块 / 可插拔 / 低耦合 / 复用已有能力 / 不依赖 UI 与网络（便于独立测试）。
- **不自动打包 EXE（用户手动打包）**：AI 禁止执行 `build.bat` 或 `pyinstaller` 任何命令。用户手动运行 `build.bat` 打包 EXE。AI 不得以任何理由自动执行打包操作。

---

## 二、项目目录结构（重构后）

```
Obsidian-upload-web/
├── lib/                    Python 包根
│   ├── __init__.py
│   ├── core/               核心层（入口与编排）
│   │   ├── __init__.py
│   │   ├── main.py         程序入口：四窗口 + js_api + 托盘 + 单实例 + 看门狗（禁止写业务）
│   │   ├── api.py          Api / SettingsApi / ToolApi 三个 js_api 类
│   │   ├── window_manager.py 热键调起窗口的强制前台聚焦
│   │   └── settings.py     settings.json 读写（默认保存地址）
│   ├── backend/            后端业务层
│   │   ├── __init__.py
│   │   ├── storage.py      聚合追加保存（save_note / save_daily_log）
│   │   ├── markdown.py     聚合格式 / obsidian:// 打开 / 调试日志
│   │   ├── uploader.py     剪贴板图片 → PicGo → R2 → Markdown 链接
│   │   ├── clipboard_parser.py 剪贴板 HTML 解析（SAX 式遍历，DOM 顺序提取 text/image 节点）
│   │   ├── html_converter.py   节点列表 → Obsidian Markdown（![[filename]] 附件引用）
│   │   ├── image_handler.py    图片保存（base64 解码 / 网络下载 / 剪贴板位图 → attachments/）
│   │   ├── capture.py      Capture 窗口配置 + 聚合保存路径（config.json 的 capture_file）
│   │   └── search_engine.py 工作区内容搜索（逐行增量匹配、limit 截断）
│   └── modules/            功能模块层
│       ├── __init__.py
│       ├── pages.py        pages.json 元数据 + Tab 独立文件管理（覆盖写）
│       ├── theme_manager.py 主题配置读写（settings.json theme 字段）
│       ├── layout_store.py 布局记忆（四个窗口独立保存，`layout_flash`/`layout_inbox`/`layout_log`/`layout_capture`）
│       ├── workspace.py     工作区管理（workspace.json 增删）
│       ├── file_tree.py    文件树懒加载扫描（explorer_exts 显示 / search_exts 搜索规则）
│       ├── file_explorer.py 资源管理器后端编排（薄转发，复用 workspace/file_tree/history）
│       ├── file_ops.py     右键菜单后端（剪贴板 / 资源管理器 / VSCode / 重命名 / 复制副本 / 移动 / 删除到回收站）
│       ├── file_assoc.py   文件关联打开 + 单实例文件转发
│       ├── history.py      历史记录持久化（record_open / record_edit / rename / move_path / remove_tree）
│       ├── favorites.py    收藏夹
│       ├── canvas_server.py 画布本地 HTTP 服务（Drawnix ES Module 需 HTTP 加载，127.0.0.1 随机端口，随首次打开懒启动/随退出）
│       └── todo_window.py   To Do 窗口编排（复用 tools/to-do 独立模块，懒加载：首次 open_todo 时创建 + show 复用 + 退出销毁；启动不再预创建，避免加载 msal/数据库）
├── frontend/              前端资源（原 web/ 目录）
│   ├── editor.html / settings.html / tools.html
│   ├── script.js / storage.js / tab-manager.js / explorer.js / context-menu.js / settings.js / tools.js
│   ├── js/                 layout / resize / outline / history / workspace / search / theme-manager / theme-loader / file-tree / favorites
│   ├── themes/             主题 CSS（window/ editor/ preview/ 三子目录，以 body[data-*-theme="id"] 作用域）
│   ├── gen_themes.py       编辑器主题 CSS 生成脚本（唯一数据源，见「十二、2」）
│   ├── editor-layout.css   编辑器布局层 / editor-syntax.css 语法层（均引用 --cm-* 变量）
│   ├── vendor/             cm6.min.js / marked.min.js（离线本地化）
│   └── theme.css / style.css / explorer.css / settings.css / tools.css
├── commands/               通用模块（保持原位）
│   ├── __init__.py
│   ├── logger.py           结构化日志（app.log，持久句柄 + 目录缓存）
│   ├── app_utils.py        窗口置顶、屏幕居中、错误弹窗、pick_folder（不用 Tkinter）
│   ├── hotkey_manager.py   RegisterHotKey 系统级热键 + 看门狗（30秒检测 + 2分钟强制重注册）
│   └── performance.py      性能监控（mark/measure/log，写 performance.log）
├── tools/                  工具插件目录（tools.json + clean_empty_lines/ + drawnix/ + to-do/，保持原位）
├── config/config.json      内嵌配置文件
├── scripts/make_icon.py    生成 app.ico
├── spec/                   PyInstaller spec 输出目录
├── test/test-theme-run.py  主题调试脚本
├── build.bat               打包脚本（用户手动执行）
├── app.ico
├── CLAUDE.md
└── README.md
```

---

## 三、关键技术约束（必读）

### 1. 入口变更
- 新入口：`lib/core/main.py`（旧 `main.py` 与 `Obsidian-upload.py` 已删除）
- PyInstaller 入口：`lib\core\main.py`

### 2. sys.modules 注册（重要陷阱）
`lib/core/main.py` 顶部必须保留：
```python
sys.modules.setdefault('lib.core.main', sys.modules[__name__])
```
原因：以 `__main__` 运行（PyInstaller 打包 / `python lib/core/main.py`）时，`sys.modules['lib.core.main']` 不存在，api.py 的 `from lib.core import main as _main` 会 import 失败。setdefault 注册后 api.py 才能拿到本模块对象访问全局状态。

### 3. api.py 全局状态访问机制
- `lib/core/api.py` 包含 `Api`（编辑器窗口，四份实例独立编辑状态）/ `SettingsApi`（设置窗口）/ `ToolApi`（工具箱）三个类。
- 通过 `from lib.core import main as _main` 拿到 main 模块引用，方法调用时访问 main.py 的全局变量：
  - `_windows`（四窗口实例字典）/ `_tools_window` / `_page_seq`
  - `WINDOW_TITLES` / `_set_last_active` / `_safe_show_window`
  - `log_dir` / `resource_path` / `cfg`（运行时配置）
- 修改这些全局状态时，main.py 与 api.py 必须保持一致。

### 4. 包 import 规则
- 全部包结构 import：`from lib.backend import storage`、`from lib.modules import file_explorer`、`from lib.core import settings`、`from commands.logger import log_info`。
- lib/core, lib/backend, lib/modules, commands 都是 Python 包（有 `__init__.py`）。
- 别名约定：`storage` / `capture as capture_store` / `history as history_store` / `workspace as workspace_store` / `pages as page_store` / `theme_manager as theme_store` / `favorites as favorites_store`。

### 5. resource_path 更新
- `web` → `frontend`（前端资源根目录）
- `config.json` → `config/config.json`（运行时配置）
- PyInstaller 打包：`--add-data "frontend;frontend"`、`--add-data "config/config.json;config"`
- **tools.json 是单文件**：必须 `--add-data "tools\tools.json;tools"`（分号后是**目录**）。若写成 `;tools\tools.json`，PyInstaller 会把目标当目录嵌套成 `tools\tools.json\tools.json`，`resource_path("tools/tools.json")` 读不到，`ToolApi._load()` 静默回退 → 新增的内置工具永远合并不进用户配置。

---

## 四、pywebview 陷阱（必须保留）

### 1. 参数命名陷阱
暴露给 JS 的 API 方法参数名**禁止使用 `window`**：会遮蔽 JS 全局 `window` 对象，导致 `window.pywebview._jsApiCallback(...)` 报 `Cannot read properties of undefined`。
- 反例：`def save_theme(self, window)` ← 禁止
- 正例：`def save_theme(self, window_theme)` ← 用别名
- pywebview 的 `sanitize_params` 只转义 JS 保留字（如 `class`/`return`），不转义 `window`/`document` 等全局变量名，必须人工避免。

### 2. evaluate_js 广播陷阱
pywebview edgechromium 后台线程调用 `evaluate_js` 会破坏 JS 桥接内部状态（`_jsApiCallback` 冲突）。
- 主题同步**禁止**用 Python `evaluate_js` 广播。
- 改用 JS 端轮询：`frontend/js/theme-manager.js` 每 2 秒调用 `get_theme()` 检测变化并同步 apply（最多 2 秒延迟）。

### 3. Drawnix 画布桥接陷阱（canvas-bridge.js）
- 导入链路：工具箱「🖼️ 导入画布」→ `Api.import_markdown_to_canvas(content)` → `_main._canvas_server.submit_import({"markdown": md})` → 画布内 `canvas-bridge.js` 每 2 秒轮询 `GET /api/import` 一次性消费（读后清空，兼容旧 `{"data":...}` 字段）。
- **IndexedDB 存对象禁止 JSON 序列化**：localforage 的 IndexedDB driver 可直接存/取 JS 对象，向 Drawnix 写数据必须 `store.put(data, CONTENT_KEY)` 传对象；若传 `JSON.stringify` 字符串，Drawnix 读回 `e.children` 为 undefined → `undefined.forEach` 白屏。
- 解析用 Drawnix 官方解析器：动态 `import('/assets/dist-CikEzr4-.js')` 的 `parseMarkdownToDrawnix(md)`（根节点 `type:'mindmap'` + `isRoot:true`，节点 `el.points=[[0,0]]`），外包 `{children:[el], viewport:{zoom:1}, theme:{themeColorMode:'default'}}` 写入。

---

## 五、数据安全红线

### 1. 聚合文件 → 只追加，禁止覆盖
- `storage.save_note()` 写入 inbox_file / flashnote_file / capture_file / log_dir 文件时**只追加**。
- 格式：`#### yyyy-MM-dd HH:mm:ss` + 正文 + `---`
- 禁止覆盖旧内容（用户历史笔记会丢失）。

### 2. Tab 独立文件 → 覆盖写，禁止追加
- `pages.py` 管理的 Tab 缓存文件（`{save_path}\Inbox\xxx.md` 等）**覆盖写**，不追加。
- 编辑变化 → 3 秒 debounce 覆盖；每 60 秒保险保存全部；首行标题变化 → 1200ms debounce 自动重命名；编辑↔预览焦点切换立即落盘。

### 3. 删除 → 走回收站，禁止物理删除
- `file_ops.delete_file` 必须用 `SHFileOperationW` 删除到回收站，**绝不物理删除**。
- 重命名 / 移动 / 删除后必须同步 `history`（`rename` / `move_path` / `remove_tree`）。
- 重命名：文件保留扩展名，文件夹不补；非法字符与重名检测。
- Win32 签名必须正确声明（避免 64 位 HGLOBAL / HANDLE / HWND 截断）。

### 4. 自动保存 vs 手动保存
- 自动保存（3s debounce / 60s 保险）只写 Tab 文件，**不得触发聚合追加**。
- 点「保存」（💾）/「同步」（⟳）= 立即保存 Tab 文件 + 追加聚合文件。「保存」隐藏窗口，「同步」保持窗口。
- 退出程序时后台自动保存全部窗口所有页签内容到 Tab 文件；`main.py` 退出前必须调用 `history_store.flush()` 立即落盘。

---

## 六、配置统一管理（禁止硬编码）

- 所有可变路径 / 扩展名 / 隐藏目录 / 布局 / PicGo 地址 / R2 域名 → `config/config.json`。
- 用户偏好（默认保存地址 / 主题选择）→ `%APPDATA%\Obsidian-upload\settings.json`。
- 页面元数据 → `%APPDATA%\Obsidian-upload\pages.json`。
- 工作区 → `workspace.json`；布局 → `layout.json` 或 EXE 旁 config.json 的 `layout_flash`/`layout_inbox`/`layout_log`/`layout_capture` 字段（四个窗口独立）；窗口尺寸 / 位置 → `window_geometry`（`layout_store` 节流写盘）；历史 → `history.json`（磁盘上限 500，默认返回 100，2 秒 debounce 写盘 + flush 立即落盘，RLock 线程安全）。
- 工具勾选与排序 → `%APPDATA%\Obsidian-upload\tools.json`（字段 `pinned` + `pinned_order`）。
- 性能日志 → `%APPDATA%\Obsidian-upload\performance.log`（启动耗时 / 模块加载 / 文件扫描 / 保存耗时，由 `commands/performance.py` 写入）。

### To Do（tools/to-do）同步配置

- To Do 是独立模块（`tools/to-do/`），通过 `lib/modules/todo_window.py` 接入工具箱「✅ To Do」。
- **Microsoft 同步必须配置 `tools/to-do/config.json` 的 `microsoft.client_id`**（Azure 应用注册的应用客户端 ID）。未配置时登录/同步报 `未配置 Microsoft client_id`。
- 配置项：`enabled` / `client_id` / `tenant`（个人账号 `consumers`）/ `scopes`（`Tasks.ReadWrite`、`offline_access`）/ `token_cache_file`。
- 登录链路：UI「Microsoft 登录」= 交互式（系统浏览器 OAuth），失败自动回退设备码流（`ms_device_start` / `ms_device_wait`）；令牌缓存不保存密码。
- 同步：`SyncEngine` 双向同步（拉取 LWW + 推送 upsert/软删除），个人账号下 Graph 可能只返回内置列表（`GET /me/todo/lists` 静默丢弃自建列表）——实测确认，如需支持需额外记录列表注册表。
- **数据目录**：源码运行写入 `tools/to-do/data/`；打包（EXE）运行由 `todo_window._redirect_exe_data_paths` 重定向到 `%APPDATA%\Obsidian-upload\todo\`（`_MEIPASS` 临时目录退出即删，禁止存放数据）。
- **登录状态持久化（警惕陷阱）**：to-do 模块的登录状态保存经过多轮调试才稳定，关键机制如下，修改时务必全部保持：
  1. pywebview 对 `file://` 协议**不注入 JS API**——`todo_window.create()` 和 `to-do/main.py` 中 `url` 必须传文件路径（非 `file:///`），pywebview 会自动启动 HTTP 服务器并注入 `window.pywebview.api`。
  2. 前端 `boot()` 在 API 就绪前执行会静默失败——必须 `window.events.loaded` 回调中 `evaluate_js('boot()')` 强制启动 + 前端 `waitForApi()` 轮询双保险。
  3. 双保险持久化：`token_cache.json`（MSAL 令牌）+ `login_state.json`（显式状态文件），两者缺一不可。`is_logged_in()` 以状态文件为主、MSAL 验证为辅。
  4. `save_cache()` 必须同时写入令牌缓存和登录状态文件。

---

## 七、模块职责清单（精简版）

| 模块 | 职责 |
|------|------|
| `lib/core/main.py` | 入口：四窗口 + 设置 / 工具箱 / 画布窗口 + js_api + 托盘 + 单实例 + 看门狗；**禁止写业务** |
| `lib/core/api.py` | Api / SettingsApi / ToolApi；通过 `_main` 访问 main.py 全局状态；`list_md_files(prefix)` 列出工作区 .md 文件（wikilink 自动补全）；`open_wikilink(filename)` 按文件名精确查找 .md 文件；`paste_html(content)` 解析 HTML 富文本保存图片返回 Obsidian Markdown；`paste_clipboard_image()` 保存剪贴板位图为附件；`get_attachment_data_url(filename)` 读取附件返回 base64 data URL（预览区图片渲染跨域兜底） |
| `lib/core/settings.py` | settings.json 读写 |
| `lib/core/window_manager.py` | 热键调起窗口的强制前台聚焦（AttachThreadInput + 模拟 Alt） |
| `lib/backend/storage.py` | 聚合追加保存（save_note / save_daily_log） |
| `lib/backend/markdown.py` | 聚合格式 / obsidian:// 打开 / 调试日志 |
| `lib/backend/uploader.py` | 剪贴板 → PicGo HTTP API → R2 → Markdown 链接（取 `result[0]`） |
| `lib/backend/clipboard_parser.py` | 剪贴板 HTML 富文本解析（SAX 式遍历，按 DOM 顺序提取 text/image 节点，支持 data-src/data-original 等懒加载属性） |
| `lib/backend/html_converter.py` | 节点列表 → Obsidian Markdown（图片→`![[filename]]` 附件引用，标题→`#` 前缀，列表→`-` 前缀，链接→`[text](url)`） |
| `lib/backend/image_handler.py` | 图片保存到 attachments/ 目录（base64 解码 / 网络 URL 下载 / 剪贴板位图 CF_BITMAP/CF_DIB，命名 `Pasted-image-yyyyMMdd-HHmmss`，重名自动 -001/-002） |
| `lib/backend/capture.py` | Capture 窗口配置（WINDOW_DEF）+ 聚合保存路径（capture_file） |
| `lib/backend/search_engine.py` | 工作区搜索（逐行增量匹配、文件名/内容命中、2MB 以上跳过内容搜索） |
| `lib/modules/pages.py` | pages.json + Tab 独立文件管理（覆盖写 / 重命名 / 启动恢复 / 内存缓存 + 2s debounce 写盘） |
| `lib/modules/theme_manager.py` | settings.json theme 字段读写（window / editor / preview 三组） |
| `lib/modules/layout_store.py` | 布局记忆（四个窗口独立：`layout_flash`/`layout_inbox`/`layout_log`/`layout_capture`，每窗口独立宽度比例/pane_mode/workspace显隐与宽度/explorer_sort）+ 窗口尺寸位置记忆（`window_geometry`，节流写盘） |
| `lib/modules/workspace.py` | workspace.json 增删（路径去重大小写不敏感，RLock 线程安全） |
| `lib/modules/file_tree.py` | 文件树懒加载（scan_dir 直接子项；iter_files 递归；隐藏目录过滤；explorer_exts / search_exts） |
| `lib/modules/file_explorer.py` | 资源管理器编排（薄转发，复用 workspace / file_tree / history / layout_store） |
| `lib/modules/file_ops.py` | 右键后端（剪贴板 / 资源管理器 / VSCode / 重命名 / 复制副本 / 新建 / 移动 / 删除到回收站） |
| `lib/modules/file_assoc.py` | 文件关联打开 + 单实例文件转发（pending 队列消费） |
| `lib/modules/history.py` | 历史记录（record_open / record_edit / query / search / rename / move_path / remove / remove_tree / flush） |
| `lib/modules/favorites.py` | 收藏夹 |
| `lib/modules/canvas_server.py` | 画布本地 HTTP 服务（Drawnix 是 Vite/React 的 ES Module 应用，file:// 会被 CORS 拦截，必须 HTTP 承载 tools/drawnix 产物；127.0.0.1 随机端口，start()/stop()，随程序启停） |
| `lib/modules/todo_window.py` | To Do 窗口编排（复用 tools/to-do 独立模块：懒加载——首次 open_todo 时创建 + show 复用 + 退出销毁，Microsoft 适配器失败降级本地模式；启动不再预创建） |
| `commands/logger.py` | 结构化日志（app.log，持久句柄 + 目录缓存，flush 退出落盘） |
| `commands/performance.py` | 性能监控（mark/measure/log/time_call，写 performance.log） |
| `commands/app_utils.py` | 窗口置顶 / 居中 / 错误弹窗 / pick_folder（ctypes SHBrowseForFolderW，不用 Tkinter） |
| `commands/hotkey_manager.py` | RegisterHotKey 系统级热键 + 看门狗（30秒检测 + 2分钟强制重注册，重注册在热键线程内执行避免 1408） |

> 所有 lib/backend、lib/modules、commands 模块均**不依赖 UI / 网络**，可独立测试。

---

## 八、热键稳定性要求

- 热键：`Alt+E`（Inbox）/ `Alt+S`（FlashNote）/ `Alt+R`（Daily Log）/ `Alt+D`（Capture）。
- 实现：`RegisterHotKey` 系统级热键（非键盘钩子）→ 隐藏消息窗口（独立线程）→ `WM_HOTKEY` 置 `threading.Event`（零阻塞）→ 工作线程消费 → 窗口显示+置顶+聚焦。
- 看门狗：30 秒存活检测 + 2 分钟强制重注册。
- **重注册必须在热键线程内执行**（`WM_APP_REBIND` 消息触发），禁止跨线程直接调用 `RegisterHotKey`/`UnregisterHotKey`（会 1408 错误）。
- 异常日志：`shortcut_error.log`。

---

## 九、关闭标签行为

### Inbox / FlashNote / 日志记录 窗口
- 关闭标签时弹出确认对话框，提供两个按钮：
  - **删除**：不保存内容，直接从页签栏移除
  - **保存**：保存到聚合文件（如 `📦 inbox.md`）后关闭页签

### Capture 窗口
- 保持原有关闭即保存逻辑，无弹窗确认。

---

## 十、打包命令（build.bat 关键参数）

```bash
pyinstaller --noconfirm --clean ^
  --onedir --windowed ^
  --name Obsidian-upload --icon app.ico ^
  --paths . ^
  --upx-dir "C:\Users\leokou\AppData\Local\upx\upx-5.2.0-win64" ^
  --specpath spec ^
  --exclude-module numpy ^
  --exclude-module cryptography ^
  --exclude-module PIL._avif ^
  --hidden-import=pystray ^
  --hidden-import=webview --hidden-import=webview.platforms.edgechromium ^
  --hidden-import=commands --hidden-import=commands.logger ^
  --hidden-import=commands.app_utils --hidden-import=commands.hotkey_manager --hidden-import=commands.performance ^
  --hidden-import=lib --hidden-import=lib.core --hidden-import=lib.backend --hidden-import=lib.modules ^
  --hidden-import=lib.core.api --hidden-import=lib.core.main --hidden-import=lib.core.window_manager --hidden-import=lib.core.settings ^
  --hidden-import=lib.backend.storage --hidden-import=lib.backend.markdown --hidden-import=lib.backend.uploader ^
  --hidden-import=lib.backend.clipboard_parser --hidden-import=lib.backend.html_converter --hidden-import=lib.backend.image_handler ^
  --hidden-import=lib.backend.capture --hidden-import=lib.backend.search_engine ^
  --hidden-import=lib.modules.pages --hidden-import=lib.modules.file_assoc --hidden-import=lib.modules.layout_store ^
  --hidden-import=lib.modules.history --hidden-import=lib.modules.workspace --hidden-import=lib.modules.file_tree ^
  --hidden-import=lib.modules.file_explorer --hidden-import=lib.modules.file_ops ^
  --hidden-import=lib.modules.favorites --hidden-import=lib.modules.theme_manager ^
  --hidden-import=lib.modules.canvas_server --hidden-import=lib.modules.todo_window ^
  --hidden-import=msal ^
  --collect-submodules=pystray ^
  --collect-submodules=lib ^
  --add-data "frontend;frontend" ^
  --add-data "tools\drawnix;tools\drawnix" ^
  --add-data "tools\clean_empty_lines;tools\clean_empty_lines" ^
  --add-data "tools\to-do;tools\to-do" ^
  --add-data "tools\tools.json;tools" ^
  --add-data "config/config.json;config" ^
  --add-data "commands;commands" ^
  --add-data "app.ico;." ^
  lib\core\main.py
```

> **AI 禁止自动执行打包命令**，用户手动运行 `build.bat` 打包。

输出：`dist\Obsidian-upload\Obsidian-upload.exe`（onedir 单文件夹，无控制台；分发整个 dist\Obsidian-upload 文件夹）。
config.json 嵌入 EXE，复制到 EXE 旁可自定义（无需重新打包）。

---

## 十一、AI 修改代码流程

### 修改前分析阶段

任何代码修改前，必须执行：

1. **阅读本 CLAUDE.md**
   - 理解项目架构与模块职责
   - 理解 sys.modules 注册机制
   - 理解 api.py 全局状态管理
   - 理解 pywebview 生命周期陷阱
   - 理解多窗口状态隔离要求

2. **阅读 README.md**
   - 了解项目整体功能
   - 了解运行方式
   - 了解已有功能边界

3. **检查当前代码结构**
   - 确认 `lib/core` / `lib/backend` / `lib/modules` / `frontend` 目录职责
   - **禁止**：根据历史记忆推测代码结构
   - **必须**：读取当前实际文件

4. **定位相关模块**
   - 查找：后端 Python 模块 / 前端 JS 模块 / CSS 模块 / 配置文件 / API 接口
   - 使用项目包路径：`from lib.xxx import yyy`
   - **禁止**：临时添加 `sys.path` 绕过模块结构

5. **分析影响范围**
   - 修改前必须明确影响：后端模块 / API 接口 / 前端 JS 调用 / 配置文件 / 数据结构 / 打包流程
   - 输出修改方案
   - **未经确认，禁止大规模修改**

### 修改策略（按优先级）

**第一优先级：新增独立模块**
- `lib/modules/xxx.py` 或 `lib/backend/xxx.py`
- 要求：单一职责、可独立测试、可插拔、不影响旧模块

**第二优先级：扩展已有模块**
- 要求：保持已有接口、向后兼容、不破坏调用方

**第三优先级：修改核心文件（main.py / api.py）**
- 仅当新功能必须接入且无其他合理方案时允许
- 必须：最小修改、保持全局状态一致、更新相关初始化流程、更新日志

### 代码修改规则

**禁止**：
1. 往旧大文件堆代码（新功能必须独立文件，见「一、最高开发原则」不往旧大文件堆代码；预览区代码见「不随意修改预览区代码」红线，无明确需求禁止改动）
2. 删除已有功能
3. 重写整个模块
4. 修改无关代码
5. 修改公共接口名称
6. 自动执行打包命令

**新增功能必须**：独立文件、明确输入输出、有错误处理、有日志记录

### 前后端联动规则

涉及 Python API 修改时，必须检查：
- API 注册位置（`lib/core/api.py`）
- JS 调用位置（`frontend/js/*.js` 或 `frontend/script.js`）
- 参数格式与返回格式

**修改 API 必须同步前后端**：后端改 `api.py`，前端改对应 `.js`。**禁止只修改一端**。

### 配置修改规则

新增配置必须：
1. 加入配置文件
2. 设置默认值
3. 增加读取逻辑
4. 增加异常处理

涉及 `config.json` / `settings.json` / `pages.json` / `workspace.json` / `history.json` 时，**必须保持兼容旧数据**。

### 修改后验证

每次修改必须验证：

**基础**：
- ✅ 应用启动正常
- ✅ 无 import 错误
- ✅ pywebview 窗口正常创建

**功能**：
- ✅ 四窗口正常（Inbox / FlashNote / Log / Capture）
- ✅ 热键正常（Alt+E/S/R/D）
- ✅ 自动保存正常
- ✅ 图片上传正常
- ✅ 历史记录正常
- ✅ 工作区正常
- ✅ Inbox/FlashNote/Log 关闭标签弹窗正常（保存/删除）
- ✅ Capture 关闭标签保持原有关闭即保存

**日志**：
- ✅ app.log / shortcut_error.log / upload_debug.log

**配置**：
- ✅ config.json / settings.json / pages.json / workspace.json / history.json

**打包**：
- ✅ build.bat 正常（用户手动执行）
- ✅ EXE 正常启动

### 性能要求

新增功能不得：
- 阻塞 UI 线程
- 增加无意义后台线程
- 增加高频轮询

文件扫描必须懒加载；网络请求必须异步或后台执行。

### 失败处理

如果修改失败：
1. 保留错误日志
2. 分析原因
3. 回退最近修改

**禁止**：继续叠加错误代码。

### 最终原则

AI 开发 LeoDiary Capture 必须遵守：小步修改、模块隔离、接口稳定、功能不破坏、代码可维护、长期可扩展。

---

## 十二、性能优化规范

### 1. 启动优化
- 启动延迟已从 1.5s 降到 0.3s（`main.py` show_default）。
- 启动四阶段性能标记：`main_start → config_loaded → windows_created → startup_complete`，写入 `performance.log`。
- **禁止**启动时：扫描整个 workspace / 加载全部历史 / 初始化所有工具插件 / 加载非必要页面。
- **必须**采用懒加载：用户展开目录才读取。

### 2. CSS 懒加载（必须保留）
- 前端**禁止**在 HTML 中预加载全部主题 CSS（原 88+20+20 个 `<link>` 已移除）。
- 主题 CSS 由 `frontend/js/theme-loader.js` 按需加载当前激活主题，切换时移除旧 `<link>`（先加载新再移除旧，避免切换瞬间无样式）。
- `editor.html` / `settings.html` / `tools.html` 均已接入 ThemeLoader。
- 新增窗口必须遵循：HTML 中只保留 `theme.css` + 结构样式，主题 CSS 由 ThemeLoader 动态注入。
- **主题文件生成源（改主题必读）**：`frontend/gen_themes.py` 是编辑器主题 CSS 的唯一数据源（`THEMES` dict 含全部 35 个主题的 `--cm-*` 颜色变量），生成 `themes/editor/*.css`（仅颜色变量，布局/语法由 editor-layout.css + editor-syntax.css 统一管理）。**改主题颜色必须改 gen_themes.py 再运行重新生成，禁止直接改 css 产物**（否则下次生成被覆盖）。深色主题的 `cm-formatting-color` 已调亮为可见值（如 github-dark `#8B949E`、neon-cyber `#00B32E`）。输出路径固定为 `frontend/themes/editor`（勿改成带空格的旧路径）。
- **编辑器语法高亮**：`script.js` 用 `HighlightStyle.define`（`window.CodeMirrorBundle.HighlightStyle/tags`，已在 `vendor/cm6.min.js` 补挂载导出）定义 `themeHighlightStyle`，把语法 tag 映射到 `--cm-*` 主题变量，注册在 `syntaxHighlighting(defaultHighlightStyle, {fallback:true})` 之后。原因：CM6 默认 `defaultHighlightStyle` 标记色（meta `#404740` 等）是浅色主题配色，深色主题下不可见；且 CM6 生成 `ͼxx` 哈希类名，`editor-syntax.css` 的 `.cm-formatting`/`.cm-heading` 等语义类选择器不匹配、不生效（死规则，保留无害）。**注意**：CM6 markdown 把 `# - * 1. > \`` 等标记标为 `meta` tag；`tags.list` 会命中段落正文，禁止染色；后注册 style 按 tag 粒度整体接管同 tag 规则（含 fontStyle/fontWeight），自定义规则须补齐样式属性；改 `vendor/cm6.min.js` 须保留 `HighlightStyle:Gi,tags:p` 导出。

### 3. 内存缓存 + 延迟写盘（pages.py 模式）
- `pages.json` 已实现内存缓存 `_db`：首次访问加载，后续 `load_pages` / `find_page` 零磁盘 IO。
- `update_page` 采用 2 秒 debounce 延迟写盘，合并频繁元数据更新。
- `add_page` / `remove_page` **立即落盘**（页面数量变化是关键操作，不允许丢失）。
- `flush()`：程序退出时立即落盘（`main.py` exit_app 必须调用）。
- 新增持久化模块遵循此模式：内存缓存 + debounce 写盘 + 关键操作立即落盘 + flush 退出保底。

### 4. 日志 I/O 优化
- `commands/logger.py` 已用持久文件句柄 `_fh`（append 模式）+ 目录检查缓存 `_dir_ensured`。
- 消除每次写入的 open/close/makedirs 系统调用开销。
- 写后 flush 保证崩溃安全；句柄失效自动重置重试。
- `flush()`：程序退出时刷新缓冲区并关闭句柄。

### 5. 前端轮询与自动保存优化
- pending 文件由前端 `pollPendingFiles()` 每 2 秒轮询 `get_pending_files()` 消费，**仅 capture 窗口返回文件**；后端 watcher 只负责检测到文件时调起 Capture 窗口（避免 evaluate_js 广播）。
- 自动保存（`storage.js`）已加内容跟踪：内容未变更时跳过保险性保存，减少 CPU/IO。
- 光标同步保存：编辑区↔预览区焦点切换时，若当前 Tab 有未保存内容立即落盘（跳过 3s debounce），避免切换时丢数据；外部文件同样适用。

### 6. 性能监控模块（commands/performance.py）
- API：`mark(name)` / `measure(start, end, category)` / `log(category, name, ms)` / `time_call(func, ...)` / `reset()`。
- 日志文件：`%APPDATA%/Obsidian-upload/performance.log`。
- 使用 `time.perf_counter()` 高精度计时。
- 标记缺失时静默跳过（不抛异常）。
- 新增长耗时操作必须埋点：启动 / 文件扫描 / 保存 / 上传。

### 7. 性能约束（新增功能必须遵守）
- **禁止**阻塞 UI 线程。
- **禁止**增加无意义后台线程。
- **禁止**高频轮询（`while True` 无 sleep）。
- **禁止**启动递归扫描 workspace。
- **必须**：文件扫描懒加载 / 网络请求异步或后台 / 频繁写盘用 debounce。
- **必须**：长时间运行不泄漏（句柄 / 缓存有释放路径）。

---

## 十三、编辑区与预览区联动机制

### 1. 跨区行高亮（黄色高亮）

- 编辑区和预览区同时高亮光标所在行，编辑器用 `.cm-crossHighlightLine`（黄色背景），预览区用 `.cross-highlight`。
- 高亮触发时机：
  - 编辑器：方向键（keyup）、鼠标点击（mouseup/click）、聚焦（focus）
  - 预览区：方向键（keyup）、鼠标点击（mouseup）
- 编辑区高亮必须用 `view.domAtPos(pos)` 定位 `.cm-line` 元素，**禁止**用 `querySelectorAll(".cm-line")[n]`（CodeMirror 6 虚拟化渲染，视口外的行不在 DOM 中，索引会越界）。

### 2. 光标驱动的双向滚动同步

- 编辑器光标移动 → 预览区滚动到对应行
- 预览区光标移动 → 编辑器滚动到对应行
- 同步策略：**相对位置同步**（非固定偏移），使光标所在行在对侧视口中出现在**相同**的相对高度。

关键函数：
| 函数 | 用途 |
|------|------|
| `_getEditorCursorRatio()` | 获取编辑器光标行在视口中的相对位置（0=顶部, 1=底部） |
| `_getPreviewBlockRatio(block)` | 获取预览区块在视口中的相对位置 |
| `scrollPreviewToLine(line, ratio)` | 预览区滚动到指定行，`ratio` 控制目标行在视口位置 |
| `scrollEditorToLine(line, ratio)` | 编辑器滚动到指定行，`ratio` 控制目标行在视口位置 |
| `_highlightLine(lineNum, scrollTarget)` | 高亮两侧 + 滚动同步（`scrollTarget: 'preview'['editor'`） |

### 3. 防循环机制

- `_cursorSyncActive` 标志：光标驱动的滚动同步期间置 `true`，200ms 后释放，防止 scroll 事件反向触发造成循环。
- 滚动条拖拽走的原有滚动同步（`syncing` 标志 + `syncing` 变量），与光标驱动同步互斥。

### 3.1 光标跟随滚动（cursorFollowPlugin）

- 位置：`frontend/script.js` 的 `editorExtensions` + `_ensureEditorCursorVisible()`。
- 背景（实测确认）：CM6 内置光标滚动在编辑器**无焦点**事务（预览区编辑同步、工具栏插入、粘贴上传等）下完全不生效；`scrollIntoView`/`scrollHeight` 在新增行未布局时（rAF 阶段浏览器布局未更新）会按旧值 clamp，滚动距离不足。
- 机制：doc/selection 变化且选区为空 → rAF 阶段用 `view.lineBlockAt(head)` 检查光标行是否离开视口（顶部 10px / 底部 40px 边距）→ **直接设置 `scrollDOM.scrollTop`（不做手动 clamp，浏览器自动兜底）** → 下一帧复测（布局已完成）若仍越界再补滚。
- 跳过场景：编辑区隐藏（clientHeight=0）、非空选区（拖选交给 CM6 内置）。
- 验证：`test/cursor-follow-test.html`（Edge headless）——无焦点事务下内置 scrollTop 保持 0，插件滚动到位且光标行完整可见。
- 预览区（contenteditable）同侧保障：`_scrollPreviewCursorIntoView()` 在 `_doPreviewEnter`（回车）、`_placeCursorAtDocEnd`、图片插入预览区后调用，光标所在块越界时滚动预览区。

### 4. 预览区编辑同步

- 预览区 `contenteditable="true"`，用户可在预览区直接编辑。
- 编辑内容通过 `_syncPreviewToEditor()` 同步回编辑器，核心逻辑：保存旧块纯文本 → 计算 diff → 映射到 markdown 源码位置 → 插入/删除对应字符。
- `_previewEditing` 标志防止循环同步，`_skipPreviewRerender` 用于 Enter 等操作时跳过预览重新渲染。
- **编辑前基准必须在 `beforeinput` 捕获**（DOM 变更前，`innerText` 是编辑前文本）；若在 `input` 里保存，`innerText` 已是编辑后文本 → 首次编辑 diff 恒 null 不同步，后续删除/输入位置错位（曾导致"删除键跳过最后一个字删前面的字"）。
- **光标恢复 clamp 陷阱**：`_restorePreviewCursor` 中 `Math.min(remaining, len - 1)` 会把光标从文本末尾挪到倒数第二个字符后，下次 Backspace 删错字——必须用 `Math.min(remaining, len)`。
- 验证：`test/preview-delete-test.html`（Edge headless）——修复前首次删除 diff null 不同步、光标被 clamp 到 len-1；修复后删除/输入正确、光标落位末尾。

### 5. 预览区图片粘贴上传

- 预览区图片粘贴通过 `document` 的 `paste` 捕获处理器（`capture: true`）统一处理。
- 检测焦点/选区是否在预览区内：`_isFocusInPreview()` 遍历 `anchorNode` 的父节点链直到 `previewEl`。
- 图片上传流程：`uploadAndInsert()` →
  - 焦点在编辑器 → 保持原行为，插入到编辑器光标位置
  - 焦点在预览区 → `_insertImageToPreview(res)`：在光标所在 block 的 markdown 末尾插入 `\n\n![alt](url)\n`，重渲染预览区，光标放到图片所在块末尾，重置 `_oldBlock` 状态
- **预览区文本粘贴**：由同上 paste 处理器拦截，用 `clipboardData.getData("text/plain")` 插入纯文本（`_insertPlainTextToPreview`），阻止浏览器插入 HTML 格式污染 contenteditable。
- 预览区 keydown 处理器**不拦截 Ctrl+V**（`preventDefault` 会阻止 paste 事件触发），让 paste 事件正常传播到 document 捕获处理器。
- 预览区右键菜单「粘贴」沿用 `navigator.clipboard.readText()` 回退方案（paste 事件无法从右键菜单获取）。

### 6. 预览区 Enter 键处理

- 预览区 Enter 由 `_doPreviewEnter(isSoftEnter)` 处理：
  - 获取光标所在 block 的 data-line → 计算块在 markdown 中的范围 → 用 `_mapPlainToMd` 将纯文本偏移映射为 markdown 位置 → 在 markdown 中插入 `\n`（硬换行）或 `  \n`（软换行）
  - **硬换行时删除光标前的尾部空格**：与 marked `breaks: true` 行为一致，保证 markdown 与 innerText 字符位置对应，避免后续 diff 同步错位
  - **不重新渲染预览区**：直接在 DOM 光标位置插入 `<br>`，光标放到 `<br>` 之后（若重新渲染，marked 将 `\n` 渲染为同一段落内的 `<br>`，data-line 不变，`_placeCursorAtLineStart` 找不到下一个块，光标会跑到段落开头）
  - 更新 `_oldBlock` 基准状态，让后续输入能通过 diff 精确同步

### 7. 已知陷阱

- **预览区→编辑器方向**：编辑器行可能不在视口内（CodeMirror 虚拟化），必须先 `scrollEditorToLine` 使目标行进入视口，再等双重 `requestAnimationFrame` 等待 CodeMirror 渲染完成后，才能用 `_findEditorLineEl` 定位并加高亮类。
- **编辑器高亮定位**：`_findEditorLineEl` 用 `view.domAtPos(pos)` 定位，得到的可能是文本节点，需向上遍历找 `.cm-line` 元素。
- **`_highlightLine` 取消 `if (lineNum !== _lastHighlightedLine)` 跳过**：跨区切换时，同一行号需要重新执行高亮+滚动（因为 scrollTarget 不同）。
- **`_clearCrossHighlight` 必须先清再设**：不允许先给新行加高亮再清旧的，否则同一行号会短暂消失。
- **预览区图片粘贴必须通过捕获阶段**：`document.addEventListener("paste", ..., true)` 必须在捕获阶段拦截，否则 `previewEl` 的 keydown 或 contenteditable 默认行为可能先消化事件导致图片丢失。
- **预览区粘贴纯文本**：`navigator.clipboard.readText()` 在 pywebview 环境中不可靠，必须用 `e.clipboardData.getData("text/plain")` 直接读取。
- **预览区 Enter 不重新渲染**：标记 `_skipPreviewRerender = true` 阻止 updateListener 中的 `renderPreview()` 回调，避免 marked 重新解析导致 data-line 错位。

### 8. data-line 行号锚点与嵌套块禁则

**机制**：预览区通过自定义 `marked.use({ renderer })` 给块级元素（h1-h6 / p / blockquote / pre / hr / ul / ol / li / table）注入 `data-line` 属性，值由 `_lineOf(raw)` 通过 `_renderDoc.indexOf(raw, _renderPos)` 查找 raw 文本在原文中的行号（1 起）。

**核心陷阱 — 嵌套块 data-line="0"**：
- marked.js 将 `li` / `blockquote` 内的内容包裹为 paragraph token，触发 `paragraph` 渲染器嵌套调用 `_lineOf(para_raw)`
- 此时 `_renderPos` 已被父块（list/blockquote）的 `_lineOf` 推进到父块之后，嵌套块的 raw 文本位于 `_renderPos` **之前** → `indexOf` 返回 -1 → `_lineOf` 返回 0
- 产生的 `<p data-line="0">` 假锚点会拦截 `_findCursorBlock()` 向上遍历，导致点击列表项时返回 paragraph 而非 `<li>`，高亮错位

**修复规则（2026-08-05）**：
1. `_lineOf()`：raw 不可见时返回 `0`（原返回 `_renderDoc.slice(0, _renderPos).split("\n").length`，产生错误的正数行号）
2. 所有可能嵌套的渲染器（paragraph / blockquote / code / table）：`line > 0` 时才输出 `data-line`，否则不输出
3. `_findCursorBlock()` 防御性跳过 `parseInt(data-line) > 0` 不成立的元素
4. `_highlightLine()` 防御性 `if (lineNum <= 0) return`

**验证**：`node -e` 模拟渲染确认无 `data-line="0"`；`test/highlight-bug-test.html` 浏览器手动验证。

---

## 十四、Obsidian Wikilink 双链支持

### 1. 编辑器高亮（ViewPlugin）

- 文件：`frontend/script.js` 的 `wikilinkPlugin`（ViewPlugin）
- 扫描编辑器可见区域，给 `[[filename]]` / `[[filename|display]]` 加 `.cm-wikilink` 样式（紫色文字 + 浅紫背景）
- 未闭合的 `[[filename`（输入中）加 `.cm-wikilink-unfinished` 样式（浅黄背景 + 黄色虚线下划线）
- 依赖：`cm6.min.js` 导出的 `ViewPlugin`/`Decoration`（已手动添加 `window.CodeMirrorBundle`）

### 2. 自动补全（`[[` 触发）

- 文件：`frontend/script.js` 的 `wikilinkCompletionSource`（异步补全源）
- 检测到 `[[` 前缀时调用 `pywebview.api.list_md_files(prefix)` 获取候选 .md 文件列表
- 选中后自定义 `apply` 函数：检测光标后是否已有 `]]`（避免 `closeBrackets` 重复闭合）
- 注册方式：`autocompletion({ override: [wikilinkCompletionSource] })`
- 补全 keymap 必须在 `defaultKeymap` 之前注册（否则 Enter/Arrow 被默认快捷键拦截）

### 3. 预览区点击打开

- 文件：`frontend/script.js` 的 `_processWikilinks()` / `_openWikilinkTab(filename)`
- 解析 `[[filename]]` 和 `[[filename|display]]` 为 `<a class="wikilink">` 链接
- 点击时调用 `pywebview.api.open_wikilink(filename)`：
  - 精确匹配文件名（大小写不敏感）→ 读取文件内容在新页签打开
  - 未找到 → 在 `A📥 收集（Capture）` 目录新建空 .md 文件并打开

### 4. 资源管理器右键「复制双链」

- 文件：`frontend/js/workspace.js` 的 `showFileContextMenu()`
- 菜单项「复制双链」在「收藏」下方，复制内容 `[[文件名]]`（调用 `fileBase(path)` 自动去 `.md` 后缀）

### 5. 后端 API

- `api.py` → `list_md_files(prefix="", limit=50)`：遍历工作区文件夹，返回匹配前缀的 .md 文件名列表（跳过 `.obsidian`/`.git`/`node_modules` 等隐藏目录）
- `api.py` → `open_wikilink(filename)`：按文件名精确搜索工作区 .md 文件，返回 `{content, title, path, exists}`；未找到时在 Capture 目录新建文件，返回 `{content:"", title, path, exists:False, created:True}`

> 编辑器与预览区的 wikilink 样式统一在 `frontend/style.css` 中定义。

---

## 十五、剪贴板富文本粘贴（网页复制 → Obsidian Markdown）

### 1. 整体流程

```
浏览器 Ctrl+C → 剪贴板含 text/html + text/plain
  ↓
前端 paste 事件捕获（document.capture 阶段）
  ↓
检测 clipboardData.types 包含 text/html
  ↓
e.preventDefault() + pywebview.api.paste_html(html)
  ↓
Python 后端：clipboard_parser 解析 → image_handler 保存图片 → html_converter 转 Markdown
  ↓
返回 {ok, markdown, imageCount}
  ↓
前端 _insertPasteText() 插入编辑器/预览区光标处
```

### 2. 前端 paste 优先级

`frontend/script.js` 的 `document.addEventListener("paste", ..., true)` 捕获阶段拦截：

1. **text/html 富文本**（网页复制）→ `pasteHtmlContent()` → 后端 `paste_html` → 保存图片返回 Obsidian Markdown
2. **图片文件/剪贴板位图**（截图）→ `pasteClipboardImage()` → 后端 `paste_clipboard_image` → 保存附件 → 失败回退 PicGo 上传
3. **预览区文本粘贴** → 插入纯文本（避免 HTML 污染 contenteditable）
4. **编辑器文本粘贴** → 放行给 CodeMirror 原生处理

### 3. 后端 API

| API | 参数 | 返回 | 说明 |
|-----|------|------|------|
| `paste_html(content)` | HTML 字符串 | `{ok, markdown, imageCount, msg}` | 解析 HTML 保存图片，返回 Obsidian Markdown；图片失败不影响文字 |
| `paste_clipboard_image()` | 无 | `{ok, markdown, msg}` | Pillow ImageGrab 保存剪贴板截图 |
| `get_attachment_data_url(filename)` | 文件名 | `{ok, dataUrl}` | 读取附件返回 base64 data URL（预览区图片渲染跨域兜底） |

### 4. 图片保存规则

- 目录：`{default_save_path}/attachments/`（或 config.json 的 `attachments_dir`）
- 命名：`Pasted-image-yyyyMMdd-HHmmss.png`，重名自动 `-001`、`-002`
- 图片来源分派：
  - `data:image/...;base64,...` → 解码保存（情况 A）
  - `http(s)://...` → requests 下载保存（情况 B）
  - `blob:` → 无法下载，跳过（浏览器内部引用）
  - `CF_BITMAP/CF_DIB` → Pillow 保存（情况 C）
- 失败降级：图片保存失败不影响文字粘贴

### 5. 预览区 ![[image]] 渲染

- `_processImageEmbeds()` 在 `renderPreview()` 中被调用（在 wikilink 处理之前，避免 `![[x]]` 被 `[[x]]` 误匹配）
- 首次加载通过 `get_attachment_data_url` 异步获取 base64 data URL（缓存到 `_embedImgCache`）
- 图片加载完成前透明度 0.3，加载后恢复原值，过渡动画 0.2s
- **图片放大预览**：`_setupImageZoom()` 在 `renderPreview()` 末尾执行，将预览区所有 `<img>`（本地附件 `![[...]]` 与 PicGo 远程图 `![alt](url)` 统一处理）包入 `.img-zoom-wrap` 并挂放大镜按钮；hover 显示、点击打开 `.img-lightbox` 遮罩（点击背景 / ✕ / Esc 关闭）。按钮用内联 SVG（无文本节点），避免污染预览区 `innerText` 的 diff 同步。

### 6. 模块依赖

```
clipboard_parser.py（无依赖，纯标准库 html.parser）
  ↓
html_converter.py（无依赖，只做字符串拼接）
  ↓
image_handler.py（依赖 PIL / requests）
  ↓
api.py（编排三个模块，暴露给前端）
```

> 所有模块均不依赖 UI，可独立测试。测试用例覆盖：网页复制、多图片顺序、base64 图片、纯文本回退、blob URL 跳过、混合失败降级。

---

## 十六、资源管理区文件多选与批量操作

### 1. 多选状态管理

- 文件：`frontend/explorer.js`
- 状态变量：
  - `selectedPaths`（`Map<norm(path), rawPath>`）— 当前选中的文件路径集合
  - `_lastClickedPath` — 最近一次点击的文件路径（Shift 范围选择锚点 + Ctrl 首次点击回溯）
- 暴露方法：`getSelected()` 返回路径数组、`clearSelected()` 清空多选

### 2. Ctrl+Click 多选

- `click` 事件中检测 `e.ctrlKey || e.metaKey`
- **关键逻辑**：如果 `selectedPaths` 为空但 `_lastClickedPath` 存在（之前普通点击打开过文件），先把 `_lastClickedPath` 加入多选，再 toggle 当前文件。确保 Ctrl 开始多选时第一个点过的文件也被包含。
- 不打开文件，只切换选中状态

### 3. Shift+Click 范围选择

- 无锚点（`_lastClickedPath` 为 null）时，选中当前文件作为锚点
- 有锚点时，在同一个父目录下计算锚点与当前点击之间的范围，选中范围内所有文件
- 不打开文件，只选中范围

### 4. 右键菜单多选模式

- `contextmenu` 事件中调用 `getSelected()` 获取多选路径列表
- 多选模式（`paths.length > 1`）：
  - **不调用 `setActive()`**（`setActive` 内部会 `clearSelected()` 清空多选）
  - 直接传递 `paths` 给 `onFileContext` 回调
- 单文件模式：走原有逻辑，`clearSelected()` → `setActive()`

### 5. 工作区右键菜单路由

- 文件：`frontend/js/workspace.js` → `showFileContextMenu(path, x, y, paths)`
- 多选模式（`paths && paths.length > 1`）：
  - 只显示两个菜单项：「批量移动（N 个文件）」和「批量删除（N 个文件）」
  - 批量删除带 `danger: true` 标记
- 单文件模式：显示完整菜单（收藏、复制双链、资源管理器、VSCode、重命名等）
- **关键陷阱**：`onFileContext` 回调必须传递第4个参数 `paths`，否则 `showFileContextMenu` 始终走单文件模式

### 6. 批量后端操作

- 文件：`lib/modules/file_ops.py`
- `batch_delete(paths)`：循环调用 `delete_file`，逐个移到回收站，统计成功数
- `batch_move(paths, dest_dir)`：循环调用 `move_item`，逐个移动到目标目录，统计成功数
- 返回 `(ok, msg, count)`

### 7. 前端批量删除实现

- 文件：`frontend/js/workspace.js` → `batchDeleteFile(paths)`
- 显示确认对话框 → 循环调用 `pywebview.api.explorer_delete(path)` 逐个删除 → 刷新所有被删文件所在父目录 → 刷新历史 → 清空多选
- 不依赖 `explorer_batch_delete`（pywebview 参数传递可能有问题），改为逐个调用已知可用的 `explorer_delete`

### 8. 前端批量移动实现

- 文件：`frontend/js/workspace.js` → `batchMoveFile(paths)`
- 弹出目标目录选择对话框 → 调用 `pywebview.api.explorer_batch_move(paths, destDir)` → 刷新所有源目录和目标目录 → 刷新历史 → 清空多选

### 9. 多选样式

- 文件：`frontend/explorer.css`
- `.exp-row.exp-selected`：紫色半透明背景 + 紫色轮廓边框
- 通过 `updateSelectedUI()` 统一更新：先清除所有 `.exp-selected` 类，再根据 `selectedPaths` 重新添加

### 10. 已知陷阱

- **`click` 事件 `e.button` 检查**：`click` 事件处理函数开头必须加 `if (e.button !== 0) return;`，避免右键/中键触发 `click` 导致多选状态被意外修改
- **`e.preventDefault()`**：Ctrl/Shift 分支必须调用 `e.preventDefault()`，阻止浏览器默认行为（文本选中、链接打开等）干扰多选
- **路径标准化**：`selectedPaths` 用 `Map<norm(path), rawPath>` 存储，norm 函数做大小写不敏感标准化。右键检查时 `selectedPaths.has(norm(item.path))` 匹配，`getSelected()` 返回原始路径数组
- **右键回调参数传递**：`Explorer.init` 的 `onFileContext` 回调签名必须是 `(path, x, y, paths)` 四个参数，缺少第4个参数会导致多选模式永远无法触发
- **`_lastClickedPath` 回溯**：Ctrl 首次点击时 `selectedPaths` 为空，需要把 `_lastClickedPath`（之前普通点击的锚点）加入多选，否则之前点过的文件不会出现在批量操作中

> 本规范为强制性执行标准。所有 AI 辅助开发必须严格遵守。如有特殊需求，需与团队评审并修改本规范。

---

## 十七、Markdown 工具栏（编辑区 + 预览区）

### 1. 文件与职责

| 文件 | 职责 |
|------|------|
| `frontend/toolbar/toolbar_config.json` | 按钮定义（fetch 加载，失败回退 FALLBACK_CONFIG）。**改按钮必须同步 FALLBACK_CONFIG** |
| `frontend/toolbar/toolbar.js` | 渲染工具栏、颜色按钮（label + 透明 input[type=color]）、pointerdown 捕获预览选区、`EDIT_COMMANDS` 集合、命令分发 |
| `frontend/toolbar/commands.js` | 命令实现（纯逻辑，不依赖 DOM，可独立测试） |
| `frontend/toolbar/toolbar.css` | 按钮 / 分隔线 / 颜色取色器样式 |

宿主能力由 `script.js` 在 `Toolbar.init(ctx)` 注入：`getView` / `copyMarkdown` / `revealFile` / `toast` / `capturePreviewRange` / `applyPreviewRangeToEditor` / `openZoomDialog` / `savePreviewToolbarOrder`（预览区拖拽排序后落盘）。工具栏本模块不直接依赖全局函数。

### 2. 按钮布局（当前唯一事实源：toolbar_config.json）

- **编辑区（16 按钮，3 分隔线）**，顺序固定：
  1. 文字样式组：`B` 加粗 → `I` 斜体 → `U` 下划线 → `S` 删除线
  2. `H1` `H2` `H3` `H4` 标题
  3. `1.` 有序列表 → `•` 无序列表 → `☑` 任务列表 → 引用（内联 SVG 引号图标）→ 代码块（内联 SVG `</>` 图标）→ `🖍️` 荧光笔高亮 → `A` 文字颜色 → `A` 底色（颜色/底色是 label + 透明取色器）
- **预览区（7 按钮，1 分隔线）**：`📖` 阅读模式 → `📋` 复制 → `📂` 定位文件 ｜ `🔗` 链接 → `🖼️` 图片 → `⛓️` 双链 → `缩放`（同心方框 SVG 图标，仅此处有显示缩放按钮）
- **显示缩放弹窗**：点预览区「缩放」打开 `modal-overlay` 弹窗（复用 `:root` 主题变量，自动适配当前窗体主题），双滑块分别设置编辑区/预览区比例（50%–300%，默认 100%），拖动实时预览；「保存」写入 `settings.json` 的 `zoom` 字段（重启保持），「取消」回滚到上次保存值。链路：`frontend/toolbar/commands.js` 的 `zoom` 命令 → `script.js` 的 `openZoomDialog()` / `applyZoom()`；后端 `lib/core/api.py` 的 `save_zoom` / `lib/core/settings.py` 的 `get_zoom` / `save_zoom`。
- **预览区工具栏可拖拽自定义顺序**：按钮 `draggable`，拖拽实时换位，`dragend` 时把当前 DOM 顺序（含按钮 id 与分隔线占位 `__sep__N`）经 `ctx.savePreviewToolbarOrder` → `pywebview.api.save_preview_toolbar_order` 写入 `settings.json` 的 `preview_toolbar_order`；启动时 `script.js` 读 `CFG.previewToolbarOrder` 调 `Toolbar.setPreviewOrder` 应用（工具栏异步构建前调用也安全，构建时按 `_previewOrder` 重排）。分隔线随按钮一起参与排序。编辑区工具栏顺序仍由配置固定，不可拖拽。
  - **两侧缩放机制不同，勿统一**：编辑区改 `.cm-scroller` 的 `font-size`（基准 13px × 比例）并 `view.requestMeasure()`，**不能用 CSS zoom** —— CM6 内部混用 `scrollTop/clientHeight`（局部像素）与 `getBoundingClientRect`（视口像素），加 zoom 会让两套坐标差一个缩放因子，破坏虚拟滚动与光标定位。预览区因 `h1~h6` 等为固定 px，只能用 CSS `zoom` 作用于 `#preview` 自身；`#preview` 仍是滚动容器，`offsetTop / scrollTop / clientHeight` 同属局部坐标系不受影响，唯一混用 rect 的 `_scrollPreviewCursorIntoView()` 已按 `_previewZoom` 除以缩放比补偿（100% 时 z=1，行为与改动前完全一致）。
- **已移除**：`📑` 目录、`⟳` 刷新预览（按钮已从配置删除；`previewCommands` 中 `toggleToc`/`refresh` 处理器保留但不可达，勿恢复按钮）。
- **按钮顺序即配置顺序**：想交换/对调按钮只需改 `toolbar_config.json`（并同步 FALLBACK_CONFIG），无需改 JS。**编辑区顺序固定由配置决定**；**预览区顺序用户拖拽后会覆盖配置**，持久化在 `preview_toolbar_order`（见上）。
- **SVG 图标**：引用/代码块用内联 `<svg>`（`fill="currentColor"`，自动跟随按钮文字颜色）。配置 icon 以 `<svg` 开头时 `toolbar.js` 用 `innerHTML` 渲染，否则 `textContent`；按钮加 `class: "md-tb-svg"`（toolbar.css 负责 flex 居中）。

### 3. 命令语义（commands.js）

- **包裹 toggle**：`wrapToggle(view, before, after)` —— 选区首尾已等长包裹则取消，否则包裹；无选区时插入占位、光标居中。下划线 `<u>`、删除线 `~~`、高亮 `<mark>`、颜色/底色 `<span style>` 均走此逻辑（`spanWrap`）。
- **标题**：`heading(args=1..6)`，同级别再点取消、跨级切换。
- **有序列表** `orderedList`：覆盖行正则 `/^\d+\.\s+/` 全命中则去除编号，否则加 `1. ` 前缀（渲染器自动编号）。
- **行前缀**（`list` / `quote` / `taskList` / `orderedList`）：空行跳过；全命中才移除。
- **链接/图片/双链**：`[文本](链接)`（选中 url 占位）、`![[文件名]]`、`[[文件名]]`（选中名称占位便于直接改名）。**注意 image/wikilink 输出 Obsidian 嵌入语法，非 `![]()`**。
- **任务列表预览渲染陷阱**：`script.js` 的自定义 `marked.use({renderer:{list}})` 会覆盖 marked 默认的 GFM task checkbox 渲染。list 渲染器内**必须**保留 `item.task` 分支：`itemBody += '<input type="checkbox" disabled' + (item.checked ? ' checked' : '') + ' class="md-task-checkbox"> ';`，否则 `- [ ]` 在预览区不显示勾选框。
- **任务列表一行显示（关键）**：marked 的 `Parser.parse(tokens, t)` 第二参数为 `true` 时会把 `text` token 包成 `<p>`（这是该版本 Parser 内部 `case "text"` 行为）。默认 `listitem` 渲染器调用的是 `this.parser.parse(item.tokens, item.loose)`，而自定义 list 渲染器若漏传第二参数，checkbox 与文本会变两行。**必须**写 `itemBody += this.parser.parse(item.tokens, item.loose);`。
- **快捷键**：`Ctrl+B` / `Ctrl+I` / `Ctrl+U` = 加粗/斜体/下划线（tooltip 已标注）。keymap 在 `defaultKeymap` 之前注册 `Mod-b/Mod-i/Mod-u` → `ToolbarCommands.execute(...)`；预览区 keydown（Ctrl+Z/Y 同一 handler）对 Ctrl+B/I/U 先 `_capturePreviewRange()` → `_applyPreviewRangeToEditor()` 再执行，防 contenteditable 原生格式化。
- **格式按钮 active 状态**：光标所在格式实时高亮按钮（含颜色/底色按钮的色条与取色器值同步）。`commands.js` 的纯函数 `getActiveState(view)`（形参为 `{state}`，取 `view.state.selection.main.head` + `view.state.doc`）检测：行内包裹用 `before.lastIndexOf(open)>=0 && after.indexOf(close)>=0`；斜体用 `findLoneStar` 跳过相邻星号区分 `*i*`/`**b**`；`codeBlock` 检测当前行 ` ``` ` 或前方围栏计数，代码块内抑制其他格式；颜色/底色提取 hex（`/color:\s*(#[0-9a-fA-F]{3,8})/`）。`toolbar.js` 的 `updateActiveState(view)` 映射按钮 `.active`（taskList→id `task`、heading 按 data-args、ol 对应 orderedList），颜色 active 时同步 `.md-tb-color-bar` 与 `input[type=color].value`；`script.js` updateListener 在 `selectionSet||docChanged` 分支调用。

### 4. 预览选区 → 编辑器映射（关键机制）

- 编辑命令（`EDIT_COMMANDS`）在预览区选中后点击工具栏按钮，会先把预览选区映射为编辑器选区再执行。
- `toolbar.js` 工具栏 `pointerdown`（先于 click 触发）调用 `ctx.capturePreviewRange()` 缓存 `_pendingPreviewRange`；`executeCommand` 命中 `EDIT_COMMANDS` 且存在缓存时先 `ctx.applyPreviewRangeToEditor(range)` 再执行，执行后清空。
- `EDIT_COMMANDS` **必须包含 link/image/wikilink**——它们虽在预览工具栏，仍是修改 Markdown 的编辑命令，否则预览选区不会被映射。
- 颜色按钮由 `input[type=color]` 的 `change` 事件驱动，普通 click 被 `md-toolbar-color` 检查跳过，避免空白点击触发空包裹。

### 5. 在资源管理器中定位当前文件（revealFile）

- 入口：预览工具栏 `📂` → `ctx.revealFile()` → `script.js` 的 `syncExplorerWithTab()` → `Explorer.reveal(tab.extPath || tab.file)`。
- **历史 Bug（已修复）**：`restoreTab()`（启动恢复 Tab）曾不设置 `tab.file`，导致恢复的页签点「定位」无任何反应。**新建/恢复/外部 Tab 都必须带文件路径**：`addTab` 异步设置 `tab.file`、`restoreTab` 设置 `tab.file = page.file`、`addExternalTab` 设置 `tab.extPath`。
- `Explorer.reveal` 仅在工作区文件夹内的路径生效（`relativeSegments` 逐层 `expandTo` 懒加载 + `setActive` 高亮）；路径不在工作区时静默返回，不影响当前高亮。
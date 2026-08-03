# LeoDiary Capture 项目开发规范

项目名称：LeoDiary Capture（Obsidian-upload - web）
技术栈：Python + HTML/CSS/JS + Edge WebView2（pywebview 6.x）+ CodeMirror 6 + marked.js
打包：PyInstaller 单文件 EXE

> 本文档仅记录项目特定约束与陷阱。通用编程原则（错误处理、日志、测试、Git 规范等）AI 本身已掌握，不再赘述。功能介绍详见 README.md。

---

## 一、最高开发原则（AI 禁止行为红线）

- **不删除已有功能**：即使认为「无用」「冗余」，删除前必须确认。
- **不修改未知影响范围的公共接口**：js_api 暴露给前端 JS 的方法签名不得改名/改参。
- **不大范围重构**：为小需求不修改大量无关代码、不重写历史模块。
- **不堆积 main.py**：业务逻辑必须落到 lib/backend 或 lib/modules，main.py 只做编排。
- **不改变技术栈**：禁止用 Tkinter / PyQt / AutoHotkey 替代 Web UI；旧入口 `Obsidian-upload.py`（Tkinter）已删除，禁止恢复。
- **不随意修改 to-do 模块**：`tools/to-do/` 是独立子模块，无用户明确指令**禁止修改**其中任何文件（auth / api / sync / ui 等）。该模块登录状态持久化机制经过多轮调试才稳定，改动极易引入回归。**尤其警惕"保存"相关逻辑**（`token_cache.json` / `login_state.json` / `save_cache()` / `is_logged_in()`），这是多轮调试才稳定的核心机制，任何改动都可能导致「每次重启都要重新登录」的回归。
- **新增功能原则**：独立模块 / 可插拔 / 低耦合 / 复用已有能力 / 不依赖 UI 与网络（便于独立测试）。

---

## 二、项目目录结构（重构后）

```
Obsidian-upload - web/
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
│       ├── canvas_server.py 画布本地 HTTP 服务（Drawnix ES Module 需 HTTP 加载，127.0.0.1 随机端口，随启动/随退出）
│       └── todo_window.py   To Do 窗口编排（复用 tools/to-do 独立模块，hidden 预创建 + show 复用 + 退出销毁）
├── frontend/              前端资源（原 web/ 目录）
│   ├── editor.html / settings.html / tools.html
│   ├── script.js / storage.js / tab-manager.js / explorer.js / context-menu.js / settings.js / tools.js
│   ├── js/                 layout / resize / outline / history / workspace / search / theme-manager / theme-loader / file-tree / favorites
│   ├── themes/             主题 CSS（window/ editor/ preview/ 三子目录，以 body[data-*-theme="id"] 作用域）
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
├── build.bat               打包脚本
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
| `lib/core/api.py` | Api / SettingsApi / ToolApi；通过 `_main` 访问 main.py 全局状态 |
| `lib/core/settings.py` | settings.json 读写 |
| `lib/core/window_manager.py` | 热键调起窗口的强制前台聚焦（AttachThreadInput + 模拟 Alt） |
| `lib/backend/storage.py` | 聚合追加保存（save_note / save_daily_log） |
| `lib/backend/markdown.py` | 聚合格式 / obsidian:// 打开 / 调试日志 |
| `lib/backend/uploader.py` | 剪贴板 → PicGo HTTP API → R2 → Markdown 链接（取 `result[0]`） |
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
| `lib/modules/todo_window.py` | To Do 窗口编排（复用 tools/to-do 独立模块：hidden 预创建 + show 复用 + 退出销毁，Microsoft 适配器失败降级本地模式） |
| `commands/logger.py` | 结构化日志（app.log，持久句柄 + 目录缓存，flush 退出落盘） |
| `commands/performance.py` | 性能监控（mark/measure/log/time_call，写 performance.log） |
| `commands/app_utils.py` | 窗口置顶 / 居中 / 错误弹窗 / pick_folder（ctypes SHBrowseForFolderW，不用 Tkinter） |
| `commands/hotkey_manager.py` | RegisterHotKey 系统级热键 + 看门狗（30秒检测 + 2分钟强制重注册，重注册在热键线程内执行避免 1408） |

> 所有 lib/backend、lib/modules、commands 模块均**不依赖 UI / 网络**，可独立测试。

---

## 八、热键稳定性要求

- 热键：`Alt+S`（Inbox）/ `Alt+E`（FlashNote）/ `Alt+J`（Daily Log）/ `Alt+D`（Capture）。
- 实现：`RegisterHotKey` 系统级热键（非键盘钩子）→ 隐藏消息窗口（独立线程）→ `WM_HOTKEY` 置 `threading.Event`（零阻塞）→ 工作线程消费 → 窗口显示+置顶+聚焦。
- 看门狗：30 秒存活检测 + 2 分钟强制重注册。
- **重注册必须在热键线程内执行**（`WM_APP_REBIND` 消息触发），禁止跨线程直接调用 `RegisterHotKey`/`UnregisterHotKey`（会 1408 错误）。
- 异常日志：`shortcut_error.log`。

---

## 九、打包命令（build.bat 关键参数）

```bash
pyinstaller --noconfirm --clean ^
  --onefile --windowed ^
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

输出：`dist\Obsidian-upload.exe`（单文件，无控制台）。
config.json 嵌入 EXE，复制到 EXE 旁可自定义（无需重新打包）。

---

## 十、AI 修改代码流程

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
1. 大文件堆代码
2. 删除已有功能
3. 重写整个模块
4. 修改无关代码
5. 修改公共接口名称

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
- ✅ 热键正常（Alt+S/E/J/D）
- ✅ 自动保存正常
- ✅ 图片上传正常
- ✅ 历史记录正常
- ✅ 工作区正常

**日志**：
- ✅ app.log / shortcut_error.log / upload_debug.log

**配置**：
- ✅ config.json / settings.json / pages.json / workspace.json / history.json

**打包**：
- ✅ build.bat 正常
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

## 十一、性能优化规范

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

> 本规范为强制性执行标准。所有 AI 辅助开发必须严格遵守。如有特殊需求，需与团队评审并修改本规范。

# LeoDiary Capture（Obsidian-upload）

> Obsidian + PicGo + Cloudflare R2 专用快速记录工具。
> Markdown 编辑、实时预览、图片一键上传、多窗口多页签、自动保存防丢失、托盘常驻、全局热键。

LeoDiary Capture 是运行在 Windows 的桌面快速采集工具：四个独立窗口（Inbox / FlashNote / Daily Log / 📥 Capture）随叫随到，内容自动保存到 Tab 独立文件，点「保存」再追加到聚合文件；剪贴板图片 `Ctrl+V` 一键上传 PicGo → Cloudflare R2 图床；三栏布局支持目录导航与历史记录。

---

## 功能特性

- **Markdown 专业编辑**：CodeMirror 6（行号、折叠、语法高亮、自动补全）
- **实时预览**：右侧 marked.js 渲染，与编辑区**按比例双向同步滚动**（编辑区滚动 → 预览定位，预览点击 → 编辑区跳转）；预览区支持 `contenteditable` 直接编辑，修改后自动同步回编辑区（全量替换方案，120ms 防抖）
- **预览区右键编辑**：预览区右键菜单支持复制(`Ctrl+C`)、剪切(`Ctrl+X`)、粘贴(`Ctrl+V`)、全选(`Ctrl+A`)
- **四栏布局**：`📥 工作区 | 编辑 | 预览 | 第三栏`，工作区资源管理器默认隐藏，可点击展开；第三栏在「📑 目录」与「🕘 历史」间切换，拖拽调整各栏宽度
- **工作区资源管理器**：左侧文件夹树浏览工作区文件，点击 `.md` 以页签打开（编辑+预览同步），支持名称/时间排序与展开/折叠全部；文件右键菜单（复制文件名 / 复制完整路径 / 资源管理器显示 / VSCode 打开 / 复制副本 / 移动文件 / 重命名 / 删除到回收站），目录右键菜单（复制名称·路径 / 资源管理器显示 / 复制副本 / 移动文件夹 / 新建文件夹 / 新建文件 / 重命名 / 删除到回收站）；`Ctrl+H` 在工作区内全量搜索文件内容（按扩展名分组展示），点击结果定位到命中行
- **多窗口**：Inbox / FlashNote / Daily Log / 📥 Capture 四个独立窗口，同时存在、互不影响、独立编辑状态
- **多标签页**：每个窗口独立多个页签，首行标题自动命名、自动重命名文件、滚轮切换；页签右键菜单支持**关闭当前 / 关闭其他 / 关闭右侧 / 全部关闭 / 锁定**；`Ctrl+W` 快捷关闭当前标签；页签过多时自动折叠为「▼」下拉清单（按页签顺序列出全部隐藏页签，点击一键切换）
- **关闭标签弹窗确认**：Inbox / FlashNote / 日志记录窗口关闭标签时弹出确认对话框，可选择「保存」（保存到聚合文件后关闭）或「删除」（不保存直接移除）；Capture 窗口保持原有关闭即保存逻辑
- **自动保存防丢失**：编辑变化 3 秒 debounce 覆盖写入 Tab 文件 + 每 60 秒保险保存 + 退出程序后台保存全部页签，**不丢内容**
- **图片粘贴上传**：`Ctrl+V` 剪贴板图片 → PicGo HTTP API → Cloudflare R2 → 自动插入 `![图片](URL)`，预览立即显示，不保存本地图片
- **历史记录**：最近打开/编辑的文件按时间分组展示，可搜索、可点击重新打开
- **快速保存**：底部右侧「💾 保存」（保存 Tab 文件 + 聚合追加，随后隐藏窗口）与「⟳ 同步」（同样保存但窗口保持打开，保存中按钮旋转），聚合格式统一；操作成功右下角滑入提示，3 秒自动消失
- **目录导航**：当前文档标题章节大纲，点击跳转编辑区+预览区
- **文件关联打开**：用 EXE 直接打开 `.md/.txt/.json` 等文本文件，以页签形式进入
- **设置窗口**：右上角「⚙️」修改默认保存地址 + 三组独立主题（窗口 20 套 / 编辑区 30 套 / 预览 40 套），立即生效、重启保持
- **工具箱**：右上角「🛠️」插件式工具窗口（当前内置：画布 / 导入画布 / 删除空行 / 查找 / 页面顶部 / 页面底部 / ✅ To Do）
- **To Do 任务管理**：独立窗口（工具箱「✅ To Do」入口），SQLite 本地存储 + Microsoft To Do 双向同步；支持任务 CRUD、项目/标签/优先级分类、附件管理、自动同步；Microsoft 登录状态持久化，重启免重新登录
- **自定义功能区**：工具箱里勾选工具后，图标即显示在保存按钮左侧（单行、可拖拽排序），点击快捷执行，无需打开工具箱
- **保存/同步纯图标按钮**：底部右侧「💾 保存」/「⟳ 同步」精简为纯图标（悬停显示说明）
- **托盘常驻**：点窗口 X 隐藏到后台继续运行（隐藏不退出程序）；托盘右键「退出程序」结束所有 Obsidian-upload 实例（不会残留后台进程）
- **全局热键**：`Alt+E` / `Alt+S` / `Alt+R` / `Alt+D` 呼出四个窗口（RegisterHotKey 系统级热键，看门狗守护）
- **单实例保护**：多次启动只会激活已有窗口，不会重复运行
- **结构化日志**：app.log 全链路记录热键、窗口、上传、保存生命周期

---

## 窗口与快捷键

| 窗口 | 快捷键 | 保存目标 |
|------|--------|----------|
| 📦 Inbox | `Alt+E` | 保存 Inbox → `D:\Obsidian\LeoDiary\📦 inbox.md` |
| 🧠 FlashNote | `Alt+S` | 保存 FlashNote → `D:\Obsidian\LeoDiary\🧠 FlashNote.md` |
| 📅 日志记录 | `Alt+R` | 保存日志 → `log_dir\yyyy-MM-dd 周X.md`（按日期自动命名，追加不覆盖） |
| 📥 Capture | `Alt+D` | 保存 Capture → `D:\Obsidian\LeoDiary\A📥 收集（Capture）\Capture.md` |

## 保存机制说明

     所有窗口（Inbox / FlashNote / Daily Log / Capture）：
     - 支持资源管理器打开文件
     - 有保存 / 同步按钮
     - **Inbox / FlashNote / 日志记录**：关闭标签弹窗确认，可选择「保存」（保存到聚合文件后关闭）或「删除」（不保存直接移除）
     - **Capture 窗口**：关闭标签即保存，无需弹窗确认
     - **锁定标签**：右键菜单锁定后，`Ctrl+W` 和关闭按钮均不可关闭，防止误操作

     ---
     光标同步说明：
          编辑区 → 预览区：编辑区实时渲染预览（marked.js），滚动同步定位
          预览区 → 编辑区：预览区支持直接编辑（contenteditable），修改后 120ms 防抖全量替换回编辑区文档
          光标跨区保存：鼠标从预览区切入编辑区时，立即触发未保存内容的落盘

     保存机制
          1 debounce 自动保存  编辑器内容变化后，停止输入 3 秒才写 Tab 文件
          2 保险保存  每 1 分钟定时触发，但会比对内容，未变更则跳过
          3 标题自动重命名  首行标题变化后停止 1.2 秒触发
          4 关闭保存  关闭标签时立即保存当前内容（不等 debounce）
          颜色 状态 含义 🟢 绿色光晕 saved 已保存 内容已成功写入 Tab 文件 灰色光晕 unsaved 未保存 编辑后未落盘（3s debounce 等待中，或保存失败） 🔵 蓝色呼吸 saving 保存中 正在写盘，1s 呼吸动画 🔴 红色加粗 error 保存失败 写盘异常

     资源管理器打开的文件
          支持光标双向同步
          保存机制同上


四个窗口：同时存在、独立运行、互不影响、独立编辑状态。点窗口「X」= 隐藏到托盘，程序继续运行（不退出）。托盘图标**双击默认弹出 Capture 窗口**。

聚合保存格式统一为：

```markdown
#### 2026-08-01 19:31:53

内容...

---
```

---

## 三栏布局（目录 / 历史）

主界面为四栏，宽度可拖拽调整，**四个窗口独立记忆布局**（重启保持）：

```
┌──────┬──────────────┬──────────────┬──────────────┐
│ 📥工作区 │  Markdown 编辑 │  实时预览    │ 📑目录 / 🕘历史 │
└──────┴──────────────┴──────────────┴──────────────┘
```

- **四个窗口独立布局**：FlashNote / Inbox / 日志 默认仅显示编辑+预览；Capture 默认显示工作区+编辑+预览；各窗口面板显隐与宽度独立保存，互不影响
- **📥 工作区**：左侧资源管理器栏，点左上角窗口名称（如 `📦 Inbox`）显示/收起，宽度可拖拽（160-400px）；支持名称/时间排序、展开/折叠全部
- **📑 目录**：解析当前文档标题生成章节大纲，点击跳转编辑区与预览区，光标移动高亮当前章节
- **🕘 历史**：最近文件记录面板，见下节
- 点击「目录 / 历史」按钮切换第三栏内容，再次点击收起/展开；当前选择（`pane_mode`）、各栏宽度、工作区显隐（`workspace_visible`）、宽度（`workspace_width`）与资源树排序（`explorer_sort`）写入 `layout_<type>` 配置（如 `layout_flash`），重启保持

---

## 工作区资源管理器

快速浏览与检索工作区（Obsidian 仓库 / 项目目录）文件。

- **入口**：左上角窗口名称（`brand`，如 `📦 Inbox`），点击显示、再次点击收起（显隐与宽度自动记忆）
- **添加文件夹**：栏内「＋ 添加文件夹」→ Windows 文件夹选择对话框 → 加入工作区，存于 `%APPDATA%\Obsidian-upload\workspace.json`
- **文件树**：文件夹可展开/收起（懒加载，逐层扫描），支持按名称/时间排序与展开/折叠全部；点击 `.md` 等文件以新页签打开，恢复编辑与预览同步
- **右键操作**：文件与文件夹均支持右键菜单，操作成功自动局部刷新树（不整树重建）：
  - 文件：复制文件名 / 复制完整路径 / 资源管理器显示 / VSCode 打开 / 复制副本（`xxx-副本.md`，重名自动加序号）/ 移动文件 / 重命名（保留扩展名）/ 删除到回收站
  - 文件夹：复制名称·路径 / 资源管理器显示（直接打开该目录窗口）/ 复制副本（递归复制整个文件夹）/ 移动文件夹 / 新建文件夹（`新建文件夹`）/ 新建文件（`新建笔记.md`）/ 重命名（不补扩展名）/ 删除到回收站
  - **移动弹窗**：可展开/收缩的目录树（默认展开工作区根，显示一二级文件夹，更深层点击 ▸ 懒展开），点击目录行即移动；搜索时仅显示匹配目录及其祖先，命中行高亮；目标为自身/子目录的项自动排除
- **隐藏目录**：`.git / node_modules / __pycache__ / dist / .obsidian / .trash` 默认不显示（`config.json` 的 `workspace_hidden_dirs` 可配置）
- **全局搜索**：`Ctrl+H` 显示工作区并聚焦搜索框，在工作区内全量搜索 `.md/.txt/.py/.js/.json/.yaml/.yml/.ini/.tsc` 文件内容（搜索范围 = `search_exts` ∪ `explorer_exts`）
  - 逐文件逐行匹配（不整文件载入内存），超过 2MB 的文件跳过内容搜索
  - 文件名命中与内容命中均展示；内容命中显示「第 N 行」+ 命中行预览
  - 结果**按扩展名分组**展示（组标题吸顶），最多返回 500 条
  - 搜索框右侧「⚙️」可配置**匹配大小写 / 正则表达式 / 整词匹配**（条件保存在 localStorage，重启保持）
  - 点击结果打开文件并定位光标到命中行；`Esc` / 清空输入恢复文件树

---

## 历史记录

记录所有「打开 / 编辑保存」过的文件，用于快速找回最近工作内容。

- **入口**：顶部「🕘 历史」按钮（与「📑 目录」共用第三栏）
- **记录时机**：打开文件 → 更新「最后打开」；自动保存 / 手动保存 → 更新「最后编辑」；关闭页签不删除记录
- **按时间分组**：按**最后编辑时间**分组展示——`今天` / `昨天` / `前天` / 具体日期（如 `2026年8月22日`），组内与组间均按时间倒序
- **条目内容**：仅显示文件名 + 类型徽标，鼠标悬停显示完整路径
- **搜索**：顶部搜索框按文件名模糊搜索（200ms 防抖，不区分大小写），搜索结果同样分组
- **点击重开**：点击条目读取文件内容，以新页签打开，恢复 Markdown 编辑状态与预览同步
- **持久化**：存于 `%APPDATA%\Obsidian-upload\history.json`，磁盘保留上限 500 条，默认显示最近 100 条，2 秒防抖写盘 + 退出时立即落盘

---

## 图片上传

```
剪贴板图片 (Ctrl+V)
     ↓
Pillow 解析剪贴板图像
     ↓
PicGo HTTP API  http://127.0.0.1:36677/upload  （multipart/form-data，字段 files）
     ↓
Cloudflare R2 图床
     ↓
返回图片 URL（PicGo 返回 result[0]）
     ↓
插入 Markdown  ![](https://cdn.xxx.com/Pasted-image-xxx.png)
```

- 图片 **不保存本地**，直接上传 R2 并返回 URL
- PicGo 返回格式：`{"success": true, "result": ["https://..."]}`，取 `result[0]`
- 上传过程写入 `upload_debug.log`（成功 / 失败详情），失败时前端 toast 提示

---

## 保存规则（双轨并存）

两种保存并存、互不干扰：

**1. Tab 独立文件（自动保存，防丢失缓存）**
```
{default_save_path}\Inbox\
{default_save_path}\FlashNote\
{default_save_path}\Log\
Capture → capture_file 所在目录（默认 D:\Obsidian\LeoDiary\A📥 收集（Capture）\）
```
- 编辑变化 → 3 秒 debounce 覆盖写入
- 每 60 秒保险保存全部页签
- 关闭标签立即保存（不等 debounce，右键批量关闭同理）
- 覆盖写，不追加
- 首行标题变化 → 1200ms debounce 自动重命名文件
- 元数据记录：`%APPDATA%\Obsidian-upload\pages.json`

**2. 聚合文件（点「保存」按钮 / 日志）**
- 格式：`#### yyyy-MM-dd HH:mm:ss` + 正文 + `---`，**追加**，禁止覆盖旧内容
- Inbox → `inbox_file`（默认 `D:\Obsidian\LeoDiary\📦 inbox.md`）
- FlashNote → `flashnote_file`（默认 `D:\Obsidian\LeoDiary\🧠 FlashNote.md`）
- Daily Log → `log_dir\yyyy-MM-dd 周X.md`
- Capture → `capture_file`（默认 `D:\Obsidian\LeoDiary\A📥 收集（Capture）\Capture.md`）

> 点「保存」（💾）或「同步」（⟳）= 立即保存 Tab 文件 + 追加聚合文件；「保存」随后隐藏窗口到托盘，「同步」保持窗口打开。自动保存不得触发聚合追加。
> 启动时直接读取已保存页面（不弹恢复窗口）；退出程序时后台自动保存全部窗口所有页签内容。

---

## 数据目录

配置与元数据全部存于 `%APPDATA%\Obsidian-upload\`：

| 文件 | 作用 |
|------|------|
| `settings.json` | 默认保存地址 + 主题选择（window / editor / preview，设置窗口修改，立即生效、重启保持） |
| `pages.json` | 页面元数据（Tab 独立文件的 id / 标题 / 路径） |
| `workspace.json` | 工作区文件夹列表 |
| `layout.json` | 三栏布局（四个窗口独立：`layout_inbox` / `layout_flash` / `layout_log` / `layout_capture`）+ 窗口尺寸与位置记忆（`window_geometry`），优先写入 EXE 旁 config.json |
| `history.json` | 历史记录（最近打开 / 编辑的文件） |
| `tools.json` | 工具箱工具勾选状态（`pinned`）+ 功能区排序（`pinned_order`） |
| `performance.log` | 性能日志（启动耗时 / 模块加载 / 文件扫描 / 保存耗时） |
| `app.log` | 应用日志（全链路） |
| `shortcut_error.log` | 热键异常日志 |
| `upload_debug.log` | 图片上传调试日志 |

---

## 热键守护架构

全局热键采用 **RegisterHotKey 系统级热键**（非键盘钩子），由 Windows 统一裁决，任何程序前台运行时都可可靠触发：

```
用户按键 Alt+E / Alt+S / Alt+R / Alt+D
     ↓
RegisterHotKey 注册的热键（系统级，id 从 0xC000 起）
     ↓
WM_HOTKEY 消息循环 → 仅置位 threading.Event（零阻塞）
     ↓
工作线程 消费 Event → 执行 summon 回调（显示+置顶+聚焦窗口）
     ↓
看门狗线程（30 秒存活检测 + 2 分钟强制重注册）
     ↓
日志: app.log + shortcut_error.log
```

三重保障：
1. **零阻塞**：消息循环回调只置位 Event，立即返回
2. **存活检测**：每 30 秒检查热键消息循环是否存活，失效则重建
3. **强制重注册**：每 2 分钟在热键线程内重注册全部热键（重注册在热键线程内执行，避免跨线程调用 Windows 热键 API 引发 1408 错误）

日志可观察到：
```
[INFO] 热键管理器已启动（RegisterHotKey，4 个热键，30秒检测 + 2分钟强制重置）
[INFO] 热键 inbox (alt+e) 注册成功
[INFO] 热键 flash (alt+s) 注册成功
[INFO] 热键 log (alt+r) 注册成功
[INFO] 热键 capture (alt+d) 注册成功
```

---

## 文件关联打开

通过 Windows 文件关联，直接用本 EXE 打开常见文本文件：

- 受支持扩展名：`config.json` 的 `associated_exts`（内置默认 `.md .txt .ini .json .yaml .yml .tsc`）
- 双击关联文件（或命令行传入）→ 以页签形式打开，内容可编辑、可保存
- **单实例转发**：程序已在运行时，新启动的实例会把文件路径转交给已运行实例，由它打开新页签，不会重复启动进程

---

## 工具箱

- 入口：顶部「🛠️ 工具箱」按钮，独立窗口
- 插件式：每个工具一个独立目录（`tools\<工具名>\`，含 `config.json` + `index.js`）
- 工具列表与排序存于 `tools\tools.json`（用户配置在 `%APPDATA%\Obsidian-upload\tools.json`，勾选状态与功能区排序也保存在此）
- 当前内置：**🎨 画布**（Drawnix 开源白板：思维导图/流程图/自由画）、**🖼️ 导入画布**（把当前页签 Markdown 一键导入画布生成思维导图）、**🧹 删除空行**（清理 Markdown 连续空行）、**🔍 查找**（编辑器查找面板）、**⬆️ 页面顶部**（滚动到第一行）、**⬇️ 页面底部**（滚动到最后一行）
- **画布**：点击「🎨 画布」→ 独立窗口打开 Drawnix 白板。Drawnix 是 Vite/React 构建的 ES Module 应用，`file://` 直开会被浏览器 CORS 拦截白屏，程序用 `lib/modules/canvas_server.py` 在 `127.0.0.1` 随机端口起本地 HTTP 服务承载 `tools\drawnix\` 构建产物（随程序启动、随退出关闭），并放开浏览器下载以支持导出 PNG/JSON
- **导入画布**：点击「🖼️ 导入画布」（或功能区图标）→ 把当前编辑器页签的 Markdown 内容经 `Api.import_markdown_to_canvas` 提交给本地画布服务（`canvas_server.submit_import`），画布内嵌桥接 JS 轮询消费后用 Drawnix 官方 `parseMarkdownToDrawnix` 解析成思维导图渲染；若画布窗口未打开会自动打开
- **自定义功能区**：卡片右上角勾选框 → 勾选后该工具图标出现在编辑器底部「保存」按钮左侧，点击快捷执行；图标可拖拽自定义顺序；取消勾选即从功能区移除

```
tools/
├── tools.json             工具列表（id/名称/描述/图标/排序/勾选状态 pinned + 功能区排序 pinned_order）
├── clean_empty_lines/
│   ├── config.json
│   └── index.js
└── drawnix/               Drawnix 白板构建产物（Vite 静态资源，由本地 HTTP 服务承载）
```

---

## 主题系统

三组独立主题（窗口 20 套 / 编辑区 30 套 / 预览 40 套），在「⚙️ 设置」窗口下拉选择 → 点「应用主题」立即生效。

```
frontend/themes/
├── window/   窗口主题（20 套）：工具栏/Tab/按钮/面板/背景，github-light / notion-light / obsidian-dark / solarized-light / dracula-dark / nord-dark / material-light / one-dark / monokai-dark / github-dark ...
├── editor/   编辑区主题（30 套）：CodeMirror 6 语法高亮，鲜艳高对比度，github-light / monokai / dracula / nord / gruvbox-dark / tokyo-night / catppuccin-mocha / synthwave-84 / rose-pine ...
└── preview/  预览主题（40 套）：白底层次分明，参考 GitHub/Notion/Medium/Stripe/Apple Docs/Tailwind/Vercel 等国际知名 Markdown 样式，另含霓虹/日落/海洋/森林/糖果/皇家/赛博朋克/秋日/热带/星河 10 套鲜明风格
```

**架构：CSS 懒加载（ThemeLoader）+ data 属性切换 + JS 轮询同步**

1. 主题 CSS 由 `frontend/js/theme-loader.js` **按需懒加载**：HTML 只保留基础结构样式，启动时仅注入当前激活主题的 CSS；切换主题时先加载新 CSS 再移除旧的 `<link>`（避免切换瞬间无样式）
2. 每套 CSS 以 `body[data-window-theme="id"]` / `body[data-editor-theme="id"]` / `body[data-preview-theme="id"]` 选择器作用域，切换主题 = 修改 `body` 的 `data-*-theme` 属性，只有匹配的 CSS 生效
3. 设置窗口点「应用主题」→ `save_theme()` 保存到 `settings.json` → 本地同步 apply（即时生效）
4. 编辑器 / 工具箱窗口通过 `theme-manager.js` 每 2 秒轮询 `get_theme()`，检测到变化则先经 ThemeLoader 加载 CSS 再 apply（最多 2 秒延迟）

> **不使用 Python `evaluate_js` 广播**：pywebview edgechromium 后台线程调用 `evaluate_js` 会破坏 JS 桥接内部状态（`_jsApiCallback` 冲突），改用 JS 端轮询彻底避免。

> **pywebview 参数命名陷阱**：暴露给 JS 的 API 方法参数名禁止使用 `window`（会遮蔽 JS 全局 `window` 对象，导致 `window.pywebview._jsApiCallback(...)` 报 `Cannot read properties of undefined`）。本项目 `save_theme` 方法使用 `window_theme` 而非 `window` 作为参数名。

---

## 使用流程

1. 双击 `Obsidian-upload.exe`（无需管理员权限，首次启动自动注册热键）
2. `Alt+E` / `Alt+S` / `Alt+R` / `Alt+D` 呼出对应窗口（或点击托盘图标）
3. 输入 Markdown，`Ctrl+V` 粘贴图片自动上传 Cloudflare R2
4. **预览区编辑**：直接在右侧预览区点击编辑，修改自动同步回编辑区；右键菜单支持复制/剪切/粘贴/全选
5. 内容自动保存到 Tab 文件；点「保存」额外追加到聚合文件
6. 标签页右键：关闭当前 / 关闭其他 / 关闭右侧 / 全部关闭 / 锁定；`Ctrl+W` 快捷关闭
7. 查看「🕘 历史」按时间找回最近编辑的文件，点击重新打开
8. 点窗口 X 隐藏到托盘，随时再次呼出；托盘菜单可退出程序

---

## 快捷键

| 按键 | 功能 |
|------|------|
| `Alt+E` | 呼出/置顶 Inbox 窗口 |
| `Alt+S` | 呼出/置顶 FlashNote 窗口 |
| `Alt+R` | 呼出/置顶 Daily Log 窗口 |
| `Alt+D` | 呼出/置顶 Capture 窗口 |
| `Ctrl+W` | 关闭当前标签页（锁定标签不可关闭） |
| `Ctrl+V` | 剪贴板图片 → 上传 → 插入 `![](URL)`（文字则正常粘贴） |
| `Ctrl+Enter` | 保存当前窗口（Tab 文件 + 聚合追加） |
| `Ctrl+H` | 工作区全量搜索（显示资源管理器并聚焦搜索框） |
| `Ctrl+C` | 复制选中文本（编辑区 / 预览区通用） |
| `Ctrl+X` | 剪切选中文本（编辑区 / 预览区通用） |
| `Ctrl+A` | 全选当前区域文本（编辑区 / 预览区通用） |

---

## 项目结构

项目采用三层包结构（`lib/core` + `lib/backend` + `lib/modules`），前端资源在 `frontend/`，配置在 `config/`：

```
Obsidian-upload-web/
├── lib/                        Python 包根
│   ├── __init__.py
│   ├── core/                   核心层（入口与编排）
│   │   ├── __init__.py
│   │   ├── main.py             程序入口：四窗口 + 设置 / 工具箱 / 画布窗口 + js_api + 托盘 + 单实例 + 看门狗（禁止写业务）
│   │   ├── api.py              Api / SettingsApi / ToolApi（通过 _main 访问 main.py 全局状态）
│   │   ├── window_manager.py   热键调起窗口的强制前台聚焦（AttachThreadInput + 置顶）
│   │   └── settings.py         settings.json 读写（默认保存地址）
│   ├── backend/                后端业务层
│   │   ├── __init__.py
│   │   ├── storage.py          聚合追加保存（save_note / save_daily_log）
│   │   ├── markdown.py         聚合保存格式 / obsidian:// 打开 / 调试日志
│   │   ├── uploader.py         剪贴板图片 → PicGo HTTP API → Cloudflare R2 → Markdown 链接
│   │   ├── capture.py          Capture 窗口配置 + 聚合保存路径与逻辑（config.json 的 capture_file）
│   │   └── search_engine.py    工作区内容搜索（逐行增量匹配、文件名/内容命中、limit 截断）
│   └── modules/                功能模块层
│       ├── __init__.py
│       ├── pages.py            pages.json 元数据 + Tab 独立文件管理（覆盖写/重命名/恢复）
│       ├── theme_manager.py    主题配置读写（settings.json 的 theme 字段：window / editor / preview 三组）
│       ├── layout_store.py     布局记忆（四个窗口独立：宽度比例 / pane_mode / 工作区显隐与宽度 / explorer_sort）+ 窗口尺寸与位置记忆（window_geometry）
│       ├── workspace.py        工作区管理（workspace.json 读写、文件夹增删）
│       ├── file_tree.py        文件树扫描（懒加载、隐藏目录过滤、explorer_exts 显示 / search_exts 搜索规则）
│       ├── file_explorer.py    资源管理器后端编排（文件夹增删 / scan 懒加载 / 时间·名称排序 / 打开文件）
│       ├── file_ops.py         右键菜单后端（剪贴板 / 资源管理器 / VSCode / 重命名 / 复制副本 / 新建 / 移动 / 删除到回收站）
│       ├── file_assoc.py       文件关联打开（扩展名过滤 / 单实例文件转发）
│       ├── history.py          历史记录持久化（record_open / record_edit / query / search / flush / rename / move_path / remove / remove_tree）
│       ├── favorites.py        收藏夹
│       └── canvas_server.py    画布本地 HTTP 服务（Drawnix ES Module 需 HTTP 加载，127.0.0.1 随机端口，随启动/随退出）
├── frontend/                   前端资源（原 web/ 目录）
│   ├── editor.html             编辑窗口结构（工作区 + 三栏 + 工具栏）
│   ├── script.js               CodeMirror / Tab / 图片粘贴 / 保存 / 历史重开 / 工作区打开 / 功能区渲染
│   ├── storage.js              自动保存（3s debounce + 60s 保险）+ 页面 API 封装
│   ├── tab-manager.js          Tab 渲染 + 状态圆点 + 关闭/删除确认
│   ├── settings.html / settings.js / settings.css   设置窗口
│   ├── tools.html / tools.js / tools.css            工具箱窗口
│   ├── theme.css               主题基础变量（被 themes/ 下的具体主题覆盖）
│   ├── style.css               布局样式
│   ├── explorer.css            工作区资源管理器样式（树行 / 缩进 / 文件名省略 / 右键菜单 / 弹窗输入）
│   ├── explorer.js             工作区资源管理器渲染（懒加载逐层展开、时间·名称排序、展开/折叠全部、文件·目录点击与右键回调、refreshDir/refreshAll 局部刷新）
│   ├── context-menu.js         通用右键菜单 / 重命名弹窗 / 删除确认弹窗 / 移动弹窗（可展开/收缩目录树）
│   ├── js/
│   │   ├── layout.js           布局核心（目录/历史模式切换、工作区显隐、宽度应用、布局保存）
│   │   ├── resize.js           拖拽调整宽度（工作区/编辑/预览/目录）
│   │   ├── outline.js          目录（章节大纲、点击跳转、光标高亮）
│   │   ├── history.js          历史面板（按时间分组渲染、搜索、点击重开）
│   │   ├── workspace.js        工作区资源管理器（文件夹增删、栏显隐、Ctrl+H 聚焦、文件·目录右键菜单）
│   │   ├── search.js           工作区全局搜索（输入防抖、按扩展名分组渲染、点击定位）
│   │   ├── theme-manager.js    主题管理器（轮询 get_theme 检测变化 + 调 ThemeLoader 加载 CSS + data 属性切换）
│   │   ├── theme-loader.js     主题 CSS 懒加载（按需注入 <link>，切换时先加载新再移除旧，避免无样式闪烁）
│   │   ├── file-tree.js        文件树前端渲染辅助
│   │   └── favorites.js        收藏夹前端
│   ├── themes/                 主题 CSS 文件（每套以 body[data-*-theme="id"] 作用域）
│   │   ├── window/             窗口主题（20 套）
│   │   ├── editor/             编辑区主题（30 套，鲜艳高对比度语法高亮）
│   │   └── preview/            预览主题（40 套，白底，参考国际知名 Markdown 样式 + 鲜明风格主题）
│   └── vendor/                 cm6.min.js、marked.min.js（本地化，离线可用）
├── commands/                   通用模块（保持原位）
│   ├── __init__.py
│   ├── logger.py               结构化日志（app.log）
│   ├── app_utils.py            窗口置顶、屏幕居中、错误弹窗
│   ├── hotkey_manager.py       全局热键（RegisterHotKey + 看门狗）
│   └── performance.py          性能监控（mark/measure/log，写 performance.log）
├── tools/                      工具插件目录（tools.json + clean_empty_lines/ + drawnix/，保持原位）
├── config/config.json          配置文件（PicGo / 路径 / 布局 / 文件关联）
├── scripts/make_icon.py        生成 app.ico（多尺寸）
├── spec/                       PyInstaller spec 输出目录
├── test/test-theme-run.py      主题调试脚本
├── build.bat                   打包脚本（PyInstaller）
├── app.ico
├── CLAUDE.md
├── README.md
└── dist/Obsidian-upload.exe
```

> 入口已从旧 `main.py` 改为 `lib/core/main.py`；旧 `Obsidian-upload.py`（Tkinter 版）已删除。所有后端模块统一使用包结构 import（如 `from lib.backend import storage`、`from lib.modules import file_explorer`、`from lib.core import settings`）。

---

## 配置（config/config.json）

`config/config.json` 内嵌于 EXE，复制到 EXE 同目录即可自定义（无需重新打包）：

```json
{
  "picgo_api": "http://127.0.0.1:36677/upload",
  "cloudflare_domain": "https://pub-xxx.r2.dev",
  "inbox_file": "D:\\Obsidian\\LeoDiary\\📦 inbox.md",
  "flashnote_file": "D:\\Obsidian\\LeoDiary\\🧠 FlashNote.md",
  "log_dir": "D:\\Obsidian\\LeoDiary\\Journals",
  "capture_file": "D:\\Obsidian\\LeoDiary\\A📥 收集（Capture）\\Capture.md",
  "vault_name": "LeoDiary",
  "associated_exts": [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"],
  "workspace_hidden_dirs": [".git", "node_modules", "__pycache__", "dist", ".obsidian", ".trash"],
  "search_exts": [".md", ".txt", ".py", ".js", ".json", ".yaml", ".yml"],
  "explorer_exts": [".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tsc"],
  "layout": {
    "editor_width": 30,
    "preview_width": 32,
    "outline_width": 38,
    "outline_visible": false,
    "pane_mode": "outline",
    "workspace_visible": false,
    "workspace_width": 220,
    "explorer_sort": "time"
  }
}
```

| 字段 | 作用 |
|------|------|
| `picgo_api` | PicGo 上传接口地址（默认本地 36677 端口） |
| `cloudflare_domain` | R2 图床返回的 URL 前缀 |
| `inbox_file` / `flashnote_file` / `capture_file` | 聚合保存目标文件 |
| `log_dir` | 日志保存目录（`yyyy-MM-dd 周X.md`） |
| `vault_name` | Obsidian 仓库名（`obsidian://` 打开用） |
| `associated_exts` | 文件关联支持的扩展名 |
| `workspace_hidden_dirs` | 工作区文件树隐藏的目录名（大小写不敏感） |
| `search_exts` | `Ctrl+H` 工作区搜索参与内容匹配的扩展名（搜索范围 = `search_exts` ∪ `explorer_exts`） |
| `explorer_exts` | 资源管理器文件树显示的扩展名（`workspace_hidden_dirs` 之外的过滤规则） |
| `layout` | 布局内置默认（宽度比例 / 目录可见性 / 第三栏模式 / 工作区显隐与宽度 / 资源树排序）；运行时各窗口独立布局保存为 `layout_flash` / `layout_inbox` / `layout_log` / `layout_capture`，窗口尺寸位置保存为 `window_geometry`（`%APPDATA%\Obsidian-upload\layout.json`） |
| `window_geometry` | 各窗口尺寸与位置记忆（`layout.json`，移动/缩放后节流写盘） |

> 默认保存地址（Tab 独立文件根目录）在程序内「⚙️ 设置」窗口修改，写入 `%APPDATA%\Obsidian-upload\settings.json`，立即生效、重启保持。

---

## 依赖

- Python 3.10+（实测 3.14）
- `pywebview`（含 Edge WebView2 Runtime，Win10/11 自带）
- `Pillow`（剪贴板图片解析）
- `requests`（PicGo 上传）
- `pystray`（系统托盘）
- Node.js（仅前端脚本语法检查 / 重新构建 CodeMirror 时用，运行 EXE 不需要）
- 本地 [PicGo](https://picgo.github.io/PicGo-Doc/) 服务（端口默认 36677，配置 R2 图床）

> 说明：热键已从 `keyboard` 库升级为 Windows `RegisterHotKey` 系统级热键，运行时不再依赖 `keyboard`。

---

## 打包

```bash
build.bat
```

打包命令等价于（入口 `lib\core\main.py`，`--paths .` 让 PyInstaller 识别 `lib` 包根，`--specpath spec` 输出 spec 文件，`--collect-submodules=lib` 收集所有子模块）：

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
  --hidden-import=commands.app_utils --hidden-import=commands.hotkey_manager ^
  --hidden-import=commands.performance ^
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
`config/config.json` 嵌入 EXE，复制到 EXE 旁可自定义（无需重新打包）。

> **体积优化说明**：EXE 约 20MB。打包已做三项裁剪：
> - `--exclude-module cryptography`：urllib3 可选 pyopenssl 依赖，上传只走本地 HTTP 用不到，省约 6MB
> - `--exclude-module PIL._avif`：Pillow 的 AVIF 编解码，托盘图标用不上，省约 4MB
> - `--upx-dir`：UPX 5.2 压缩内嵌 DLL/PYD，约再省 2MB
> 需先在 `C:\Users\leokou\AppData\Local\upx\upx-5.2.0-win64` 安装 UPX（github.com/upx/upx/releases 下载 win64 解压即可）；未装 UPX 时删除该行仍可打包（约 22MB）。

---

## 日志

| 日志文件 | 位置 | 记录内容 |
|----------|------|----------|
| 应用日志 `app.log` | `%APPDATA%\Obsidian-upload\app.log` | 全链路：启动 / 窗口 / 热键 / 上传 / 保存 / 看门狗 |
| 热键异常 `shortcut_error.log` | `%APPDATA%\Obsidian-upload\shortcut_error.log` | 热键注册失败、异常恢复、当前状态 |
| 上传调试 `upload_debug.log` | `%APPDATA%\Obsidian-upload\upload_debug.log` | 图片上传成功 / 失败详情 |
| 性能日志 `performance.log` | `%APPDATA%\Obsidian-upload\performance.log` | 启动耗时 / 模块加载 / 文件扫描 / 保存耗时（`commands/performance.py`） |
| 笔记日志 | `log_dir\yyyy-MM-dd 周X.md` | 保存日志按钮生成的每日笔记（追加） |

---

## 开发

- **语法检查**：
  - Python：`python -m py_compile lib\core\main.py lib\core\api.py lib\core\settings.py lib\core\window_manager.py lib\backend\storage.py lib\backend\markdown.py lib\backend\uploader.py lib\backend\capture.py lib\backend\search_engine.py lib\modules\pages.py lib\modules\theme_manager.py lib\modules\layout_store.py lib\modules\workspace.py lib\modules\file_tree.py lib\modules\file_explorer.py lib\modules\file_ops.py lib\modules\file_assoc.py lib\modules\history.py lib\modules\favorites.py lib\modules\canvas_server.py commands\logger.py commands\app_utils.py commands\hotkey_manager.py commands\performance.py`
  - JavaScript：`node --check frontend\*.js frontend\js\*.js`
- **前端模块职责**：`frontend/js/layout.js` 管布局模式与保存，`resize.js` 管拖拽，`outline.js` 管目录，`history.js` 管历史面板，`explorer.js` 管树渲染，`context-menu.js` 管右键菜单/重命名/删除确认，`workspace.js` 管工作区，`search.js` 管搜索，`theme-loader.js` 管主题 CSS 懒加载，`theme-manager.js` 管主题轮询同步；`script.js` 只做编排与胶水
- **历史持久化**：`lib/modules/history.py` 不依赖 UI / 网络，可独立测试；后端只记录「打开 / 编辑」，分组展示纯前端完成
- **工作区与搜索**：`lib/modules/workspace.py / file_tree.py / file_explorer.py / search_engine.py / file_ops.py` 均为纯后端模块，不依赖 UI，可独立测试；树懒加载逐层扫描、搜索逐行增量匹配不整文件载入内存（搜索范围 = `search_exts` ∪ `explorer_exts`）；文件·文件夹右键操作走 `file_ops.py`（删除绝不物理删除，走回收站；重命名/移动/删除同步 `history` 的 rename / move_path / remove_tree）
- **入口与全局状态**：入口在 `lib/core/main.py`；`lib/core/api.py` 通过 `from lib.core import main as _main` 访问 main.py 的全局状态（`_windows` / `_tools_window` / `_page_seq` / `WINDOW_TITLES` 等），具体约束详见 `CLAUDE.md`
- **新增功能原则**：独立模块、可插拔、低耦合；优先新增文件（`lib/modules/xxx.py` 或 `lib/backend/xxx.py`），避免在大文件里堆业务逻辑（详见 `CLAUDE.md`）
# LeoDiary Capture 项目开发执行规范

项目名称：
LeoDiary Capture

项目定位：
LeoDiary Capture 是一个基于 Python + HTML/CSS/JS + WebView2(pywebview) 的 Obsidian 快速记录工具。

目标：
打造类似 Obsidian 原生体验的个人知识快速采集系统。

核心能力：
- Markdown 快速编辑
- Markdown 实时预览（双向同步滚动）
- 四栏布局（工作区资源管理器 | 编辑 | 预览 | 第三栏：目录/历史切换）
- 工作区资源管理器（文件夹树、点击打开、Ctrl+H 全量搜索）
- 图片上传（PicGo → Cloudflare R2）
- 图片自动插入 Markdown
- Inbox 快速记录
- FlashNote 快速记录
- Daily Log 日志记录
- Capture 快速收集（Alt+D）
- 多窗口管理（4 个独立窗口）
- 多标签页管理
- 自动保存防丢失（Tab 独立文件 + 聚合文件双轨）
- 历史记录（按时间分组、搜索、点击重开）
- 目录导航（章节大纲）
- 文件关联打开（单实例转发）
- 布局记忆（宽度比例 / 第三栏模式 / 工作区显隐与宽度重启保持）
- 工具插件系统

==================================================
一、最高开发原则
==================================================
所有开发必须遵守：
1. 稳定运行优先
2. 数据安全优先
3. 用户体验优先
4. 功能扩展优先
禁止：
- 一次性重构整个项目
- 删除已有功能
- 重写历史模块
- 改变已有接口
- 将所有代码堆积到单文件
- 为小功能修改大量无关代码
所有新增功能必须：
1. 新功能独立模块
2. 后端与前端分离
3. 单一职责
4. 可插拔、低耦合
5. 可单独测试
6. 复用已有能力
7- 易维护

==================================================
二、模块化架构要求
==================================================
核心要求：
禁止：
main.py 持续堆积业务代码。
错误方式：
main.py：
包含：
- 图片上传
- Markdown处理
- 快捷键
- 设置管理
- UI逻辑
- 保存逻辑
- 工具系统
- 日志系统
正确方式：
按照功能拆分模块。
实际结构：
project/
├── main.py                程序入口：窗口 + js_api(Api类) + 托盘 + 单实例 + 看门狗
│                          禁止写业务逻辑
├── pages.py               页面元数据 pages.json + Tab 独立文件管理
├── settings.py            settings.json 读写（默认保存地址）
├── storage.py             聚合追加保存（save_note / save_daily_log）
├── uploader.py            剪贴板图片 → PicGo → R2 → Markdown 链接
├── markdown.py            聚合保存格式 / obsidian:// 打开 / 调试日志
├── history.py             历史记录持久化（record_open / record_edit / query / search / flush / rename / move_path / remove / remove_tree）
├── file_ops.py            右键菜单后端操作（剪贴板复制 / 资源管理器显示 / VSCode 打开 / 重命名 / 复制副本 / 新建文件夹·文件 / 移动 / 删除到回收站）
├── layout_store.py        三栏布局记忆（宽度比例 / 目录可见性 / pane_mode / 工作区显隐与宽度 / explorer_sort）
├── workspace.py           工作区管理（workspace.json 读写、文件夹增删）
├── file_tree.py           文件树扫描（懒加载、隐藏目录过滤、explorer_exts 显示规则 / search_exts 搜索规则）
├── file_explorer.py       资源管理器后端编排（文件夹增删 / scan 懒加载 / 名称·时间排序 / 打开文件 / all_dirs / 复制副本 / 新建文件夹·文件 / 移动）
├── search_engine.py       工作区内容搜索（逐行增量匹配、文件名/内容命中、limit 截断）
├── window_manager.py      热键调起窗口的强制前台聚焦
├── file_assoc.py          文件关联打开 + 单实例文件转发
├── commands/
│   ├── logger.py          结构化日志（app.log）
│   ├── app_utils.py       窗口置顶、居中、错误提示
│   └── hotkey_manager.py  全局热键（RegisterHotKey + 看门狗）
├── web/                   前端（HTML/CSS/JS）
│   ├── editor.html        编辑窗口结构
│   ├── script.js          编排层（CodeMirror / Tab / 图片粘贴 / 保存 / 历史重开）
│   ├── storage.js         自动保存（2s debounce + 30s 保险）+ 页面 API 封装
│   ├── tab-manager.js     Tab 渲染 + 状态圆点 + 关闭/删除确认
│   ├── settings.*         设置窗口
│   ├── tools.*            工具箱窗口
│   ├── theme.css / style.css / explorer.css
│   ├── explorer.js        资源管理器渲染（懒加载逐层展开、名称·时间排序、展开/折叠全部、文件·目录点击回调 + 右键菜单）
│   ├── context-menu.js    通用右键菜单 / 重命名弹窗 / 删除确认弹窗
│   └── js/
│       ├── layout.js      三栏布局核心（模式切换 / 宽度应用 / 布局保存）
│       ├── resize.js      拖拽调整宽度
│       ├── outline.js     目录（章节大纲）
│       └── history.js     历史面板（分组渲染 / 搜索 / 点击重开）
└── tools/                 工具插件目录

==================================================
三、功能模块设计规则
==================================================
1. 单一职责原则
一个文件只负责一个主要功能。
例如：
clean_empty_lines.py
只能负责：
- 检测空行
- 删除空行
- 返回处理结果
禁止加入：
- UI代码
- 网络请求
- 文件保存
- 快捷键
--------------------------------------------------
2. 公共能力必须抽离
多个模块共同使用：
- 文件读写
- JSON处理
- Markdown处理
- 日期格式
- 路径管理
必须抽离到公共模块（utils/ 或 commands/）。
禁止复制粘贴代码。
--------------------------------------------------
3. UI与业务分离
UI负责：
- 创建窗口
- 创建按钮
- 用户输入
- 显示状态
业务负责：
- 保存文件
- 图片上传
- 数据处理
- 文件管理
禁止：
按钮事件中直接写业务逻辑。
正确：
button_click()
调用：
save_service.save()
--------------------------------------------------
4. 配置统一管理
禁止硬编码。
错误：
SAVE_PATH="D:\\Obsidian\\LeoDiary"
正确：
config.json 或 settings.json 读取。
代码读取配置。

==================================================
四、技术架构要求
==================================================
必须使用：
后端：
- Python
桌面窗口：
- pywebview 6
- Microsoft Edge WebView2
前端：
- HTML
- CSS
- JavaScript
编辑器：
- CodeMirror 6
Markdown：
- marked.js v15
打包：
- PyInstaller EXE（build.bat）
禁止：
- Tkinter（Obsidian-upload.py 为旧版遗留，禁止恢复使用）
- PyQt替代Web UI
- AutoHotkey作为主程序
原因：
HTML/CSS/JS 更适合：
- Markdown编辑
- 双栏/三栏预览
- 图片展示
- 拖动排序
- 主题系统

==================================================
五、项目目录规范
==================================================
main.py
入口文件：
负责：
- 初始化程序
- 创建四个窗口（inbox / flash / log / capture）
- 注册 API（Api 类，js_api）
- 注册托盘
- 注册热键
- 单实例检查
- 健康检查看门狗
禁止：
写业务代码。

pages.py
负责：
- pages.json 元数据（%APPDATA%\Obsidian-upload\pages.json）
- Tab 独立 Markdown 文件管理（覆盖写，自动保存防丢失）
- 文件名清洗 / 去重 / 启动恢复

settings.py
负责：
- settings.json 读写（%APPDATA%\Obsidian-upload\settings.json）
- 默认保存地址 default_save_path（立即生效、重启保持）

storage.py
负责：
- 聚合追加保存（save_note / save_daily_log）
- 追加格式：#### yyyy-MM-dd HH:mm:ss + 正文 + ---

capture.py
负责：
- Capture 窗口配置（WINDOW_DEF：key/title/hotkey/saveLabel/hotkeyHint，供 main.py 复用）
- Capture 聚合保存路径（config.json 的 capture_file，缺省内置默认，不写死）
- Capture 聚合保存（save_capture：复用 storage.save_note 的标准格式追加）
- Capture Tab 目录特殊：与聚合文件同在 capture_file 所在目录（由 main.py _tab_dir 单独解析）

uploader.py
负责：
- 剪贴板图片 → Pillow 解析 → PicGo HTTP API → Cloudflare R2 → Markdown 链接
- PicGo 字段 files，返回 result[0]

markdown.py
负责：
- 聚合保存格式
- obsidian:// 打开
- 调试日志

history.py
负责：
- 历史记录持久化（%APPDATA%\Obsidian-upload\history.json）
- record_open(path)：打开时更新最后打开时间
- record_edit(path)：编辑/保存时更新最后编辑时间
- query(limit) / search(keyword, limit)：按最后编辑时间倒序
- rename(old, new)：重命名后迁移旧路径记录（含子路径，实际委托 move_path）
- move_path(old, new)：移动后把 old 下（含自身）全部记录迁移到 new 对应位置
- remove(path)：删除文件后移除该路径记录；remove_tree(path)：删除文件夹后移除该路径及其所有子路径记录
- 磁盘上限 500，查询默认 100，2 秒 debounce 写盘 + flush() 立即落盘
- RLock 线程安全（多窗口自动保存并发）
- 不依赖 UI / 网络，可独立测试

layout_store.py
负责：
- 布局记忆（编辑/预览/目录宽度比例 + 目录可见性 + pane_mode + workspace_visible + workspace_width + explorer_sort）
- 读：EXE 旁 config.json → %APPDATA%\Obsidian-upload\layout.json → 内置默认
- 写：优先 EXE 旁 config.json，否则 layout.json

workspace.py
负责：
- 工作区管理（%APPDATA%\Obsidian-upload\workspace.json）
- folders() / add_folder() / remove_folder()
- 目录必须存在、路径去重（大小写不敏感）、名称取目录名
- RLock 线程安全，不依赖 UI / 网络，可独立测试

file_ops.py
负责：
- 右键菜单后端操作：copy_text（ctypes 剪贴板复制）/ reveal_in_explorer（资源管理器显示，文件夹直接打开目录、文件定位选中）/ open_with_vscode（VSCode 打开）/ rename_file（重命名，文件自动保留扩展名、文件夹不补、非法字符与重名检测）/ delete_file（SHFileOperationW 删除到回收站，绝不物理删除）/ duplicate_file（复制副本，文件 copy2 / 文件夹 copytree，重名自动加序号）/ create_folder / create_file（新建文件夹·Markdown 文件，重名自动加序号）/ move_item（移动文件·文件夹，禁止移入自身内部、重名自动加序号）
- 正确声明 Win32 签名（避免 64 位 HGLOBAL / HANDLE 截断）
- 重命名/删除/移动后同步 history（rename / remove / remove_tree / move_path），不依赖 UI / 网络，可独立测试

file_tree.py
负责：
- 文件树懒加载扫描：scan_dir(path, cfg) 只返回直接子项，逐层展开
- 隐藏目录过滤（config.json 的 workspace_hidden_dirs，默认 .git/node_modules/__pycache__/dist/.obsidian/.trash）
- 显示规则 explorer_exts（默认 .md/.txt/.ini/.json/.yaml/.yml/.tsc）：scan_dir 只返回这些扩展名的文件
- iter_files(roots, cfg, limit=None, exts=None)：递归遍历工作区文件（供搜索用，跳过隐藏目录），
  exts 默认 search_exts（默认 .md/.txt/.py/.js/.json/.yaml/.yml）
- 目录在前、按名排序；不依赖 UI，可独立测试

file_explorer.py
负责：
- 资源管理器后端编排：folders() / add_folder() / remove_folder() / scan(path, sort) / open_file(path) / all_dirs() / duplicate() / move() / new_folder() / new_file()
- 排序偏好 get_sort_pref() / set_sort_pref()（复用 layout_store，存 config.json layout.explorer_sort：name 名称 / time 时间）
- 薄转发，复用 workspace / file_tree / history / layout_store，不写业务逻辑

search_engine.py
负责：
- 工作区内容搜索：search(roots, keyword, cfg, limit=100)
- 扩展名过滤：search_exts ∪ explorer_exts 的并集（保证搜索结果含 .ini/.tsc 等资源树文件）
- 逐文件逐行增量匹配（不整文件载入内存），超过 2MB 的文件跳过内容搜索
- 文件名命中 kind="filename"（line_no=0）、内容命中 kind="content"（含行号+命中行预览）
- 不区分大小写，返回结果最多 limit 条（前端请求 limit=500）

window_manager.py
负责：
- 热键调起窗口的统一激活流程
- force_foreground(hwnd)：AttachThreadInput + 模拟 Alt 键绕过 Windows 前台锁
- 正确声明 Win32 签名（避免 64 位 HWND 截断）

file_assoc.py
负责：
- 受支持扩展名统一配置（config.json 的 associated_exts）
- 启动参数过滤：从 sys.argv 提取受支持文件绝对路径
- 单实例转发：新实例带文件参数 → pending 队列 → 已运行实例消费打开

commands/
logger.py
负责：
- 结构化日志（app.log）
app_utils.py
负责：
- 窗口置顶
- 居中
- 错误提示
- pick_folder()：Windows 文件夹选择对话框（ctypes SHBrowseForFolderW，不用 Tkinter；工作区选目录现由 main.py 的 pick_workspace_folder 改用 pywebview create_file_dialog）
hotkey_manager.py
负责：
- RegisterHotKey 系统级热键（独立线程隐藏消息窗口）
- WM_HOTKEY 消息循环置事件（零阻塞）
- 看门狗（30 秒存活检测 + 2 分钟强制重注册）
- 重注册在热键线程内执行（避免跨线程调用 1408 错误）

web/
editor.html
负责：
- 编辑窗口结构（工作区栏 + 三栏 + 工具栏）
- 工具栏按钮为纯图标（📑目录 / 🕘历史 / 🛠️工具箱 / ⚙️设置，title 保留悬停提示；「▼」页签下拉按钮仅在溢出时出现）
- 底部右对齐保存区：💾「保存」（保存后隐藏窗口）/ ⟳「同步」（保存但窗口保持打开，保存中按钮旋转）+ 右下角滑入提示（#sync-toast，3 秒自动消失）
script.js
负责：
- 编排层：CodeMirror / Tab系统 / 图片粘贴 / 保存交互 / 历史重开
- 启动恢复（直接读取已保存页面，不弹恢复窗口）
storage.js
负责：
- 自动保存（2 秒 debounce）
- 30 秒保险保存
- 页面 API 封装（创建/恢复/关闭/重命名）
tab-manager.js
负责：
- Tab 渲染与状态圆点（已保存=绿色光晕 / 未保存=红色光晕 / 保存中=蓝色呼吸 / 失败=红色加粗）
- 关闭确认（删除/保存）/ 删除二次确认
js/layout.js
负责：
- 布局核心（mode="outline"|"history" 切换、工作区显隐与宽度、宽度应用、布局保存）
js/resize.js
负责：
- 拖拽调整宽度（工作区/编辑/预览/目录四栏）
js/outline.js
负责：
- 目录（章节大纲、点击跳转编辑区+预览区、光标移动高亮）
js/history.js
负责：
- 历史面板：按最后编辑时间分组渲染（今天/昨天/前天/日期）、文件名模糊搜索、点击重开
- 纯 UI，通过 init() 注入 api 与 onOpen
js/workspace.js
负责：
- 工作区资源管理器：栏显隐（走 Layout.setWorkspaceVisible 持久化）、文件夹增删、树加载
- 调用 pick_workspace_folder / add_workspace_folder / remove_workspace_folder / get_file_tree
- 文件右键菜单：复制文件名 / 复制完整路径 / 资源管理器显示 / VSCode 打开 / 复制副本 / 移动文件 / 重命名 / 删除（走 ContextMenu + file_ops API，成功后刷新树与历史）
- 目录右键菜单：复制目录名·路径 / 资源管理器显示 / 复制副本 / 移动文件夹 / 新建文件夹 / 新建文件 / 重命名 / 删除（无 VSCode）
- 移动弹窗：ContextMenu.moveDialog（可展开/收缩目录树，默认显示一二级，点击目录行即移动）
js/search.js
负责：
- 工作区全局搜索（Ctrl+H 聚焦输入框、300ms 防抖、结果按扩展名分组渲染、点击定位行）
- 请求 limit=500；空关键字 / Esc → Workspace.clearSearch() 恢复文件树
explorer.js（web/ 根目录，非 js/）
负责：
- 工作区资源管理器树渲染：懒加载逐层展开、名称/时间排序、展开/折叠全部、文件点击回调、refreshDir/refreshAll 局部刷新
- 纯 UI，数据由 workspace.js 注入 loadChildren 回调；点击 → openWorkspaceFile
- 文件行右键 → onFileContext(path, x, y)、目录行右键 → onDirContext(path, x, y) 回调（由 workspace.js 注入）
explorer.css（web/ 根目录）
负责：
- 资源管理器样式：树行 flex-wrap 布局、文件名省略号单行展示、层级缩进
- 右键菜单样式（.ctx-menu / .ctx-item / .ctx-item.danger / .ctx-icon / .ctx-label）与通用弹窗输入（.modal-input）
context-menu.js（web/ 根目录）
负责：
- ContextMenu.open(x, y, items, onPick)：通用右键菜单（fixed 定位、越界校正、点外部关闭、escapeHTML）
- renameDialog(title, current, onConfirm)：重命名输入弹窗（Enter 提交 / Esc 取消 / 自动聚焦全选）
- confirmDialog(title, text, onConfirm)：删除确认弹窗（danger 文案）
- moveDialog(dirs, currentPath, onPick)：移动弹窗（可展开/收缩的目录树，默认展开根显示一二级文件夹；行内 ▸/▾ 懒展开；点击目录行直接移动；搜索仅显示匹配目录及其祖先，匹配行高亮）
settings.html / settings.js / settings.css
负责：
- 设置窗口（默认保存地址修改，立即生效、重启保持）
tools.html / tools.js / tools.css
负责：
- 工具箱窗口（加载工具插件、拖动排序）
theme.css
主题变量。
style.css
布局样式。
禁止：
style.css直接写主题颜色。

tools/
工具插件目录。
每个工具独立目录：
例如：
tools/
└── clean_empty_lines/
    ├── config.json
    └── index.js
工具列表与排序：tools/tools.json

==================================================
六、核心功能规范
==================================================
一、四个独立窗口
窗口与热键（以 main.py WINDOW_DEFS 为准）：
1. Inbox Capture
快捷键：
Alt + S
保存：
inbox_file
Tab 子目录：
{default_save_path}\Inbox\
--------------------------------------------------
2. FlashNote Capture
快捷键：
Alt + E
保存：
flashnote_file
Tab 子目录：
{default_save_path}\FlashNote\
--------------------------------------------------
3. Daily Log
快捷键：
Alt + J
保存：
log_dir/yyyy-MM-dd 周X.md
Tab 子目录：
{default_save_path}\Log\
--------------------------------------------------
4. Capture
快捷键：
Alt + D
保存：
capture_file
Tab 子目录：
capture_file 所在目录（默认 D:\Obsidian\LeoDiary\A📥 收集（Capture）\）
要求：
四个窗口：
- 同时存在
- 独立运行
- 互不影响
- 独立编辑状态
关闭窗口：
隐藏窗口到托盘。
禁止退出程序。
托盘：
图标常驻，托盘图标双击默认弹出 Capture 窗口（菜单可打开任一窗口 / 工具箱 / 退出）。

==================================================
七、Markdown编辑器规范
==================================================
布局：
三栏：
左侧：
Markdown编辑器
中间：
实时预览
右侧：
第三栏（目录 or 历史）
要求：
- 行号
- Markdown高亮
- 折叠
- 双向同步滚动
同步规则：
编辑区点击：
↓
预览区定位
预览区点击：
↓
编辑区定位
实现：
data-line 行号映射。

==================================================
八、四栏布局与面板规范
==================================================
整体布局：
工作区资源管理器（最左侧，默认隐藏）+ 编辑 + 预览 + 第三栏。

工作区资源管理器：
- 入口：左上角窗口名称（brand，如「📥 My-Inbox」），点击显示/再次点击收起
- 宽度固定像素（workspace_width），拖拽 resizer-0 调整（160-400px 约束）
- 显示时其余三栏按 flex 比例瓜分剩余空间（宽度比例不变）
- 显隐与宽度走 layout_store 持久化

第三栏两种模式：
- outline（目录）
- history（历史）
切换：
顶部「📑 目录」/「🕘 历史」按钮。
再次点击：
收起/展开第三栏。
布局记忆：
- 宽度比例（editor/preview/outline）
- 第三栏可见性
- pane_mode
- workspace_visible / workspace_width
保存位置：
layout_store（config.json 的 layout 字段）。
新功能接入：
历史面板 HTML 容器已存在于 editor.html 的 #pane-outline 内，
后续第三栏新面板遵循：新增 body 容器 + layout.js 支持新 mode。

==================================================
八B、工作区资源管理器规范
==================================================
后端（workspace.py / file_tree.py / file_explorer.py / search_engine.py / file_ops.py）：
- workspace.json 存 %APPDATA%\Obsidian-upload\workspace.json
- 树懒加载：get_file_tree(path) 只返回直接子项，前端展开时再逐层请求
- 显示扩展名 explorer_exts（默认 .md/.txt/.ini/.json/.yaml/.yml/.tsc），隐藏目录 config.json 的 workspace_hidden_dirs（默认 .git/node_modules/__pycache__/dist/.obsidian/.trash）
- 排序：explorer_sort（name 名称 / time 时间），存 config.json layout.explorer_sort
- 搜索：search_workspace(keyword, limit) 遍历工作区，扩展名过滤 search_exts ∪ explorer_exts，
  逐行增量匹配（不整文件载入内存），2MB 以上文件跳过内容搜索
- 文件操作：file_ops（剪贴板复制 / 资源管理器显示 / VSCode 打开 / 重命名 / 复制副本 / 新建文件夹·文件 / 移动 / 删除到回收站），重命名·删除·移动同步 history（rename / remove_tree / move_path）
- 模块均不依赖 UI / 网络，可独立测试

前端（js/workspace.js / js/search.js / explorer.js / context-menu.js）：
- explorer.js：纯渲染（懒加载逐层展开、名称/时间排序、展开/折叠全部、文件·目录点击与右键回调、refreshDir/refreshAll 局部刷新），数据由 workspace.js 注入 loadChildren 回调
- workspace.js：栏显隐（Layout.setWorkspaceVisible 持久化）、文件夹增删、树加载、文件·目录右键菜单
- search.js：Ctrl+H 聚焦输入框、300ms 防抖、结果按扩展名分组渲染、点击 openWorkspaceFile(path, line)
- context-menu.js：通用右键菜单 + 重命名/删除确认弹窗 + 移动弹窗（可展开/收缩目录树，点击行直接移动）
- 点击文件/结果 → openWorkspaceFile：open_history_file 读取 + addExternalTab +
  命中行定位（view.dispatch selection + scrollEditorToLine + scrollPreviewToLine）

==================================================
九、多标签页规范
==================================================
每个窗口支持：
多个Tab。
规则：
新增：
点击 ＋
Tab名称：
默认：
Markdown第一行。
第一行变化：
同步更新Tab名称。
Tab过多：
必须支持：
- 横向滚动
- 鼠标滚轮切换
- 快速切换（下拉列表）
溢出折叠（script.js manageOverflow）：
- 从后往前折叠页签（优先保留当前激活页签），被折叠页签隐藏（.overflowed）
- 最后一个页签后显示「▼」下拉按钮（仅溢出时出现）
- 点击下拉按钮弹出清单，按页签顺序列出全部被折叠页签，点击任意一项快速切换（setActiveTab）
- 切换/重命名/窗口尺寸变化后重新计算（renderTabs / updateTabName / ResizeObserver）
新增按钮：
必须始终位于最后一个Tab后。
状态圆点：
- 已保存 = 绿色光晕
- 未保存 = 红色光晕
- 保存中 = 蓝色呼吸
- 失败 = 红色加粗

==================================================
十、图片上传规范
==================================================
图片来源：
Ctrl + V
流程：
剪贴板图片
↓
Pillow解析
↓
PicGo HTTP API
↓
Cloudflare R2
↓
返回URL
↓
插入Markdown
格式：
![](图片URL)
要求：
不保存本地图片。
PicGo字段：
files
返回：
result[0]
失败：
写入 upload_debug.log + 前端 toast 提示。

==================================================
十一、保存规则（双轨并存）
==================================================
两种保存并存，互不干扰：
1. Tab 独立文件（自动保存，防丢失缓存）
   位置：
   {default_save_path}\Inbox\
   {default_save_path}\FlashNote\
   {default_save_path}\Log\
   {capture_file 所在目录（Capture，默认 D:\Obsidian\LeoDiary\A📥 收集（Capture）\）}
   规则：
   - 编辑变化 → 2 秒 debounce 覆盖写入
   - 每 30 秒保险保存全部页面
   - 覆盖写，不追加
   - 首行标题变化 → 1200ms debounce 自动重命名文件
   - 元数据记录：pages.json（%APPDATA%\Obsidian-upload\pages.json）
2. 聚合文件（保存按钮 / 日志）
   统一：
   storage.save_note()
   格式：
   #### yyyy-MM-dd HH:mm:ss
   正文
   ---
   保存方式：
   追加。
   禁止：
   覆盖旧内容。
   Inbox → inbox_file（默认 D:\Obsidian\LeoDiary\My-Inbox.md）
   FlashNote → flashnote_file（默认 D:\Obsidian\LeoDiary\🧠 FlashNote.md）
   Daily Log → log_dir/yyyy-MM-dd 周X.md
   Capture → capture_file（默认 D:\Obsidian\LeoDiary\A📥 收集（Capture）\Capture.md）
点「保存」按钮 = 立即保存 Tab 文件 + 追加聚合文件。
自动保存不得触发聚合追加。
启动时直接读取已保存页面（不弹恢复窗口，页面本就已保存）。
退出程序时后台自动保存全部窗口所有页签内容。

==================================================
十二、历史记录规范
==================================================
后端（history.py）：
- 记录字段：name / path / type / created / last_edited / last_opened / seq
- record_open：打开文件时更新最后打开时间
- record_edit：自动/手动保存时更新最后编辑时间
- 同一路径去重，按最后编辑时间倒序返回
- 排序稳定性：seq 单调递增（同秒内保证后编辑在前）
- 磁盘上限 MAX_SAVED=500，查询默认 DEFAULT_LIMIT=100
- 2 秒 debounce 合并写盘，flush() 立即落盘（退出时调用）
- 退出程序时 main.py 必须调用 history_store.flush()
记录触发（main.py）：
- 打开文件 / 恢复页面 → record_open
- 创建页面 / 自动保存 / 手动保存 / 外部文件保存 → record_edit
- 关闭页签不删除记录
前端（js/history.js）：
- 按最后编辑时间分组：今天 / 昨天 / 前天 / 具体日期（YYYY年M月D日）
- 组内与组间均按时间倒序
- 条目仅显示文件名 + 类型徽标（路径/时间不展示）
- 搜索：文件名模糊匹配，200ms debounce，不区分大小写，结果同样分组
- 点击条目 → onOpen(path) → open_history_file → 新建外部 Tab 恢复编辑

==================================================
十三、文件关联规范
==================================================
支持扩展名：
config.json 的 associated_exts（内置默认 .md .txt .ini .json .yaml .yml .tsc）。
新增格式：
只需改 config.json，无需改代码。
打开流程：
EXE 带文件参数启动
↓
file_assoc 过滤受支持文件
↓
单实例已运行 → 写入 pending 队列 → 已运行实例消费打开
↓
未运行 → 直接打开（新页签，标题=首行非空或文件名）
页签类型：
外部文件（external），保存走 save_external_file。

==================================================
十四、布局记忆规范
==================================================
数据：
layout_store.py 负责读写（config.json layout 字段 或 layout.json）。
字段：
- editor_width / preview_width / outline_width（宽度比例）
- outline_visible（第三栏可见性）
- pane_mode（"outline" 目录 / "history" 历史）
- workspace_visible（工作区栏显隐，默认 false）
- workspace_width（工作区栏宽度，默认 220，范围 160-400）
- explorer_sort（资源树排序："name" 名称 / "time" 时间，默认 name）
前端：
layout.js 保存布局（节流防抖），启动时 layout_store 读取并应用。
规则：
- 拖动宽度、切换/收起第三栏、切换工作区栏后保存
- 重启后恢复上次布局

==================================================
十五、日志系统（每日日志）
==================================================
日志快捷键：
Alt + J
文件：
yyyy-MM-dd 周X.md
例如：
2026-08-01 周六.md
目录不存在：
自动创建。
追加格式：
2026-08-01 19:31:53
日志内容
---

==================================================
十六、工具箱系统
==================================================
入口：
工具箱按钮（🛠️）。
独立窗口：
1000×600。
功能：
加载工具插件。
每个工具包含：
- 图标
- 名称
- 描述
- 执行入口
支持：
- 拖动排序
- 保存顺序
- 图标大小调整
排序保存：
tools/tools.json

==================================================
十七、主题规范
==================================================
主题：
护眼浅色。
禁止：
纯黑背景。
颜色统一：
web/theme.css
示例：
背景：
#F7F6F2
编辑区：
#FAF9F5
预览区：
#FFFFFF
字体：
编辑：
16px
预览：
16px
行高：
1.6
未来支持：
Dark Mode

==================================================
十八、快捷键稳定性要求
==================================================
快捷键：
Alt+S（Inbox）
Alt+E（FlashNote）
Alt+J（Daily Log）
Alt+D（Capture）
要求：
长期稳定运行。
架构：
RegisterHotKey 系统级热键
↓
隐藏消息窗口（独立线程）
↓
WM_HOTKEY → 置 threading.Event（零阻塞）
↓
工作线程处理 → 窗口显示/置顶/聚焦
↓
看门狗（30 秒存活检测 + 2 分钟强制重注册）
要求：
- 回调禁止阻塞
- 重注册必须在热键线程内执行（WM_APP_REBIND 消息触发），
  禁止跨线程直接调用 RegisterHotKey/UnregisterHotKey（会 1408）
- 自动恢复
- 状态检测
- 错误日志（shortcut_error.log）
日志：
shortcut_error.log

==================================================
十九、日志系统规范
==================================================
app.log
位置：
%APPDATA%\Obsidian-upload\app.log
记录：
- 启动
- 窗口
- 热键
- 上传
- 保存
shortcut_error.log
位置：
%APPDATA%\Obsidian-upload\shortcut_error.log
记录：
- 热键异常
- 时间
- 错误
- 当前状态
upload_debug.log
位置：
%APPDATA%\Obsidian-upload\upload_debug.log
记录：
图片上传过程。

==================================================
二十、开发流程
==================================================
新增功能：
第一步：
分析功能边界。
明确：
- 功能职责
- 输入输出
- 与哪些模块交互
- 是否已有能力可复用
--------------------------------------------------
第二步：
创建独立模块。
禁止：
直接修改大文件。
--------------------------------------------------
第三步：
实现模块内部逻辑。
--------------------------------------------------
第四步：
增加接口连接。
--------------------------------------------------
第五步：
单独测试。
--------------------------------------------------
第六步：
验证：
- 不影响旧功能
- 日志正常
- 配置正常
- 打包正常

==================================================
二十一、代码修改原则
==================================================
修改已有功能：
优先：
新增模块。
其次：
扩展已有模块。
禁止：
为了一个小需求：
- 大规模重构
- 删除旧代码
- 修改公共接口

==================================================
二十二、最终目标
==================================================
LeoDiary Capture 最终必须达到：
- 一个功能一个模块
- 一个组件一个文件
- UI和业务完全分离
- 配置统一管理
- 工具插件化
- 功能可插拔
- 稳定运行
- 易维护
- 可长期扩展
所有未来AI开发任务必须严格遵守以上规范。

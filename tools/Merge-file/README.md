# 文件合并工具 (MD Merger)

一个基于 Python + Tkinter 的桌面小工具，支持将多个 **txt / md / docx** 文件拖拽合并为一个 Markdown 文件。

## ✨ 功能特性

- 🖱 **拖拽添加**：直接把文件/文件夹拖进窗口即可添加（需安装 tkinterdnd2）
- 📁 **按钮添加文件**：通过对话框选择多个文件
- 📂 **添加文件夹**：选择文件夹，自动递归扫描所有子文件夹中的支持文件，按类型分组展示，支持全选/反选/多选勾选
- 🔢 **顺序调整**：支持上移/下移调整合并顺序
- 🗑 **灵活管理**：移除选中、清空列表
- 📝 **多格式支持**：
  - `.txt` / `.md` / `.markdown` → 直接读取
  - `.docx` → 自动转换为 Markdown（标题、段落、表格）
- 💾 **一键导出**：合并为单个 `.md` 文件
- ☁️ **上传到 GitHub**：直接上传列表中的所有文件到 GitHub
- 🔄 **合并同步GitHub**：无需导出本地文件，合并后直接上传到 GitHub
- 🌐 **跨平台**：Windows / macOS / Linux 均可运行

## 🚀 快速开始

### 1. 安装依赖

```bash
# 基础运行（无拖拽，只能按钮添加）
# Python 自带 tkinter，零依赖即可运行

# 完整功能（推荐）
pip install tkinterdnd2 python-docx pygithub
```

| 依赖包 | 作用 | 是否必须 |
|--------|------|----------|
| `tkinter` | GUI 界面 | Python 自带，无需安装 |
| `tkinterdnd2` | 拖拽文件支持 | 可选，不装也能用按钮添加 |
| `python-docx` | 读取 Word (.docx) 文件 | 可选，不装则跳过 docx |
| `pygithub` | 上传文件到 GitHub | 可选，不装则无法使用上传功能 |

### 2. 运行

```bash
python md_merger.py
```

## 📖 使用方法

1. **添加文件**：把文件拖进窗口，或点「➕ 添加文件」
   - 拖拽整个文件夹时，会自动递归扫描里面所有支持的文件
2. **调整顺序**：选中文件，点「⬆ 上移」或「⬇ 下移」
3. **移除文件**：选中后点「🗑 移除选中」，或「🧹 清空列表」全部清空
4. **合并导出**：点「🚀 合并导出」，选择保存位置即可

### 合并规则

- 每个文件前自动加上 `## 序号.文件名` 标题
- 文件之间用 `---` 分隔线隔开
- 输出编码为 UTF-8
- Word 文档中的标题样式（Heading 1/2/3）会转为对应的 `#` / `##` / `###`
- Word 表格会转为 Markdown 表格

### 上传到 GitHub

#### 方式一：上传列表中的所有文件（☁️ 上传到 GitHub）

直接上传列表中的每个文件到 GitHub，不需要先合并。

1. 添加文件到列表
2. 点击「☁️ 上传到 GitHub」按钮
3. 输入 GitHub Token、仓库名、分支名
4. 点击「上传」，显示成功/失败数量，最后一个文件的 raw 链接会复制到剪贴板

#### 方式二：合并同步GitHub（🔄 合并同步GitHub）

将列表中的文件合并为一个 Markdown 文件后直接上传，无需保存到本地。

1. 添加文件到列表
2. 点击「🔄 合并同步GitHub」按钮
3. 输入输出文件名（默认 `merged_output.md`）、GitHub Token、仓库名、分支名
4. 点击「合并上传」，成功后 raw 链接会自动复制到剪贴板

**示例 raw 链接格式**：
```
https://raw.githubusercontent.com/leokou/leoshow/refs/heads/main/merged_output.md
```

## 📦 打包成 EXE（可选）

如果想打包成独立的 `.exe` 给别人用：

```bash
pip install pyinstaller

# 单文件、无控制台窗口
pyinstaller -F -w md_merger.py

# 加图标（可选）
pyinstaller -F -w -i icon.ico md_merger.py
```

打包完成后，exe 在 `dist/` 目录下。

## ❓ 常见问题

**Q: 拖拽没反应？**
A: 没装 `tkinterdnd2`，执行 `pip install tkinterdnd2` 后重启即可。

**Q: Word 文件读不出来？**
A: 需要 `python-docx`，执行 `pip install python-docx`。

**Q: 中文乱码？**
A: 程序会自动尝试 UTF-8 / GBK 等多种编码，基本不会乱码。如仍有问题请反馈。

**Q: 支持 .doc 格式吗？**
A: 不支持旧版 `.doc`，只支持 `.docx`。`.doc` 需要先用 Word 另存为 `.docx`。

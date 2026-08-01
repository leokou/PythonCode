# projects/leodiarycode — LeoDiary 工具链

Python 项目，管理 LeoDiary Obsidian 知识库的自动化工具体系。

## 技术栈

- Python 3.14+
- 仅标准库，无第三方依赖

## 目录结构

```
leodiarycode/
├── scripts/               # CLI 入口（Obsidian EXE 插件）
│   ├── obsidian_common.py      # 公共常量/工具（VAULT_ROOT、跳过规则等）
│   ├── index-updater.py        # 目录索引更新
│   ├── home-to-mulu-sync.py    # Home→目录同步
│   ├── mulu-to-home-sync.py    # 目录→Home同步
│   └── rename-check.py         # 文件名标题检查
├── config/                # 配置文件
├── docs/
├── tmp/                   # PyInstaller 构建临时目录
├── README.md
└── CLAUDE.md
```

**v3.0 项目定位**：9 个 Skill 均为纯 AI 执行，运行时不依赖本项目。本项目仅提供 `scripts/` 下 4 个 EXE 打包脚本，供 Obsidian EXE Launcher 插件调用。AI 索引构建工具位于 `D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py`（vault 内），不在本项目中。

## import 规则

scripts/ 中的脚本通过 `sys.path.insert(0, os.path.dirname(__file__))` 添加自身目录到搜索路径，导入同目录的 `scripts/obsidian_common.py`。

```python
# scripts 中实际使用：
sys.path.insert(0, os.path.dirname(__file__))
from obsidian_common import ...
```

## 运行命令

```bash
cd D:\Python\projects\leodiarycode
# 目录索引更新
python "scripts/index-updater.py"
# Home 同步
python "scripts/home-to-mulu-sync.py"
# 目录同步
python "scripts/mulu-to-home-sync.py"
# 文件名检查
python "scripts/rename-check.py"
# AI 索引全量重建（v3.0，位于 vault tools/）
python D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py
```

## 打包 EXE

EXE 统一输出到 `D:\Python\dist`（Obsidian EXE Launcher 插件读取路径）。

```bash
cd D:\Python\projects\leodiarycode
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "index-updater" "scripts/index-updater.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "home-to-mulu-sync" "scripts/home-to-mulu-sync.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "mulu-to-home-sync" "scripts/mulu-to-home-sync.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "rename-check" "scripts/rename-check.py"
```

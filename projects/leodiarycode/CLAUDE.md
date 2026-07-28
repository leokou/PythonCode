# projects/leodiarycode — LeoDiary 工具链

Python 项目，管理 LeoDiary Obsidian 知识库的自动化工具体系。

## 技术栈

- Python 3.14+
- 仅标准库，无第三方依赖

## 目录结构

```
leodiarycode/
├── src/                   # importable 模块
│   ├── obsidian_common.py      # 公共常量/工具（VAULT_ROOT、跳过规则等）
│   ├── obsidian_skill_utils.py # 30+ 通用命令，所有 Skill 共用
│   ├── frontmatter_enrich.py   # 批量补全元数据
│   ├── health_check.py         # AI 检索层健康检查（49项）
│   ├── check_ai_dir.py         # AI_DIR 检查
│   ├── check_chip_links.py     # Chip 链接检查
│   └── check_tasks.py          # Task 检查
├── scripts/               # CLI 入口
│   ├── ai_index_builder.py          # AI_INDEX 构建（11命令）
│   ├── Obsidian - index_updater.py  # 索引更新
│   ├── Obsidian - Home修改同步移动文件.py  # Home→目录同步
│   ├── Obsidian - 目录修改同步home.py      # 目录→Home同步
│   ├── Obsidian - renamepy.py       # 文件名标题检查
│   ├── Obsidian -备份笔记.py         # 笔记备份
│   └── Obsidian -备份python代码.py   # 代码备份
├── lib/                   # leo-os-tools 子包
│   ├── leo_common.py
│   ├── lint.py
│   └── validate.py
├── tests/
│   ├── LD-DVA_test_runner.py
│   └── LD-DVA_test_report.json
├── tmp/                   # 构建临时文件（gitignored）
│   ├── build/             # PyInstaller 工作目录
│   └── spec/              # PyInstaller .spec 文件
├── docs/
├── README.md
└── CLAUDE.md
```

## import 规则

scripts/ 中的脚本通过 `sys.path.insert` 自动添加 `../src` 到搜索路径，可直接 `from obsidian_common import ...`。

```python
# scripts 中自动已加：
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
```

如需从项目根运行模块：

```bash
python -m src.obsidian_skill_utils <command>
```

## 运行命令

```bash
cd D:\Python\projects\leodiarycode

# 索引更新
python scripts/Obsidian - index_updater.py

# Home 同步
python "scripts/Obsidian - Home修改同步移动文件.py"

# 目录同步
python "scripts/Obsidian - 目录修改同步home.py"

# 文件名检查
python "scripts/Obsidian - renamepy.py"

# 备份
python "scripts/Obsidian -备份笔记.py"
python "scripts/Obsidian -备份python代码.py"

# AI_INDEX
python scripts/ai_index_builder.py rebuild|incremental|status|health

# Skill 一致性检查
python src/obsidian_skill_utils.py skill-health-check "C:\Users\leokou\.claude\skills\Obsidian" "D:\Obsidian\LeoDiary"
```

## 打包 EXE

EXE 统一输出到 `D:\Python\dist`（Obsidian EXE Launcher 插件读取路径）。

```bash
cd D:\Python\projects\leodiarycode

pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian - index_updater" "scripts/Obsidian - index_updater.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian - Home修改同步移动文件" "scripts/Obsidian - Home修改同步移动文件.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian - 目录修改同步home" "scripts/Obsidian - 目录修改同步home.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian - renamepy" "scripts/Obsidian - renamepy.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian -备份笔记" "scripts/Obsidian -备份笔记.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "Obsidian -备份python代码" "scripts/Obsidian -备份python代码.py"
```

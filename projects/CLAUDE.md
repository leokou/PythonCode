# projects/ — 项目目录 AI 规则

> 本文件是 `D:\Python\projects\` 目录级 AI 规则。上级规则见 [D:\Python\CLAUDE.md](file:///D:/Python/CLAUDE.md)，子项目规则见各自 CLAUDE.md。

## 子项目速查

| 项目 | 入口 | 核心约定 |
|------|------|---------|
| [leodiarycode](./leodiarycode/CLAUDE.md) | `scripts/` 4 个 EXE 打包脚本 | 仅标准库；`src/` v3.0 已废弃 |
| [obsidian-exe-launcher](./obsidian-exe-launcher/CLAUDE.md) | `src/main.ts` 的 `EXE_CONFIGS` | esbuild 构建；vault 部署路径固定 |

## 共同约定

### 路径常量（已知，勿再询问）

- **vault 路径**：`D:\Obsidian\LeoDiary`
- **EXE 输出目录**：`D:\Python\dist`（Obsidian EXE Launcher 默认读取）
- **Obsidian 插件目录**：`D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\`
- **Skill 权威源**：`C:\Users\leokou\.claude\skills\Obsidian\`
- **v3.0 AI 索引工具**：`D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py`（位于 vault 内，不在 projects/ 下）

### v3.0 架构背景（务必知悉）

LeoDiary 知识库 v3.0 起 9 个 Skill 均为纯 AI 执行（Read/Grep/Glob/LS），不再依赖 `D:\Python\projects\leodiarycode\src\` 运行时：
- `obsidian_skill_utils.py`（旧体系 30+ 命令）已废弃
- `health_check.py` / `check_*.py` 已废弃
- v3.0 Python 工具：`tools/rebuild-ai-index.py`（索引全量重建）+ `tools/health-check-verify.py`（跨文件一致性批量校验）

`leodiarycode` 当前实际价值仅剩 `scripts/` 下 4 个 EXE 打包脚本，供 Obsidian EXE Launcher 插件调用。

## 常用命令

### leodiarycode（仅 4 个 EXE 脚本在用）

```bash
cd D:\Python\projects\leodiarycode

# 运行脚本（开发时）
python "scripts/index-updater.py"
python "scripts/home-to-mulu-sync.py"
python "scripts/mulu-to-home-sync.py"
python "scripts/rename-check.py"

# 打包 EXE（输出到 D:\Python\dist）
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "index-updater" "scripts/index-updater.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "home-to-mulu-sync" "scripts/home-to-mulu-sync.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "mulu-to-home-sync" "scripts/mulu-to-home-sync.py"
pyinstaller --onefile --distpath "D:\Python\dist" --workpath tmp\build --specpath tmp\spec --name "rename-check" "scripts/rename-check.py"
```

### obsidian-exe-launcher

```bash
cd D:\Python\projects\obsidian-exe-launcher

# 构建
npm install
npm run build

# 部署到 Obsidian vault（覆盖 main.js / manifest.json / styles.css）
Copy-Item "main.js" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\main.js" -Force
Copy-Item "manifest.json" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\manifest.json" -Force
Copy-Item "styles.css" "D:\Obsidian\LeoDiary\.obsidian\plugins\obsidian-exe-launcher\styles.css" -Force
```

部署后需在 Obsidian 中重新加载插件（设置 → 第三方插件 → 关闭再打开）。

### v3.0 AI 索引重建（vault 内）

```bash
python D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py           # 全量重建
python D:\Obsidian\LeoDiary\tools\rebuild-ai-index.py --status  # 查看状态
```

## 修改红线

- **leodiarycode/src/ 下废弃模块**：v3.0 不再维护，不要新增功能；如需修改 Skill 行为，请改 `C:\Users\leokou\.claude\skills\Obsidian\*\SKILL.md`
- **obsidian-exe-launcher/main.js**：构建产物，不要直接编辑；改 `src/main.ts` 后 `npm run build`
- **vault 内 `.obsidian/`**：被 gitignore，部署文件不进 vault git；git 同步仅针对源仓库 `D:\Python`

## 三层 CLAUDE 体系

```
D:\Python\CLAUDE.md                          工作区规则（项目容器、命名、编码）
    └── D:\Python\projects\CLAUDE.md         本文件（项目目录总览）
        └── D:\Python\projects\<项目>\CLAUDE.md   项目规则（技术栈、import、运行方式）
```

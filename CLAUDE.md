# D:\Python - AI 速查手册

> 工作区级规则。项目级规则见各 `projects/*/CLAUDE.md`。·

## 1. 目录结构

```
D:\Python/
├── projects/              # 正式项目（独立 Git）
│   ├── leodiarycode/      # LeoDiary 工具链（Python）
│   └── obsidian-exe-launcher/  # Obsidian 插件（TypeScript）
├── tools/                 # 独立工具
│   ├── skill-sync/
│   ├── chrome-go/
│   └── logseq-cleanup/
├── experiments/           # 实验验证
├── archive/               # 历史归档
└── tmp/                   # 临时目录
```

## 2. CLAUDE.md 三层体系

| 层级 | 文件 | 职责 |
|------|------|------|
| 工作区 | `D:\Python\CLAUDE.md` | 项目容器、命名、编码、通用规则 |
| 项目 | `projects/*/CLAUDE.md` | 技术栈、import 方式、运行命令 |
| 目录 | （子目录自有规则） | 具体模块分工 |

## 3. 项目速查

### projects/leodiarycode（Python）

核心目录结构：

```
leodiarycode/
├── src/                   # importable 模块
│   ├── obsidian_common.py
│   ├── obsidian_skill_utils.py
│   ├── frontmatter_enrich.py
│   ├── health_check.py
│   │   ├── scripts/               # CLI 入口
│   │   │   ├── ai_index_builder_v2.py    # ⭐ AI 检索 Builder（Router/Cache/Search/Domain/Status/Rebuild/Incremental/Health）
│   │   │   ├── batch_skill_test.py       # ⭐ 30 查询批量测试脚本
│   │   │   ├── ai_retrieval_healthcheck.py  # ⭐ 100+ 项 AI 检索层真实检测（LD-DVA Final 全链路）
│   ├── ai_index_builder.py
│   ├── Obsidian - index_updater.py
│   ├── Obsidian - Home修改同步移动文件.py
│   ├── Obsidian - 目录修改同步home.py
│   ├── Obsidian - renamepy.py
│   ├── Obsidian -备份笔记.py
│   └── Obsidian -备份python代码.py
├── lib/                   # leo-os-tools 子包
├── tests/
└── docs/
```

### projects/obsidian-exe-launcher（TypeScript）

```
obsidian-exe-launcher/
├── src/main.ts
├── manifest.json
├── package.json
├── esbuild.config.mjs
└── main.js
```

## 4. 独立工具（tools/）

| 工具 | 路径 |
|------|------|
| Skill 同步 | `tools/skill-sync/claude目录skill同步到其他agentcode.py` |
| 代理节点爬取 | `tools/chrome-go/ChromeGo - 节点爬取脚本 @ 代理节点下载.py` |
| Logseq 附件清理 | `tools/logseq-cleanup/Logseq - 附件清理脚本 @ 清理无用文件.py` |

## 5. 历史归档（archive/）

原 `_archive_oneoff/` 内容迁移至此。不再维护，参考用。

## 6. Python 脚本 vs Obsidian Skills 分工（防死循环）

> Skills 位于 `C:\Users\leokou\.claude\skills\`。

| 维度 | Python 脚本 | Obsidian Skills |
|------|------------|-----------------|
| 驱动方式 | 手动运行 / EXE 点击 | AI 自然语言调用 |
| 核心能力 | 结构维护、批量操作、快、不用模型 | 内容理解、分类、摘要、语义判断 |
| 处理 🧩目录文件 | 仅删除失效链接 | 分类区域、✍️摘要、frontmatter、重排 |
| 处理 📖目录 索引.md | `目录结构树` + `统计摘要` | `按领域分组`（分类+✍️摘要+状态） |
| 处理文件标题 | 无 frontmatter 文件的标题修正 | 有 frontmatter 文件的标题（Python 跳过） |

**核心原则**：Python 只做行级增删，不重排、不分类、不加摘要；Skill 做内容加工，可以随意重排。

## 7. 常用运行命令

```bash
# AI 检索 - Router 分类
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py router "查询内容"

# AI 检索 - 搜索
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py search "查询内容" --top 5

# AI 检索 - 索引状态
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py status

# AI 检索 - 全量重建（重建 .ai-index/ 目录）
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py rebuild

# AI 检索 - 增量更新（Pipeline Step 6 触发）
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py incremental

# AI 检索 - 批量测试（30 查询）
python D:\Python\projects\leodiarycode\scripts\batch_skill_test.py

# AI 检索 - 全链路健康检查（100+ 项 AI 检索层真实检测）
python D:\Python\projects\leodiarycode\scripts\ai_retrieval_healthcheck.py

# 索引更新
python D:\Python\projects\leodiarycode\scripts\Obsidian\ -\ index_updater.py

# Skill 一致性检查
python D:\Python\projects\leodiarycode\src\obsidian_skill_utils.py skill-health-check "C:\Users\leokou\.claude\skills\Obsidian" "D:\Obsidian\LeoDiary"

# 项目级健康检查（320+ 项：140+ Python + 100+ AI 检索真实检测 + 140+ Runtime Reality Verification + 30 查询验证 + 30 三要素验证 + 10 语义模拟）
python D:\Python\projects\leodiarycode\src\obsidian_skill_utils.py health-check-all "D:\Obsidian\LeoDiary" "C:\Users\leokou\.claude\skills\Obsidian" "D:\Python\projects\leodiarycode"
```

## 8. 打包 EXE

在 `D:\Python\projects\leodiarycode` 下运行：

```bash
pyinstaller --onefile --name "工具名" "scripts/脚本名.py"
```

EXE 输出到 `dist/`。

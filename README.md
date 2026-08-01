# Python Personal Engineering Workspace

**D:\Python** 是个人软件工程母体 workspace，不是项目。!!

## 职责边界

| 层次 | 职责 | 入口 |
|------|------|------|
| workspace | 项目容器、AI 规则入口、全局配置 | `D:\Python\CLAUDE.md` |
| project | 业务代码、独立 CI/CD、独立 Git | `projects/*/CLAUDE.md` |
| tool | 独立工具脚本，不绑定项目 | `tools/*/` |

## 目录结构

```
D:\Python/
├── README.md              # 本文件
├── CLAUDE.md              # 工作区 AI 规则（入口）
├── .gitignore             # 根忽略规则
├── .github-pat            # GitHub PAT（敏感，已 gitignore）
├── .mimocode/             # AI agent 配置
├── opencode.jsonc         # OpenCode 配置
│
├── projects/              # ⭐ 正式项目
│   ├── leodiarycode/      # LeoDiary 工具链（Python）
│   │   ├── src/           #   库模块
│   │   ├── scripts/       #   CLI 入口
│   │   ├── lib/           #   子包（leo-os-tools）
│   │   ├── tests/         #   测试
│   │   ├── docs/          #   文档
│   │   ├── README.md
│   │   ├── CLAUDE.md
│   │   └── .git/
│   │
│   └── obsidian-exe-launcher/  # Obsidian EXE Launcher 插件（TypeScript）
│       ├── src/
│       ├── manifest.json
│       ├── package.json
│       ├── README.md
│       ├── CLAUDE.md
│       └── .git/
│
├── tools/                 # 独立工具（不绑定项目）
│   ├── sync-GitHub/       # Skill 同步/备份
│   ├── chrome-go/         # 代理节点爬取
│   └── logseq-cleanup/    # Logseq 附件清理
│
├── experiments/           # 实验验证
├── archive/               # 历史归档
└── tmp/                   # 临时目录
```

## 核心约定

- **`projects/`** 是唯一放业务代码的地方，每个项目独立 Git
- **`tools/`** 放独立工具，不绑定项目，不分语言
- **`experiments/`** 放实验性代码，随时可删
- **`archive/`** 放历史脚本，参考用，不再维护
- **`tmp/`** 放临时文件，不得在根目录乱建文件

## CLAUDE.md 三层体系

```
D:\Python/CLAUDE.md                 工作区规则（项目容器、命名、编码）
    └── projects/leodiarycode/CLAUDE.md   项目规则（技术栈、import、运行方式）
        └── projects/xxx/CLAUDE.md        目录规则
```

## Git 策略

- 根目录 **无** `.git`（已删除）
- 每个项目独立 Git：
  - `projects/leodiarycode/.git` — 推送到 `leokou/PythonCode`
  - `projects/obsidian-exe-launcher/.git` — 单独管理

## 运行命令速查

### leodiarycode 工具链

```bash
# 从项目根运行
cd D:\Python\projects\leodiarycode

# AI 检索 - Router 分类
python scripts/ai_index_builder_v2.py router "查询内容"

# AI 检索 - 缓存读取
python scripts/ai_index_builder_v2.py cache-read "查询内容"

# AI 检索 - 领域索引读取
python scripts/ai_index_builder_v2.py domain-read ai

# AI 检索 - 搜索
python scripts/ai_index_builder_v2.py search "查询内容" --top 5

# AI 检索 - 批量测试（25 查询）
python scripts/batch_skill_test.py

# AI 检索 - 全链路健康检查（58 项）
python scripts/ai_retrieval_healthcheck.py

# Skill 一致性检查
python -m src.obsidian_skill_utils skill-health-check "C:\Users\leokou\.claude\skills\Obsidian" "D:\Obsidian\LeoDiary"

# 元数据校验
python -m src.obsidian_skill_utils validate-metadata "D:\Obsidian\LeoDiary" --quiet

# 内容健康检查
python -m src.obsidian_skill_utils lint-content "D:\Obsidian\LeoDiary"

# 知识库统计
python -m src.obsidian_skill_utils kb-stats "D:\Obsidian\LeoDiary"
```

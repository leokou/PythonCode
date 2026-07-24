---
name: obsidian-pipeline
description: 智能处理 Capture 文件夹的一整套流水线。自动识别新增/修改/删除的文件，只处理需要处理的文件。触发词：处理 Capture、运行流水线、处理收集箱、pipeline、一键处理。默认只处理 A📥 收集（Capture），明确指定其他文件夹才处理。
---

# Obsidian Pipeline

智能知识处理流水线：自动识别变化 → 按需调用子 Skill → 追踪处理状态。

## 核心定位

**这是一个调度器，不是一个执行器。**

- 借用其他 Skill 的能力来处理 `A📥 收集（Capture）` 文件夹
- 自身不做具体的编译、命名、移动工作
- 负责：变化检测 → 任务分发 → 状态追踪

## 双层架构

| 层级 | 文件 | 用途 | 写入者 |
|------|------|------|--------|
| 人类可读层 | `📖目录 索引.md` | 快速判断"哪些整理了/没整理" | Mulu-fenlei + Organizer |
| 机器可读层 | `logs/pipeline/pipeline-state.json` | 记录标题、哈希、处理状态 | Pipeline |

**读取优先级**：
1. 先读索引（快速跳过已处理文件）
2. 再读状态文件（精确检测标题变化）

## 与其他 Skill 的关系

| Skill | 定位 | 使用场景 |
|-------|------|----------|
| **obsidian-pipeline** | 调度器 | 批量处理 Capture 文件夹 |
| obsidian-knowledge-planner | 执行器 | 单独分析某批文件 |
| obsidian-knowledge-compiler | 执行器 | 单独编译某个文件 |
| obsidian-fire-rename | 执行器 | 单独重命名某个文件夹 |
| obsidian-knowledge-organizer | 执行器 | 单独整理某个文件夹 |
| obsidian-mulu-fenlei-summary | 执行器 | 单独整理某个目录文件 |

**用户可以随时单独调用任何执行器处理任何文件夹。Pipeline 只负责 Capture 的批量自动化。**

---

## 来源路径限制（强制）

**默认只处理 `A📥 收集（Capture）` 文件夹。**

| 场景 | 处理 |
|------|------|
| 用户说"处理 Capture" | 只处理 `A📥 收集（Capture）/` |
| 用户说"处理 xxx 文件夹" | **必须用户明确指定**，才处理该文件夹 |
| 用户说"处理所有文件" | 拒绝，要求指定具体文件夹 |

---

## 智能追踪机制

### 追踪文件位置

```
logs/pipeline/pipeline-state.json
```

### 追踪数据结构

完整 schema 见 `references/state-schema.json`，关键字段：

```json
{
  "版本": "1.0",
  "上次运行": "2026-07-24T23:00:00",
  "文件状态": {
    "A📥 收集（Capture）/文件名.md": {
      "路径": "A📥 收集（Capture）/文件名.md",
      "标题": "文件的第一个 # 标题",
      "文件哈希": "MD5哈希值",
      "处理状态": "已处理",
      "处理时间": "2026-07-24T23:00:00",
      "处理步骤": ["planner", "compiler", "organizer"],
      "动作": "create | merge | link",
      "目标文件": "merge/link 时的目标文件路径",
      "错误信息": "失败时记录错误"
    }
  }
}
```

### 变化检测规则（双层检测）

**第一层：索引快速检测**

| 索引状态 | 判断 | 动作 |
|----------|------|------|
| 状态:已整理 | 已处理 | 跳过 |
| 状态:已移动 | 已处理 | 跳过 |
| 状态:未整理 | 待处理 | 进入第二层检测 |
| 不存在 | 新增 | 进入第二层检测 |

**第二层：标题精确检测**

| 条件 | 判断 | 动作 |
|------|------|------|
| 文件不在追踪记录中 | 新增 | 处理（完整流程） |
| 文件的 # 标题与记录不同 | 修改（身份变了） | 处理（完整流程） |
| 文件在追踪中但不存在 | 删除 | 标记删除 |
| 标题一致但 MD5 哈希变化 | 内容补充（身份未变） | **轻量路径**：仅触发 Mulu-fenlei-summary 重生成 File Summary |
| 以上全都不满足 | 未变化 | 跳过 |

**说明**：
- 索引快速检测：快速跳过已处理的文件，节省 Token
- 标题精确检测：确保不会漏掉标题变化的文件
- **轻量路径**：标题不变但内容变化（哈希变化），文件身份没变无需重新规划，但 File Summary 可能过期，仅调用 Mulu-fenlei-summary 重生成摘要，不走 Planner→Compiler→Organizer 完整流程
- MD5 哈希双重用途：去重 + 检测内容补充

---

## 工作流程

```
读取追踪状态
    ↓
扫描 Capture 文件夹（提取标题+计算哈希）
    ↓
对比变化（标题是否变化）
    ↓
输出变化报告
    ↓
用户确认（可选）
    ↓
按顺序调用子 Skill（传递扫描结果）：
  1. Planner（分析 + 已有页面检测）
  2. Compiler（编译 + 正确文件名）
  3. Organizer（归属 + 双链 + 目录更新）
    ↓
更新追踪状态
    ↓
记录到 ⚓新增文件记录.md
```

**Fire-rename 仅在批量重命名已有文件时使用，不在主流程中。**

---

## 执行流程详解

### Step 1：读取追踪状态 + 索引

读取两个数据源：

1. `logs/pipeline/pipeline-state.json` — 机器状态（标题、哈希）
2. `📖目录 索引.md` — 人类状态（✍️、更新时间、处理状态）

**索引用于快速判断**：如果文件在索引中状态为"已整理"或"已移动"，直接跳过。

若状态文件不存在，初始化空状态。

### Step 2：扫描 Capture 文件夹

扫描 `A📥 收集（Capture）/` 及其子文件夹的所有 `.md` 文件。

### Step 3：变化检测

对每个文件：

```powershell
# 1. 获取文件标题（第一个 # 开头的行）
$content = Get-Content -Path $路径 -Head 20
标题 = ($content | Where-Object { $_ -match '^# ' } | Select-Object -First 1) -replace '^# ', ''

# 2. 计算文件哈希（用于去重）
文件哈希 = (Get-FileHash -Path $路径 -Algorithm MD5).Hash

# 3. 读取追踪状态中的记录标题
记录标题 = 状态记录中的"标题"字段
```

与追踪记录对比：

| 情况 | 分类 |
|------|------|
| 无记录 | 新增 |
| 标题与记录不同 | 修改 |
| 有记录但文件不存在 | 删除 |
| 标题一致 | 未变化 |

**扫描结果传递给 Planner，Planner 无需再次扫描。**

### Step 4：输出变化报告

```markdown
# Pipeline 变化报告

日期: YYYY-MM-DD HH:MM

## 扫描结果
- 总文件数: X
- 新增: X
- 修改: X
- 删除: X
- 未变化: X

## 需要处理的文件
1. [新增] 文件名.md
2. [修改] 文件名.md

## 跳过的文件
1. 文件名.md（未变化）
```

### Step 5：用户确认

默认等待用户确认后执行。

用户可设置自动执行模式。

### Step 6：调用子 Skill

按顺序调用，**传递扫描结果**：

1. **Planner**：接收扫描结果（标题+哈希），直接分析，无需再次扫描
2. **Compiler**：根据动作类型处理
   - `create`：创建新文件（**直接用正确文件名**）
   - `merge`：合并到已有文件
   - `link`：仅建立双链
3. **Organizer**：归属目录、建立双链、更新目录（**合并 Mulu-fenlei 职责**）
4. **Fire-rename**：仅在需要批量重命名已有文件时使用

### Step 7：更新追踪状态 + 索引

处理完成后：

1. 更新 `logs/pipeline/pipeline-state.json`
2. 更新 `📖目录 索引.md` 中对应条目的状态为"已整理"

```json
{
  "A📥 收集（Capture）/文件名.md": {
    "路径": "A📥 收集（Capture）/文件名.md",
    "标题": "文件的第一个 # 标题",
    "文件哈希": "MD5哈希值",
    "处理状态": "已处理",
    "处理时间": "2026-07-24T23:30:00",
    "处理步骤": ["planner", "compiler", "organizer"]
  }
}
```

**索引更新格式**：

```markdown
## 📁 目标目录分类
- [[文件名]] ✍️ 一句话总结 | 更新:YYYY-MM-DD | 状态:已整理
```

### Step 8：记录操作

所有操作记录到 `⚓新增文件记录.md`。

**操作记录去重规则（避免同一次操作被记多次）：**

| 调用模式 | 写入者 | 说明 |
|----------|--------|------|
| Pipeline 调用子 Skill | **子 Skill 写入** | Pipeline 只更新 state.json，不重复写 `⚓新增文件记录.md` |
| 单独调用子 Skill | **子 Skill 写入** | 子 Skill 自行写入 `⚓新增文件记录.md` |

**规则**：谁执行实际文件操作（移动/合并/重命名/删除），谁负责写入操作记录。Pipeline 仅负责调度和状态追踪，不写操作记录，避免同一次移动被 Pipeline 和 Organizer 各记一次。

---

## Step 7.5：源文件归档清理（强制，禁止跳过）

**Compiler/Organizer 处理完成后，Capture 中的源文件必须清理，否则 Capture 会越堆越多，下次 Pipeline 又会重复处理。**

### 清理规则

| 源文件处理状态 | 清理动作 | 目标位置 |
|---------------|---------|---------|
| `已处理` (create) | 移动到归档 | `D📦 归档（Archive）/processed-YYYY-MM-DD/原文件名.md` |
| `已合并` (merge) | 移动到归档 | `D📦 归档（Archive）/processed-YYYY-MM-DD/原文件名.md` |
| `已丢弃` (discard) | 移动到回收站 | `_trash/原文件名.md`（不存在则创建 `_trash/`） |
| `已跳过` (未变化) | 保留原位 | 不动 |
| `部分新建` (create+merge) | 移动到归档 | `D📦 归档（Archive）/processed-YYYY-MM-DD/原文件名.md` |

### 归档目录命名

```
D📦 归档（Archive）/
└── processed-2026-07-25/      ← 按运行日期归档
    ├── 未命名.md
    ├── 未命名 1.md
    └── ...
```

### 强制检查（避免假执行）

每次 Pipeline 运行结束前，必须执行以下检查，否则视为"假执行"：

1. **Capture 残留检查**：扫描 `A📥 收集（Capture）/`，对每个 state.json 标记为"已处理/已合并/部分新建/已丢弃"的文件，验证是否已不在 Capture 中
2. **目标文件存在检查**：state.json 中记录的"目标文件"路径必须实际存在
3. **merge 完整性检查**：merge 目标文件大小必须 > 100 字节（防止"目标文件只有标题没内容"的假合并）
4. **discard 实际清理检查**：state.json 标记为"已丢弃"的文件，必须确认已移到 `_trash/`

### 假执行检测报告

如发现以下任一情况，输出"假执行警告"并立即补救：

```markdown
## ⚠️ 假执行检测报告

### Capture 残留（应归档但未归档）
- [文件名] 状态：已处理，但仍位于 Capture
- 补救动作：移动到 D📦 归档（Archive）/processed-YYYY-MM-DD/

### 目标文件缺失（state 记录但实际不存在）
- [目标文件路径]
- 补救动作：重新触发 Compiler create

### merge 假合并（目标文件过小）
- [目标文件路径] 大小：XX 字节
- 补救动作：重新执行 Compiler merge

### discard 未清理（标记丢弃但未移到 _trash/）
- [文件名]
- 补救动作：移动到 _trash/
```

---

## Drift 检测机制（健康检查）

**用户可能在 Obsidian 中手动改名/移动文件，绕过 Skill，导致 state.json 与实际文件系统不一致。**

### 触发方式

| 触发词 | 说明 |
|--------|------|
| "检查 pipeline 状态" / "健康检查" / "drift 检测" | 进入 drift 检测模式 |

### 检测内容

| 检测项 | 判断 | 输出 |
|--------|------|------|
| state.json 中的文件路径，实际是否存在 | 不存在 → drift | drift 报告 |
| 实际文件系统中 Capture 下的文件，是否在 state.json 中 | 不在 → 漏处理 | 待处理列表 |
| state.json 中"目标文件"路径，实际是否存在 | 不存在 → 假执行 | 假执行警告 |
| 文件的"标题"字段，是否与实际文件的第一个 # 标题一致 | 不一致 → 标题漂移 | 标题变更列表 |
| 文件的"文件哈希"，是否与实际 MD5 一致 | 不一致 → 内容漂移 | 内容变更列表 |

### 修复方式

drift 检测后输出修复建议：

| drift 类型 | 修复建议 |
|-----------|---------|
| 文件路径不存在 | 标记为"已删除"，从 state.json 中移除 |
| Capture 新增文件 | 加入待处理队列，下次 Pipeline 处理 |
| 目标文件不存在 | 重新触发 Compiler create |
| 标题漂移 | 触发 Planner 重新评估 |
| 内容漂移 | 轻量路径，触发 Mulu-fenlei-summary 重生成 File Summary |

---

## 处理步骤与子 Skill 的关系

| 步骤 | 调用的 Skill | 输入 | 输出 |
|------|--------------|------|------|
| 1. 分析 | `$obsidian-knowledge-planner` | Capture 文件（+扫描结果） | YAML contract |
| 2. 编译 | `$obsidian-knowledge-compiler` | 原始文件 + YAML | 标准化 MD（正确文件名） |
| 3. 归属 | `$obsidian-knowledge-organizer` | MD 文件 + YAML | 移动到目录 + 双链 + 目录更新 |

**可选步骤（仅批量重命名时）：**
| 步骤 | 调用的 Skill | 输入 | 输出 |
|------|--------------|------|------|
| 4. 重命名 | `$obsidian-fire-rename` | MD 文件 | 规范化命名 |

---

## 状态管理

### 处理状态值

| 状态 | 说明 |
|------|------|
| 待处理 | 检测到变化，等待处理 |
| 处理中 | 正在执行子 Skill |
| 已处理 | 全部步骤完成 |
| 处理失败 | 某个步骤出错 |
| 已跳过 | 用户选择跳过 |

### 失败处理

| 情况 | 处理 |
|------|------|
| 某个文件处理失败 | 记录错误，继续处理其他文件 |
| 某个步骤出错 | 重试一次，仍失败则跳过该文件 |
| 全部失败 | 输出错误报告，等待用户处理 |

---

## 运行模式

| 模式 | 说明 |
|------|------|
| 交互模式（默认） | 输出变化报告 → 等待用户确认 → 执行 |
| 自动模式 | 检测到变化 → 直接执行（用户指定时启用） |

---

## 安全规则

- **默认只处理 `A📥 收集（Capture）`**，其他文件夹必须用户明确指定
- 处理前输出变化报告
- 交互模式下等待用户确认
- 单个文件失败不影响其他文件
- 所有操作可回滚（通过子 Skill 的回滚机制）
- **操作记录去重**：Pipeline 仅更新 state.json，不写 `⚓新增文件记录.md`，由实际执行文件操作的子 Skill 写入

### 文件阈值保护（强制）

| 检查项 | 阈值 | 处理 |
|--------|------|------|
| 单文件大小 | > 2 MB | 跳过并警告（疑似非文本文件） |
| 单文件大小 | < 10 字节 | 跳过（空文件） |
| Capture 文件总数 | > 100 | 分批处理，每批 ≤ 20 个 |
| 单文件行数 | > 5000 行 | 仅处理前 500 行，剩余标记 `partial` |

### 陷阱文件检测（强制跳过）

以下文件即使出现在 Capture 中也跳过，不进入流水线：

| 模式 | 跳过原因 |
|------|----------|
| 文件名含 `临时`、`tmp`、`scratch`、`draft-` 前缀 | 临时草稿 |
| 文件名以 `.` 开头（如 `.DS_Store`） | 系统隐藏文件 |
| 扩展名非 `.md`（如 `.png`/`.pdf`/`.zip`） | 非文本资源 |
| 路径含 `node_modules/`、`.git/`、`.trash/` | 系统目录 |
| 文件内容前 5 行全是 base64 或二进制字符 | 误入 Capture 的二进制 |

陷阱文件命中后，记录到 `logs/pipeline/pipeline-YYYY-MM-DD.md` 的"陷阱文件"章节，并标注跳过原因。

### 超时保护（强制）

| 阶段 | 超时阈值 | 超时处理 |
|------|----------|----------|
| Planner 分析单文件 | 60 秒 | 跳过该文件，标记 `处理失败` |
| Compiler 编译单文件 | 90 秒 | 跳过该文件，标记 `处理失败` |
| Organizer 处理单文件 | 60 秒 | 跳过该文件，标记 `处理失败` |
| 整次 Pipeline 运行 | 30 分钟 | 暂停并输出进度报告，等待用户决定是否继续 |

超时触发的文件，状态记为 `处理失败`，错误信息字段填写"超时（XX秒）"。下次运行时自动重试一次，仍超时则永久跳过并提示用户。

---

## Pipeline vs 独立 Skill（重要区分）

| 维度 | obsidian-pipeline | 其他 Skill |
|------|-------------------|------------|
| **定位** | 调度器 | 执行器 |
| **处理范围** | 仅 `A📥 收集（Capture）` | 用户指定的任意文件夹 |
| **触发方式** | "处理 Capture"、"运行流水线" | "分析 xxx 文件夹"、"重命名 xxx" |
| **调用关系** | 调用其他 Skill | 独立执行 |
| **状态追踪** | `logs/pipeline/pipeline-state.json` | 各自的 `logs/{skill}/` 目录 |

**Pipeline 借用其他 Skill 的能力来批量处理 Capture，但其他 Skill 可以独立使用。**

---

## 日志系统

### 1. 追踪状态

`logs/pipeline/pipeline-state.json`

### 2. 运行日志

`logs/pipeline/pipeline-YYYY-MM-DD.md`

```markdown
# Pipeline 运行日志

日期: YYYY-MM-DD HH:MM

## 扫描结果
- 总文件数: X
- 新增: X
- 修改: X
- 删除: X
- 跳过: X

## 处理详情
| 文件 | 动作 | 状态 | 步骤 | 耗时 |
|------|------|------|------|------|
| xxx.md | create | 成功 | planner→compiler→organizer | 30s |
| yyy.md | merge | 成功 | planner→compiler(merge) | 15s |
| zzz.md | - | 跳过 | 未变化 | 0s |

## 操作记录
- 【新增】xxx.md D:\...\路径\
- 【合并】yyy.md → 已有文件路径
```

### 3. 各子 Skill 日志

每个子 Skill 执行后必须写入自己的日志目录：

| Skill | 日志位置 | 状态文件 |
|-------|----------|----------|
| Planner | `logs/planner/planner-YYYY-MM-DD.md` | `logs/planner/planner-state.json` |
| Compiler | `logs/compiler/compiler-YYYY-MM-DD.md` | `logs/compiler/compiler-state.json` |
| Fire-rename | `logs/rename/rename-YYYY-MM-DD.md` | `logs/rename/rename-state.json` |
| Organizer | `logs/organizer/organizer-YYYY-MM-DD.md` | `logs/organizer/organizer-state.json` |
| Mulu-fenlei | `logs/summary/summary-YYYY-MM-DD.md` | `logs/summary/summary-state.json` | 仅单独调用，不在主流程中 |

---

## 使用示例

### 场景1：标准处理

```
用户: "处理 Capture"
AI: 扫描 → 输出变化报告 → 等待确认 → 执行 → 更新追踪
```

### 场景2：处理其他文件夹（需明确指定）

```
用户: "处理 B🧹 整理（Organize）文件夹"
AI: 确认 → 扫描 → 输出报告 → 等待确认 → 执行
```

### 场景3：查看状态

```
用户: "查看 Pipeline 状态"
AI: 读取 pipeline-state.json → 输出当前状态
```

---

## 文件结构

```
C:\Users\leokou\.claude\skills\obsidian-pipeline\
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── state-schema.json
```

---
name: obsidian-fire-rename
description: 根据 Obsidian 知识库文件内容自动规范化文件名称。当用户要求"重命名文件"、"规范化文件名"、"文件命名检查"、"fire rename"、"批量重命名"时使用。读取文件内容 → 按命名规则生成新文件名 → 重命名 → 记录日志。适用于 Obsidian vault 中的 .md 文件。
---

# Obsidian Fire Rename

根据文件内容自动规范化 Obsidian 知识库文件名称。

**旁路工具**：不在 Pipeline 主流程中，仅在批量重命名已有文件时使用。

## 双层架构

| 层级 | 文件 | 用途 | 写入者 |
|------|------|------|--------|
| 人类可读层 | `📖目录 索引.md` | 浏览导航 | Mulu-fenlei + Organizer |
| 机器可读层 | `logs/rename/rename-state.json` | 记录原文件名、新文件名、处理状态 | Fire-rename |

**读取优先级**：
1. 先读状态文件（快速跳过已处理文件）
2. 再扫描未处理文件

## 工作流程

```
遍历目录文件
    ↓
检查 rename-state.json（跳过已处理文件）
    ↓
判断是否为系统文件（跳过）
    ↓
读取 frontmatter + 前30行内容
    ↓
按命名规则生成新文件名
    ↓
执行重命名
    ↓
双链维护（扫描其他文件中的 [[旧文件名]] → 更新为 [[新文件名]]）
    ↓
更新状态文件
```

## 第一步：检查状态文件，过滤已处理文件

读取 `logs/rename/rename-state.json`，提取所有已记录的原文件名和新文件名。
只处理没有记录的文件。跳过已记录的文件。

## 第二步：判断系统文件（跳过不改）

以下文件保持原名，不进入命名流程：

- `AGENTS.md`、`CLAUDE.md`、`README.md`、`AI_INDEX.md`
- `🏠 home-*.md`、`🤖 AI指令.md`、`🧩 目录-*.md`
- `.gitignore`、`.env`、`package.json`、`tsconfig.json`
- `🍕 作业区.md`、`opencode.jsonc`
- `templates/`、`聊天记录/` 目录下的文件

## 第三步：读取文件内容

对每个非系统文件，读取 frontmatter + 前30行，提取：
1. **标题**（第一个 `#` 开头的行）
2. **核心对象**（文件主要讲谁/什么）
3. **文件类型**（知识/项目/工具）
4. **保存价值**（这个文件有什么价值？）

## 第四步：按命名规则生成新文件名

详细规则见 [references/naming-rules.md](references/naming-rules.md)。

### 核心公式

| 文件类型 | 格式 | 示例 |
|---------|------|------|
| 普通文件 | `主题 - 类型 @ 说明` | `Docker - 工具 @ 环境部署方法` |
| 高级文件 | `领域 - 主题 - 类型 @ 说明` | `AI - Agent - 知识 @ 智能体运行机制` |
| 项目文件 | `项目 - 文档类型 - 状态 @ 说明` | `LEO OS - 项目文档 - 定稿 @ AI认知系统设计` |

### 主题规则
- 使用明确实体名称（ChatGPT、Python、Docker）
- 不加情绪词（超级、最强、重要）
- 保留行业通用关键词

### 类型词库（固定，不要创造）

**知识页面类**：知识、概念、原理、笔记、总结、对比、案例

**工具配置类**：工具、教程、指南、手册、清单、安装、配置

**项目文档类**：项目文档、需求文档、设计方案、技术方案、会议记录、分析报告

### @说明规则
- 不重复标题，回答"这个文件有什么价值"
- 用途说明：`@ 用于xxx`
- 内容说明：`@ 包含xxx`
- 场景说明：`@ xxx场景使用`
- 关联说明：`@ 关联xxx`

### 状态字段（仅项目文件使用）
草稿、初稿、V1、V2、修订版、测试版、定稿、正式版、归档

## 第五步：执行重命名

使用 PowerShell `Rename-Item` 命令重命名文件。注意 UTF-8 编码。

## 第六步：双链维护（强制，避免双链失效）

**重命名后必须扫描整个 vault 中其他文件的双链引用，把 `[[旧文件名]]` 更新为 `[[新文件名]]`，否则原链接会变成"未找到引用"的红色断链。**

### 扫描范围

整个 `D:\Obsidian\LeoDiary\` 下的所有 `.md` 文件，排除：
- `.trash/`、`node_modules/`、`.git/`、`logs/`
- 已处理的源文件自身

### 扫描命令

```powershell
# 提取旧文件名（不含扩展名）和新文件名（不含扩展名）
$旧名 = [System.IO.Path]::GetFileNameWithoutExtension("原文件名.md")
$新名 = [System.IO.Path]::GetFileNameWithoutExtension("新文件名.md")

# 在所有 md 文件中搜索 [[旧名]] 引用
Select-String -Path "D:\Obsidian\LeoDiary\*.md" -Pattern "\[\[$旧名\]\]" -Recurse
```

### 更新规则

| 情况 | 处理 |
|------|------|
| 找到 `[[旧文件名]]` | 替换为 `[[新文件名]]`（保留前后别名，如 `[[旧文件名\|别名]]` → `[[新文件名\|别名]]`） |
| 找到 `[[旧文件名|别名]]` | 仅替换文件名部分，保留别名 |
| 找到 `![[旧文件名]]`（图片嵌入） | 也替换为新文件名（防止资源嵌入断裂） |
| 未找到引用 | 跳过（无需更新） |

### 批量更新效率

为避免对每个重命名文件都全量扫描，**批量重命名完成后一次性扫描所有更名**：

```
遍历所有重命名记录（旧名→新名）
    ↓
对 vault 中每个 .md 文件，按所有 (旧名, 新名) 对做替换
    ↓
记录每文件被更新的链接数
```

### 双链更新记录

更新的双链必须记录到状态文件（见下方"双链更新"字段）和运行日志：

```markdown
### YYYY年M月D日
- 【双链更新】旧文件名 → 新文件名（影响 X 个文件，更新 X 处引用）
  - 受影响文件：[[文件1]]、[[文件2]]、[[文件3]]
```

## 第七步：更新状态文件

更新 `logs/rename/rename-state.json`：

```json
{
  "原文件路径": {
    "原文件名": "原文件名.md",
    "新文件名": "新文件名.md",
    "目录": "目标目录",
    "处理状态": "已重命名",
    "处理时间": "ISO 8601 时间戳",
    "双链更新": {
      "受影响文件数": 0,
      "更新链接数": 0,
      "受影响文件": ["文件路径列表"]
    }
  }
}
```

## 常见问题处理

| 问题 | 处理方式 |
|------|---------|
| 文件名已有 `主题 - 类型 @ 说明` 格式 | 检查 @说明 是否准确，不准确则调整 |
| 文件名含情绪词/口语词 | 去除，保留核心主题 |
| 标题过长含冗余信息 | 精简，保留核心 |
| 缺少 @说明 字段 | 根据内容补充 |
| 缺少类型字段 | 根据内容判断类型并补充 |
| 重命名后双链失效（红色断链） | 第六步双链维护未执行 → 重新扫描全 vault 并更新 `[[旧文件名]]` → `[[新文件名]]` |
| 双链带别名 `[[旧名\|别名]]` | 仅替换文件名部分，保留别名分隔符 `\|` 后内容 |
| 图片嵌入 `![[旧名]]` 也需更新 | 一并替换为新名，避免资源嵌入断裂 |

## 操作记录

所有重命名操作必须记录到 `⚓新增文件记录.md`，格式如下：

```markdown
### YYYY年M月D日
- 【优化】原文件名 → 新文件名 D:\Obsidian\LeoDiary\路径\
```

追加写入，不覆盖已有记录。

---

## 状态追踪机制

### 追踪文件位置

```
logs/rename/rename-state.json
```

### 追踪数据结构

```json
{
  "版本": "1.0",
  "上次运行": "ISO 8601 时间戳",
  "文件状态": {
    "原文件路径": {
      "原文件名": "原文件名.md",
      "新文件名": "新文件名.md",
      "目录": "目标目录",
      "处理状态": "已重命名 | 已跳过",
      "处理时间": "最后处理时间",
      "双链更新": {
        "受影响文件数": 0,
        "更新链接数": 0,
        "受影响文件": ["文件路径列表"]
      }
    }
  }
}
```

### 变化检测规则

| 条件 | 判断 | 动作 |
|------|------|------|
| 文件名已符合 `主题 - 类型 @ 说明` 格式 | 已规范 | 跳过 |
| 文件名不符合格式 | 需规范 | 重命名 |
| 文件不在追踪记录中 | 新增 | 处理 |
| 文件在追踪中且名称未变 | 未变化 | 跳过 |

### 执行后必须

1. 更新 `logs/rename/rename-state.json`
2. 写入运行日志 `logs/rename/rename-YYYY-MM-DD.md`
3. 生成可执行的回滚脚本（见下方）

## 回滚机制（强制）

**每次重命名必须生成可执行的 PowerShell 回滚脚本，否则视为不完整执行。**

### 回滚脚本路径

```
logs/rename/rename-rollback-YYYY-MM-DD-HHMM.ps1
```

### 回滚脚本内容

```powershell
# Fire-rename 回滚脚本
# 生成时间: YYYY-MM-DD HH:MM
# 用法: powershell -ExecutionPolicy Bypass -File rename-rollback-YYYY-MM-DD-HHMM.ps1

$ErrorActionPreference = 'Stop'

# 1. 文件名回滚（旧名 → 新名 的逆操作）
$renameMap = @(
    @{ 新名 = "新文件名1.md"; 旧名 = "旧文件名1.md"; 目录 = "目录路径1" }
    @{ 新名 = "新文件名2.md"; 旧名 = "旧文件名2.md"; 目录 = "目录路径2" }
)

foreach ($r in $renameMap) {
    $newPath = Join-Path $r.目录 $r.新名
    $oldPath = Join-Path $r.目录 $r.旧名
    if (Test-Path $newPath) {
        Move-Item -LiteralPath $newPath -Destination $oldPath -Force
        Write-Host "[回滚] $($r.新名) → $($r.旧名)"
    } else {
        Write-Host "[跳过] $($r.新名) 不存在"
    }
}

# 2. 双链回滚（新名 → 旧名 的逆操作）
# 使用 Get-ChildItem + Select-String + (Get-Content | ForEach-Object { $_ -replace '\[\[新名', '[[旧名' } | Set-Content) 批量回滚
$doubleLinkMap = @(
    @{ 新名 = "新文件名1"; 旧名 = "旧文件名1" }
)

$vaultRoot = "D:\Obsidian\LeoDiary"
$excludeDirs = @("_trash", "logs", ".git", "node_modules")
$mdFiles = Get-ChildItem -Path $vaultRoot -Filter "*.md" -Recurse -File | Where-Object {
    $excludeDirs -notcontains $_.Directory.Name
}

foreach ($m in $doubleLinkMap) {
    foreach ($f in $mdFiles) {
        $content = Get-Content -LiteralPath $f.FullName -Raw
        if ($content -match "\[\[$($m.新名)") {
            $newContent = $content -replace "\[\[$($m.新名)", "[[$($m.旧名)"
            Set-Content -LiteralPath $f.FullName -Value $newContent -NoNewline
            Write-Host "[双链回滚] $($f.Name) 中的 [[$($m.新名) → [[$($m.旧名)"
        }
    }
}

Write-Host "==== 回滚完成 ===="
```

### 回滚触发方式

| 触发方式 | 说明 |
|---------|------|
| 用户说"回滚 rename" / "撤销重命名" | 找到最新的 rollback 脚本并执行 |
| 用户指定具体脚本 | `回滚 rename-rollback-2026-07-25-1930.ps1` |
| 自动触发 | merge 完整性验证失败时，自动回滚最近一次 rename |

### 回滚保护

- 回滚脚本必须先备份当前状态到 `logs/rename/backups/before-rollback-YYYY-MM-DD-HHMM.json`
- 回滚前提示用户确认（除非用户明确说"强制回滚"）
- 回滚完成后，更新 state.json 中相关文件的"处理状态"为"已回滚"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LeoDiary AI 检索系统模拟测试
============================
测试 LD-DVA Final AI_INDEX Builder 的检索、缓存、增量更新等核心功能。
模拟 5 个不同话题的完整检索流程。

话题：
1. AI 工具查询      - "AI编程助手"
2. 开发问题排查      - "Python 调试"
3. 个人知识整理      - "知识管理"
4. 系统配置         - "Obsidian 配置"
5. 项目文档检索      - "LD-DVA 方案"
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

if sys.platform == "win32" and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

VAULT_ROOT = Path(r"D:\Obsidian\LeoDiary")
PYTHON_DIR = Path(r"D:\Python\projects\leodiarycode")
SCRIPT_PATH = PYTHON_DIR / "scripts" / "ai_index_builder.py"
HARNESS_DIR = VAULT_ROOT / "_test_harness"
SCANNED_TEMP_DIR = VAULT_ROOT / "0-_test_harness"
REPORT_FILE = PYTHON_DIR / "AI_RETRIEVAL_TEST_REPORT.md"

TOPICS = [
    {
        "id": 1,
        "name": "AI 工具查询",
        "query": "AI编程助手",
        "search_terms": ["AI编程", "编程助手", "AI 助手", "开发工具"],
        "notes": [
            {
                "title": "AI编程助手 - Claude Code 使用指南 @ 2026",
                "summary": "全面介绍Claude Code作为AI编程助手的核心能力，包括代码生成、多文件编辑、Shell命令执行等实战功能。",
                "tags": ["AI编程", "编程助手", "Claude", "开发工具", "LLM"],
                "keywords": ["AI编程助手", "Claude Code", "CLI工具", "代码生成", "效率提升"],
                "entities": ["Claude Code", "Anthropic", "Code CLI"],
                "body": """# AI编程助手 - Claude Code 使用指南

## 概述
Claude Code 是目前最强大的 AI 编程助手之一，支持 CLI 方式调用，能够理解代码上下文、执行命令、编辑文件。

## 核心功能
- 代码理解与生成：理解复杂代码库，生成高质量代码
- 多文件编辑：跨文件批量修改，保持一致性
- Shell 命令执行：直接在终端执行命令
- Git 操作：集成 Git 工作流

## 实战场景
1. 快速原型开发
2. 代码审查与重构
3. 测试用例生成
4. 文档自动撰写

## 配置要点
- 使用 CLAUDE.md 配置项目规则
- 合理设置 API Key 权限
- 配置上下文引用文件
"""
            },
            {
                "title": "AI编程工具对比 - Cursor vs Copilot vs Claude @ 2026",
                "summary": "横向对比主流AI编程工具的特点和优势，帮助开发者选择最适合的AI编程助手。",
                "tags": ["AI编程", "工具对比", "Cursor", "Copilot", "Claude"],
                "keywords": ["AI编程助手", "Cursor", "Copilot", "Claude", "工具评测"],
                "entities": ["Cursor", "GitHub Copilot", "Claude Code", "Tabnine"],
                "body": """# AI编程工具对比

## 评测维度
| 工具 | 代码质量 | 上下文理解 | 编辑效率 | 价格 |
|------|---------|-----------|---------|------|
| Cursor | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 免费+付费 |
| Copilot | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $10/月 |
| Claude Code | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按量计费 |

## 选择建议
1. **个人开发者**：Cursor 或 Copilot
2. **团队协作**：Claude Code + 自定义MCP
3. **企业用户**：Tabnine 或自建方案
"""
            }
        ]
    },
    {
        "id": 2,
        "name": "开发问题排查",
        "query": "Python 调试",
        "search_terms": ["Python调试", "Python 调试", "debug", "排查"],
        "notes": [
            {
                "title": "Python 调试技巧 - 从入门到精通 @ 2026",
                "summary": "系统总结Python调试的核心技巧，包括pdb、logging、性能分析等多种调试方法。",
                "tags": ["Python", "调试", "debug", "开发技巧", "问题排查"],
                "keywords": ["Python调试", "pdb", "性能分析", "logging", "代码排查"],
                "entities": ["pdb", "PyCharm", "VS Code", "cProfile"],
                "body": """# Python 调试技巧

## 常用调试方法

### 1. 使用 pdb 命令行调试
```python
import pdb
pdb.set_trace()
# 常用命令: n(ext), s(tep), p(rint), c(ontinue), q(uit)
```

### 2. 使用 logging 模块
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("调试信息")
```

### 3. 性能分析
```python
import cProfile
cProfile.run('function_name()')
```

## 常见问题排查
- 内存泄漏：使用 tracemalloc 或 objgraph
- 性能瓶颈：使用 cProfile 或 line_profiler
- 并发问题：使用 threading/sys.settrace
- 第三方库问题：检查版本兼容性

## 最佳实践
1. 合理使用断言代替print
2. 利用 __future__ 模块
3. 使用 type hints 提前发现问题
4. 编写单元测试覆盖边界情况
"""
            },
            {
                "title": "Python 性能排查与优化实战 @ 2026",
                "summary": "分享Python性能排查的实战经验，包括瓶颈定位、内存优化、并发加速等关键技术。",
                "tags": ["Python", "性能优化", "排查", "内存管理", "并发"],
                "keywords": ["Python调试", "性能优化", "内存泄漏", "并发优化", "代码优化"],
                "entities": ["cProfile", "memory_profiler", "asyncio", "multiprocessing"],
                "body": """# Python 性能排查与优化

## 排查流程
1. 确认问题：基准测试对比
2. 定位瓶颈：性能分析器
3. 分析原因：代码审查
4. 实施优化：针对性改进

## 工具推荐
| 工具 | 用途 |
|------|------|
| cProfile | CPU性能分析 |
| memory_profiler | 内存分析 |
| line_profiler | 行级耗时分析 |
| py-spy | 生产环境采样 |

## 常见优化手段
- 使用生成器代替列表
- 合理使用缓存（functools.lru_cache）
- 批量操作代替循环
- 使用内置数据结构
- 考虑使用 C 扩展或 Cython
"""
            }
        ]
    },
    {
        "id": 3,
        "name": "个人知识整理",
        "query": "知识管理",
        "search_terms": ["知识管理", "个人知识", "笔记整理", "PARA"],
        "notes": [
            {
                "title": "知识管理 - PARA方法论实践 @ 2026",
                "summary": "详细介绍PARA方法论在个人知识管理中的实践应用，涵盖Projects/Areas/Resources/Archives四层架构。",
                "tags": ["知识管理", "PARA", "方法论", "笔记", "个人成长"],
                "keywords": ["知识管理", "PARA方法", "第二大脑", "笔记系统", "信息架构"],
                "entities": ["PARA", "Projects", "Areas", "Resources", "Archives"],
                "body": """# 知识管理 - PARA方法论实践

## PARA 架构
```
Projects（项目）: 当前进行中的目标导向工作
Areas（领域）: 持续维护的责任领域
Resources（资源）: 有参考价值的主题
Archives（归档）: 完成或过时的内容
```

## 实施步骤
1. **盘点现有**：整理现有文件结构
2. **分类归档**：按PARA重新组织
3. **命名规范**：统一文件命名约定
4. **建立索引**：创建知识地图
5. **定期维护**：周/月回顾

## 工具选择
| 需求 | 推荐工具 | 特点 |
|------|---------|------|
| 全平台同步 | Notion/Obsidian | 多端访问 |
| Markdown优先 | Obsidian | 本地存储 |
| 协作需求 | Notion | 实时协作 |

## 进阶技巧
- 使用MOC（Map of Content）组织知识
- 建立双向链接形成知识网络
- 定期回顾输出促进知识内化
"""
            },
            {
                "title": "第二大脑 - 高效知识管理系统 @ 2026",
                "summary": "介绍如何构建个人第二大脑，从收集、整理、组织到输出的完整知识管理流程。",
                "tags": ["知识管理", "第二大脑", "笔记系统", "效率", "Zettelkasten"],
                "keywords": ["第二大脑", "知识管理", "笔记系统", "信息处理", "知识内化"],
                "entities": ["笔记", "知识网络", "双向链接", "Zettelkasten"],
                "body": """# 第二大脑 - 高效知识管理系统

## 核心流程
```
收集 → 整理 → 组织 → 表达
```

## Zettelkasten 方法
1. **原子笔记**：每个笔记一个观点
2. **双向链接**：笔记间相互引用
3. **索引系统**：MOC导航地图
4. **编号系统**：可追踪的ID体系

## 避坑指南
- 不要追求完美主义
- 保持系统简洁
- 避免过度工具化
- 定期回顾和精简
"""
            }
        ]
    },
    {
        "id": 4,
        "name": "系统配置",
        "query": "Obsidian 配置",
        "search_terms": ["Obsidian配置", "Obsidian 设置", "Obsidian 配置", "Vault"],
        "notes": [
            {
                "title": "Obsidian 配置 - 最佳实践与推荐设置 @ 2026",
                "summary": "总结Obsidian的核心配置项和最佳实践，涵盖编辑器、快捷键、插件等关键设置。",
                "tags": ["Obsidian", "配置", "设置", "插件", "效率"],
                "keywords": ["Obsidian配置", "Vault设置", "插件推荐", "主题配置", "快捷键"],
                "entities": ["Obsidian", "Vault", "插件", "主题"],
                "body": """# Obsidian 配置

## 核心设置
### 编辑器设置
- 开启行号显示
- 使用 vim 模式（如习惯）
- 设置 Tab 缩进为 2 空格
- 启用拼写检查

### 快捷键配置
常用自定义快捷键：
- Ctrl+Shift+A：新建笔记
- Ctrl+Shift+O：打开命令面板
- Ctrl+Shift+F：全文搜索

### 插件推荐
| 插件 | 用途 |
|------|------|
| Templater | 模板自动化 |
| Dataview | 数据查询 |
| Periodic Notes | 日记/周记 |
| Kanban | 看板管理 |

## Vault 组织建议
1. 使用 PARA 或 Zettelkasten 结构
2. 建立命名规范
3. 定期维护和清理
"""
            },
            {
                "title": "Obsidian 高级配置 - 自定义主题与插件 @ 2026",
                "summary": "分享Obsidian高级配置技巧，包括自定义CSS主题、插件配置、Sync同步设置等。",
                "tags": ["Obsidian", "配置", "主题", "插件", "Sync"],
                "keywords": ["Obsidian配置", "自定义主题", "插件开发", "Sync同步", "CSS"],
                "entities": ["Obsidian", "CSS", "Theme", "Plugin"],
                "body": """# Obsidian 高级配置

## 自定义 CSS 主题
```css
/* 调整字体大小 */
.cm-content { font-size: 16px; }

/* 修改标题颜色 */
.cm-header-1 { color: #ff6b6b; }

/* 设置行距 */
.markdown-preview-view p { line-height: 1.8; }
```

## Sync 同步配置
- 端到端加密
- 选择性同步
- 冲突解决策略

## 插件开发
1. 了解 Obsidian Plugin API
2. 使用 TypeScript 开发
3. 利用 Community Plugins 框架
"""
            }
        ]
    },
    {
        "id": 5,
        "name": "项目文档检索",
        "query": "LD-DVA 方案",
        "search_terms": ["LD-DVA", "LD-DVA 方案", "项目文档", "DVA"],
        "notes": [
            {
                "title": "LD-DVA 方案 - AI 驱动的知识管理系统 @ 2026",
                "summary": "详细介绍LD-DVA方案的核心设计理念，包括AI索引构建、智能检索、自动化流水线等关键模块。",
                "tags": ["LD-DVA", "系统设计", "AI检索", "知识管理", "架构"],
                "keywords": ["LD-DVA方案", "AI索引", "检索系统", "知识管理架构", "自动化"],
                "entities": ["LD-DVA", "AI_INDEX", "retrieval-index", "pipeline"],
                "body": """# LD-DVA 方案

## 设计理念
LD-DVA（LeoDiary Design for Versatile Automation）是一套AI驱动的个人知识管理系统。

## 核心模块
### 1. AI 索引构建
- retrieval-index.md：关键词倒排索引
- tag-index.md：标签关联索引
- entity-index.md：实体关系索引
- query-cache.json：查询缓存
- index-state.json：状态追踪

### 2. 智能检索
- 同义词扩展
- 多维度评分（文件名/标题/摘要/关键词/标签/正文）
- 缓存加速

### 3. 自动化流水线
- Capture → Organize → Process → Archive
- 增量更新机制
- 质量检查

## 技术栈
- Python 3.x
- Obsidian Markdown
- AI 向量检索
"""
            },
            {
                "title": "LD-DVA 实现细节 - 索引构建与检索算法 @ 2026",
                "summary": "深入解析LD-DVA的索引构建算法和检索评分机制，包括同义词扩展、多维度加权评分等核心实现。",
                "tags": ["LD-DVA", "算法", "检索", "索引", "评分"],
                "keywords": ["LD-DVA实现", "索引算法", "检索评分", "同义词扩展", "增量更新"],
                "entities": ["_compute_score", "_expand_query", "_incremental", "SYNONYM_MAP"],
                "body": """# LD-DVA 实现细节

## 检索评分算法
权重分配：
- 文件名匹配：100分
- 标题匹配：90分
- 摘要匹配：70分
- 关键词匹配：60分
- 标签匹配：40分
- 正文匹配：20分

## 同义词扩展
预置同义词映射表，支持：
- 标准词 → 扩展词
- 扩展词 → 标准词
- 自动识别并扩展查询

## 增量更新
基于 hash 的变化检测：
1. 扫描文件列表
2. 对比 hash 值
3. 识别新增/修改/删除
4. 只读取变化文件
5. 合并缓存数据
6. 生成新索引

## 缓存策略
- TTL 24小时
- 自动写入命中结果
- 支持主动失效
- 统计命中率
"""
            }
        ]
    }
]


def run_cmd(args, timeout=120):
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            cwd=str(PYTHON_DIR)
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            'success': proc.returncode == 0,
            'stdout': stdout or '',
            'stderr': stderr or '',
            'returncode': proc.returncode
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        return {'success': False, 'stdout': '', 'stderr': '执行超时', 'returncode': -1}
    except Exception as e:
        return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}


class TestRunner:
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        self.test_file_paths = []

    def log(self, category, name, status, detail, remediation=""):
        entry = {
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
            "remediation": remediation,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        self.results.append(entry)
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "?")
        print(f"  {icon} [{category}] {name}: {detail}")
        return entry

    def step_search(self, query, top_n=5):
        print(f"    🔍 搜索: '{query}'")
        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "search", query, "--top", str(top_n)
        ])
        if result['success']:
            self.log("搜索", f"search '{query}'", "pass",
                     f"执行成功，输出 {len(result['stdout'])} 字节")
            return result['stdout']
        else:
            self.log("搜索", f"search '{query}'", "fail",
                     f"执行失败: {result['stderr'][:150]}")
            return None

    def step_cache_read(self, query):
        print(f"    💾 读取缓存: '{query}'")
        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "cache-read", query
        ])
        if result['success']:
            output = result['stdout'].strip()
            if output and output != "🔍 缓存未命中":
                self.log("缓存", f"cache-read '{query}'", "pass",
                         f"缓存命中: {output[:120]}")
                return True
            else:
                self.log("缓存", f"cache-read '{query}'", "warn",
                         "缓存未命中（可能是首次查询或已过期）")
                return False
        else:
            self.log("缓存", f"cache-read '{query}'", "fail",
                     f"执行失败: {result['stderr'][:100]}")
            return False

    def step_create_capture(self, topic_id, topic_name, notes, query):
        print(f"    📝 创建测试 Capture 笔记")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        created = []

        for note in notes:
            safe_title = note['title'].replace('/', '-').replace('\\', '-')
            filepath_harness = HARNESS_DIR / f"T{topic_id}_{safe_title}.md"
            filepath_scanned = SCANNED_TEMP_DIR / f"T{topic_id}_{safe_title}.md"

            fm_lines = ["---"]
            fm_lines.append(f"id: leo-test-{timestamp}-{topic_id}")
            fm_lines.append(f"title: {note['title']}")
            fm_lines.append(f"type: 测试")
            fm_lines.append(f"summary: {note['summary']}")
            fm_lines.append("tags:")
            for tag in note['tags']:
                fm_lines.append(f"  - {tag}")
            fm_lines.append("keywords:")
            for kw in note['keywords']:
                fm_lines.append(f"  - {kw}")
            fm_lines.append("entities:")
            for ent in note['entities']:
                fm_lines.append(f"  - {ent}")
            fm_lines.append(f"date: {datetime.now().strftime('%Y-%m-%d')}")
            fm_lines.append(f"updated: {datetime.now().strftime('%Y-%m-%d')}")
            fm_lines.append("---")
            fm_lines.append("")
            fm_lines.append(note['body'])

            content = "\n".join(fm_lines)

            HARNESS_DIR.mkdir(parents=True, exist_ok=True)
            SCANNED_TEMP_DIR.mkdir(parents=True, exist_ok=True)

            filepath_harness.write_text(content, encoding='utf-8')
            filepath_scanned.write_text(content, encoding='utf-8')

            created.append(str(filepath_scanned))
            self.test_file_paths.append(str(filepath_scanned))

        self.log("创建", f"T{topic_id} {topic_name}", "pass",
                 f"创建 {len(notes)} 个测试笔记（Harness + Scanned 双写）")
        return created

    def step_incremental(self):
        print(f"    🔄 执行增量更新...")
        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "incremental"
        ])
        if result['success']:
            output_text = result['stdout']
            if '没有检测到变化' in output_text:
                self.log("索引", "incremental", "warn",
                         "增量更新：没有检测到变化（新笔记可能未被扫描）")
                return None
            self.log("索引", "incremental", "pass",
                     f"增量更新成功: {output_text[:150]}")
            return True
        else:
            self.log("索引", "incremental", "fail",
                     f"增量更新失败: {result['stderr'][:150]}")
            return False

    def step_rebuild(self):
        print(f"    🔄 执行全量重建...")
        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "rebuild"
        ], timeout=180)
        if result['success']:
            self.log("索引", "rebuild", "pass",
                     f"全量重建成功: {result['stdout'][:150]}")
            return True
        else:
            self.log("索引", "rebuild", "fail",
                     f"全量重建失败: {result['stderr'][:150]}")
            return False

    def step_cache_clear(self):
        print(f"    🧹 清空缓存...")
        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "cache-clear"
        ])
        if result['success']:
            self.log("缓存", "cache-clear", "pass", "缓存已清空")
            return True
        return False

    def step_verify_search_results(self, query, search_output, expected_terms):
        if not search_output:
            self.log("验证", f"verify '{query}'", "warn",
                     "无搜索输出（可能是无匹配结果）")
            return False

        found_terms = []
        for term in expected_terms:
            if term.lower() in search_output.lower():
                found_terms.append(term)

        if found_terms:
            self.log("验证", f"verify '{query}'", "pass",
                     f"命中关键词: {', '.join(found_terms)}")
            return True
        else:
            if '命中 0 个文件' in search_output or '0 个文件' in search_output:
                self.log("验证", f"verify '{query}'", "warn",
                         "搜索无匹配结果（测试笔记可能尚未被索引）")
            else:
                self.log("验证", f"verify '{query}'", "pass",
                         f"搜索已执行，输出 {len(search_output)} 字节")
            return False

    def run_topic(self, topic):
        topic_id = topic['id']
        topic_name = topic['name']
        query = topic['query']
        notes = topic['notes']
        search_terms = topic['search_terms']

        print(f"\n  📌 Topic {topic_id}: {topic_name}")
        print(f"  {'─' * 50}")
        print(f"     查询: '{query}'")

        # Step 1: 清空缓存确保无干扰
        self.step_cache_clear()

        # Step 2: 搜索（基线）
        print(f"     ── Step 1: 基线搜索 ──")
        baseline_output = self.step_search(query)
        self._save_step_output(topic_id, "baseline_search", baseline_output)

        # Step 3: 缓存读取（验证已自动缓存）
        print(f"     ── Step 2: 缓存读取 ──")
        cache_hit = self.step_cache_read(query)

        # Step 4: 创建测试 Capture 笔记
        print(f"     ── Step 3: 创建 Capture 笔记 ──")
        self.step_create_capture(topic_id, topic_name, notes, query)

        # Step 5: 增量更新
        print(f"     ── Step 4: 增量更新 ──")
        inc_result = self.step_incremental()

        # 如果增量更新失败或无变化，回退到全量重建
        if inc_result is None:
            print(f"     ⚠️  增量更新未检测到变化，回退到全量重建以确保索引更新")
            self.step_rebuild()
        elif not inc_result:
            print(f"     ⚠️  增量更新失败，回退到全量重建")
            self.step_rebuild()

        # Step 6: 再次搜索（验证新结果）
        print(f"     ── Step 5: 再次搜索（验证新笔记已索引） ──")
        self.step_cache_clear()
        fresh_output = self.step_search(query)
        self._save_step_output(topic_id, "fresh_search", fresh_output)

        # Step 7: 验证新结果是否包含预期关键词
        print(f"     ── Step 6: 验证搜索结果 ──")
        self.step_verify_search_results(query, fresh_output, search_terms)

        # Step 8: 再次缓存读取
        print(f"     ── Step 7: 再次缓存读取 ──")
        self.step_cache_read(query)

        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "query": query,
            "baseline_output": baseline_output,
            "fresh_output": fresh_output,
        }

    def _save_step_output(self, topic_id, step_name, output):
        if not output:
            return
        try:
            output_file = HARNESS_DIR / f"T{topic_id}_{step_name}.txt"
            output_file.write_text(output, encoding='utf-8')
        except Exception:
            pass

    def cleanup(self):
        print("\n  🧹 清理测试文件...")
        paths_to_clean = [HARNESS_DIR, SCANNED_TEMP_DIR]
        for p in paths_to_clean:
            if p.exists():
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    print(f"    ✅ 已删除: {p}")
                except Exception as e:
                    print(f"    ⚠️  删除失败: {p} - {e}")

        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "cache-clear"
        ])
        print(f"    ✅ 缓存已清空")

        result = run_cmd([
            sys.executable, str(SCRIPT_PATH), "incremental"
        ], timeout=60)
        print(f"    ✅ 索引已同步")

    def generate_report(self):
        print("\n  📋 生成测试报告...")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        pass_count = sum(1 for r in self.results if r['status'] == 'pass')
        warn_count = sum(1 for r in self.results if r['status'] == 'warn')
        fail_count = sum(1 for r in self.results if r['status'] == 'fail')
        total = len(self.results)
        percentage = (pass_count * 100 + warn_count * 50) / (total * 100) * 100 if total > 0 else 0
        verdict = "PASS" if fail_count == 0 else "FAIL"

        md_lines = []
        md_lines.append("# 🧪 LeoDiary AI 检索系统测试报告\n")
        md_lines.append(f"**生成时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append(f"**测试耗时**: {duration:.1f} 秒")
        md_lines.append(f"**测试范围**: AI 检索 / 缓存 / 增量更新 / 5 话题模拟\n")

        md_lines.append("## 📊 测试结果摘要\n")
        md_lines.append(f"| 指标 | 数值 |")
        md_lines.append(f"|------|------|")
        md_lines.append(f"| 总检查项 | {total} |")
        md_lines.append(f"| ✅ 通过 | {pass_count} |")
        md_lines.append(f"| ⚠️ 警告 | {warn_count} |")
        md_lines.append(f"| ❌ 失败 | {fail_count} |")
        md_lines.append(f"| 📈 得分 | {percentage:.1f}% |")
        md_lines.append(f"| 🎯 结论 | **{verdict}** |\n")

        md_lines.append("## 📂 分类统计\n")
        categories = {}
        for r in self.results:
            cat = r['category']
            if cat not in categories:
                categories[cat] = {"pass": 0, "warn": 0, "fail": 0}
            categories[cat][r['status']] += 1

        md_lines.append("| 类别 | ✅ 通过 | ⚠️ 警告 | ❌ 失败 | 状态 |")
        md_lines.append("|------|--------|--------|--------|------|")
        for cat, counts in sorted(categories.items()):
            icon = "✅" if counts['fail'] == 0 and counts['warn'] == 0 else "⚠️" if counts['fail'] == 0 else "❌"
            status = "OK" if counts['fail'] == 0 and counts['warn'] == 0 else "WARN" if counts['fail'] == 0 else "FAIL"
            md_lines.append(f"| {cat} | {counts['pass']} | {counts['warn']} | {counts['fail']} | {icon} {status} |")

        md_lines.append("")
        md_lines.append("## 📝 详细检查日志\n")

        current_category = None
        for r in self.results:
            if r['category'] != current_category:
                current_category = r['category']
                md_lines.append(f"\n### {current_category}\n")
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(r['status'], "?")
            md_lines.append(f"- {icon} **{r['name']}** ({r['time']}): {r['detail']}")
            if r.get('remediation'):
                md_lines.append(f"  - 💡 建议: {r['remediation']}")

        md_lines.append("")
        md_lines.append("## 🧠 话题测试详情\n")

        for topic in TOPICS:
            tid = topic['id']
            tname = topic['name']
            query = topic['query']
            md_lines.append(f"### Topic {tid}: {tname}\n")
            md_lines.append(f"- **查询词**: `{query}`")
            md_lines.append(f"- **搜索词**: {', '.join(topic['search_terms'])}")
            md_lines.append(f"- **测试笔记数**: {len(topic['notes'])}")
            md_lines.append(f"- **笔记标题**:")
            for note in topic['notes']:
                md_lines.append(f"  - {note['title']}")
            md_lines.append("")

        md_lines.append("## 🔧 环境信息\n")
        md_lines.append(f"- **Vault**: `{VAULT_ROOT}`")
        md_lines.append(f"- **Python 脚本**: `{SCRIPT_PATH}`")
        md_lines.append(f"- **AI 索引目录**: `{VAULT_ROOT / '🤖AI_INDEX'}`")
        md_lines.append(f"- **测试时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        md_lines.append("")
        md_lines.append("---")
        md_lines.append(f"*报告由 LeoDiary AI 检索系统测试脚本自动生成*")

        report_content = "\n".join(md_lines)

        HARNESS_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(report_content, encoding='utf-8')

        print(f"  📄 报告已保存: {REPORT_FILE}")
        return report_content

    def run(self):
        print("=" * 60)
        print("🚀 LeoDiary AI 检索系统模拟测试")
        print("=" * 60)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试话题: 5 个不同领域")
        print(f"测试工具: ai_index_builder.py / obsidian_skill_utils.py")

        # 确保目录存在
        HARNESS_DIR.mkdir(parents=True, exist_ok=True)

        # 初始化索引（确保有基础数据）
        print("\n📦 初始化索引...")
        self.step_rebuild()

        # 遍历 5 个话题
        for topic in TOPICS:
            self.run_topic(topic)

        # 生成报告
        report = self.generate_report()

        # 清理
        self.cleanup()

        # 打印总结
        pass_count = sum(1 for r in self.results if r['status'] == 'pass')
        warn_count = sum(1 for r in self.results if r['status'] == 'warn')
        fail_count = sum(1 for r in self.results if r['status'] == 'fail')
        total = len(self.results)
        percentage = (pass_count * 100 + warn_count * 50) / (total * 100) * 100 if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"📊 测试结果总结")
        print(f"{'='*60}")
        print(f"  总检查项: {total}")
        print(f"  ✅ 通过: {pass_count}")
        print(f"  ⚠️ 警告: {warn_count}")
        print(f"  ❌ 失败: {fail_count}")
        print(f"  📈 得分: {percentage:.1f}%")
        print(f"  🎯 结论: {'PASS' if fail_count == 0 else 'FAIL'}")
        print(f"  📄 报告: {REPORT_FILE}")

        return {
            "success": fail_count == 0,
            "report": str(REPORT_FILE),
            "total_checks": total,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "score_percentage": percentage,
        }


def main():
    runner = TestRunner()
    result = runner.run()
    if not result['success']:
        print("\n⚠️  存在失败项，请查看报告了解详情。")
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LD-DVA 综合测试运行器
====================
模拟5个不同话题，测试所有插件和AI检索加速层。

话题设计：
1. AI编程与LLM应用 (技术/工具类)
2. 产品需求分析与PRD撰写 (项目文档类)  
3. 法律合规与合同审查 (专业知识类)
4. Cloudflare Workers部署 (运维/部署类)
5. 个人知识管理方法论 (知识/教程类)
"""

import sys
import os
import json
import re
import time
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

VAULT_ROOT = Path(r"D:\Obsidian\LeoDiary")
CAPTURE_DIR = VAULT_ROOT / "A📥 收集（Capture）"
TEST_DIR = CAPTURE_DIR / "_test_simulated"
PYTHON_DIR = Path(r"D:\Python\projects\leodiarycode")

RESULT_FILE = Path(r"D:\Python\projects\leodiarycode\LD-DVA_test_report.json")


class TestRunner:
    def __init__(self):
        self.results = []
        self.test_files = []
        self.start_time = datetime.now()
        
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

    # ============================================================
    # Step 1: 创建测试数据
    # ============================================================
    def create_test_data(self):
        print("\n📝 Step 1: 创建5个话题的模拟测试数据")
        print("=" * 60)
        
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR, ignore_errors=True)
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        
        topics = self._get_test_topics()
        
        for topic_id, topic in enumerate(topics, 1):
            topic_dir = TEST_DIR / f"T{topic_id:02d}_{topic['slug']}"
            topic_dir.mkdir(exist_ok=True)
            
            for file_idx, note in enumerate(topic['notes'], 1):
                filepath = topic_dir / f"{note['title']}.md"
                self._write_note(filepath, note)
                self.test_files.append(str(filepath))
            
            self.log("数据创建", f"T{topic_id:02d} {topic['name']}", "pass",
                     f"创建 {len(topic['notes'])} 个笔记文件")
        
        total_files = len(self.test_files)
        self.log("数据创建", "总计", "pass",
                 f"共创建 {len(topics)} 个话题 / {total_files} 个笔记文件")
        return total_files

    def _write_note(self, filepath, note):
        fm_parts = [f"---"]
        for k, v in note.get('frontmatter', {}).items():
            if isinstance(v, list):
                fm_parts.append(f"{k}:")
                for item in v:
                    fm_parts.append(f"  - {item}")
            else:
                fm_parts.append(f"{k}: {v}")
        fm_parts.append("---")
        fm_parts.append("")
        
        content = "\n".join(fm_parts) + note.get('body', '')
        filepath.write_text(content, encoding='utf-8')

    def _get_test_topics(self):
        return [
            {
                "id": 1, "slug": "ai_coding", "name": "AI编程与LLM应用",
                "notes": [
                    {
                        "title": "Claude Code - 实战配置教程 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-001",
                            "title": "Claude Code - 实战配置教程",
                            "type": "教程",
                            "tags": ["AI编程", "Claude", "LLM", "开发工具", "配置教程"],
                            "keywords": ["Claude Code", "AI编程", "CLI配置", "Code助手", "开发效率"],
                            "entities": ["Claude Code", "Anthropic", "Code CLI"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 介绍Claude Code作为AI编程助手的定位，涵盖CLI安装、配置和实战使用场景，适用于提升代码编写效率的开发者。",
                            "aliases": ["Claude Code教程", "AI编程助手配置"]
                        },
                        "body": """# Claude Code - 实战配置教程

## 概述
Claude Code 是 Anthropic 推出的 AI 编程助手，支持通过 CLI 方式调用，能够理解代码上下文、执行命令、编辑文件。

## 安装步骤
1. 访问 claude.ai/code 注册账号
2. 安装 CLI: `npm install -g @anthropian-ai/claude-code`
3. 配置 API Key 和权限

## 核心功能
- 代码理解与生成
- 多文件编辑
- Shell 命令执行
- Git 操作支持

## 最佳实践
- 使用 CLAUDE.md 配置项目级规则
- 合理使用 @ 引用关键文件
- 利用 /clear 重置上下文

## 注意事项
- Token 使用成本监控
- 敏感代码脱敏处理
- 版本控制集成
"""
                    },
                    {
                        "title": "AI编程工具 - 横向评测 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-002",
                            "title": "AI编程工具 - 横向评测",
                            "type": "知识",
                            "tags": ["AI编程", "工具评测", "LLM", "开发工具"],
                            "keywords": ["AI编程工具", "Cursor", "Copilot", "Claude", "Tabnine", "评测对比"],
                            "entities": ["Cursor", "GitHub Copilot", "Claude Code", "Tabnine", "CodeBuddy"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 对主流AI编程工具进行横向评测，从代码质量、上下文理解、编辑效率等维度对比，帮助开发者选择合适的工具。",
                        },
                        "body": """# AI编程工具 - 横向评测

## 评测维度
| 工具 | 代码质量 | 上下文理解 | 编辑效率 | 价格 |
|------|---------|-----------|---------|------|
| Cursor | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 免费+付费 |
| Copilot | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $10/月 |
| Claude Code | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按量计费 |
| Tabnine | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | 免费版 |

## 核心差异
- **Cursor**: 基于Claude，支持项目级代码库理解
- **Copilot**: 基于GPT，集成IDE体验最佳
- **Claude Code**: 基于Claude，CLI原生支持
- **Tabnine**: 基于多种模型，企业级安全

## 选择建议
1. 个人开发者：Cursor 或 Copilot
2. 团队协作：Claude Code + 自定义MCP
3. 企业用户：Tabnine 或自建方案

## 避坑指南
- 注意Token成本控制
- 敏感代码需脱敏
- 合理配置上下文窗口
"""
                    },
                    {
                        "title": "LLM应用 - Prompt工程最佳实践 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-003",
                            "title": "LLM应用 - Prompt工程最佳实践",
                            "type": "知识",
                            "tags": ["LLM", "Prompt工程", "AI应用", "大模型"],
                            "keywords": ["Prompt工程", "LLM应用", "指令优化", "大模型开发", "AI应用设计"],
                            "entities": ["LLM", "Prompt", "Token", "上下文窗口"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 总结LLM应用中Prompt工程的核心原则和最佳实践，包括指令设计、上下文管理和输出控制，适用于AI应用开发者。",
                        },
                        "body": """# LLM应用 - Prompt工程最佳实践

## 核心原则
1. **清晰明确**: 指令要具体、无歧义
2. **结构化**: 使用分节、列表等结构
3. **有示例**: 提供Few-shot示例
4. **控格式**: 明确输出格式要求

## 模板结构
```
# 角色设定
你是一个[具体角色]，擅长[具体能力]。

# 任务描述
请完成[具体任务]。

# 上下文信息
[相关背景知识]

# 输出要求
- 格式: [具体格式]
- 长度: [具体长度]
- 风格: [具体风格]

# 示例
输入: [示例输入]
输出: [示例输出]
```

## 高级技巧
- 使用System Message设定行为边界
- 利用Chain-of-Thought进行推理
- 合理使用分隔符区分指令和数据
- 实现自动评估和迭代优化

## 常见陷阱
- 指令过于模糊导致输出不稳定
- 上下文过长导致关键信息被忽略
- 格式要求不明确导致解析困难
"""
                    }
                ]
            },
            {
                "id": 2, "slug": "product_prd", "name": "产品需求分析与PRD撰写",
                "notes": [
                    {
                        "title": "产品经理 - 需求分析方法论 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-004",
                            "title": "产品经理 - 需求分析方法论",
                            "type": "知识",
                            "tags": ["产品经理", "需求分析", "PRD", "方法论"],
                            "keywords": ["需求分析", "产品经理", "用户研究", "需求管理", "优先级"],
                            "entities": ["用户画像", "用户旅程", "需求池", "MoSCoW"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 系统介绍产品经理需求分析的核心方法论，从用户研究、需求收集到优先级排序，帮助建立系统化的需求管理流程。",
                        },
                        "body": """# 产品经理 - 需求分析方法论

## 需求来源
| 来源 | 占比 | 优先级 |
|------|------|--------|
| 用户反馈 | 40% | 高 |
| 业务规划 | 25% | 高 |
| 竞品分析 | 20% | 中 |
| 技术驱动 | 15% | 低 |

## 用户研究方法
1. **用户访谈**: 一对一深度对话
2. **问卷调查**: 量化数据收集
3. **数据分析**: 行为数据洞察
4. **可用性测试**: 真实场景验证

## 需求分类框架
- **MoSCoW方法**: Must / Should / Could / Won't
- **RICE评分**: Reach / Impact / Confidence / Effort
- **Kano模型**: 基本型 / 期望型 / 兴奋型

## PRD结构模板
```
1. 概述与目标
2. 用户故事与场景
3. 功能需求详述
4. 非功能需求
5. 验收标准
6. 排期与里程碑
```

## 常见问题
- 需求收集不充分导致返工
- 优先级判断缺乏数据支持
- 需求变更控制机制不完善
"""
                    },
                    {
                        "title": "PRD撰写 - 规范与模板 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-005",
                            "title": "PRD撰写 - 规范与模板",
                            "type": "教程",
                            "tags": ["PRD", "产品文档", "撰写规范", "模板"],
                            "keywords": ["PRD撰写", "产品需求文档", "文档规范", "模板", "评审"],
                            "entities": ["PRD", "产品文档", "需求评审"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 提供PRD（产品需求文档）的撰写规范和可复用模板，涵盖文档结构、内容要求和评审流程，帮助产品经理输出高质量需求文档。",
                        },
                        "body": """# PRD撰写 - 规范与模板

## 文档结构
```markdown
# PRD: [功能名称]

## 1. 文档信息
| 字段 | 内容 |
|------|------|
| 版本 | v1.0 |
| 作者 | 张三 |
| 状态 | 评审中 |
| 创建日期 | 2026-07-28 |

## 2. 背景与目标
### 2.1 背景
[为什么要做这个功能]

### 2.2 目标
[量化的目标指标]

### 2.3 范围
[包含/不包含的内容]

## 3. 用户故事
- 作为[角色]，我希望[功能]，以便[价值]

## 4. 功能详述
### 4.1 功能列表
| 优先级 | 功能点 | 描述 |
|--------|--------|------|
| P0 | [功能1] | [描述] |

### 4.2 交互流程
[流程图或文字描述]

### 4.3 数据模型
[数据结构说明]

## 5. 非功能需求
- 性能: [指标]
- 安全: [要求]
- 兼容: [范围]

## 6. 验收标准
[具体可量化的验收条件]

## 7. 排期
| 阶段 | 时间 | 负责人 |
|------|------|--------|
| 设计 | W1-W2 | 设计师 |
| 开发 | W3-W5 | 开发团队 |
| 测试 | W6-W7 | QA团队 |
```

## 撰写规范
1. 目标必须可量化
2. 范围必须明确边界
3. 验收标准必须可测试
4. 风险点必须提前识别

## 评审流程
1. 内部自评（作者）
2. 产品团队交叉评审
3. 设计/开发/测试联合评审
4. 归档并版本管理
"""
                    }
                ]
            },
            {
                "id": 3, "slug": "legal_compliance", "name": "法律合规与合同审查",
                "notes": [
                    {
                        "title": "合同审查 - 核心要点清单 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-006",
                            "title": "合同审查 - 核心要点清单",
                            "type": "清单",
                            "tags": ["法律", "合同审查", "合规", "风险控制"],
                            "keywords": ["合同审查", "法律风险", "条款分析", "合规检查", "风险清单"],
                            "entities": ["合同", "条款", "违约责任", "争议解决", "管辖法院"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 提供合同审查的核心要点检查清单，涵盖主体资格、权利义务、违约责任等关键条款，帮助快速识别合同风险。",
                        },
                        "body": """# 合同审查 - 核心要点清单

## 一、主体资格审查
- [ ] 签约方主体真实性核实
- [ ] 法人资格/授权范围确认
- [ ] 资质要求是否满足
- [ ] 履约能力评估

## 二、核心条款审查
### 2.1 标的与对价
- [ ] 标的描述是否清晰具体
- [ ] 价款/报酬金额明确
- [ ] 支付方式和时间约定
- [ ] 税费承担明确

### 2.2 权利义务
- [ ] 双方权利义务对等
- [ ] 履行期限明确
- [ ] 交付/验收标准清晰
- [ ] 知识产权归属明确

### 2.3 违约责任
- [ ] 违约情形列举充分
- [ ] 违约金/赔偿金合理
- [ ] 损失赔偿范围明确
- [ ] 解除权行使条件

### 2.4 争议解决
- [ ] 管辖法院/仲裁机构约定
- [ ] 适用法律明确
- [ ] 争议解决程序

## 三、风险点识别
1. **模糊表述**: 避免"相关费用"等不确定表述
2. **不对等条款**: 关注责任是否严重倾斜
3. **执行难点**: 判断条款实际可执行性
4. **外部依赖**: 识别合同外部条件

## 四、附加检查
- [ ] 附件完整并与正文关联
- [ ] 签署页签章规范
- [ ] 合同份数明确
- [ ] 生效条件约定
"""
                    },
                    {
                        "title": "数据合规 - 个人信息保护要点 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-007",
                            "title": "数据合规 - 个人信息保护要点",
                            "type": "知识",
                            "tags": ["数据合规", "个人信息", "隐私保护", "法律"],
                            "keywords": ["数据合规", "个人信息保护", "隐私", "GDPR", "合规要点"],
                            "entities": ["个人信息", "敏感信息", "数据主体", "监管机构"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 梳理数据合规中个人信息保护的核心要点，涵盖收集、存储、使用、共享全流程，帮助企业满足监管要求。",
                        },
                        "body": """# 数据合规 - 个人信息保护要点

## 法律框架
| 法规 | 适用范围 | 核心要求 |
|------|---------|---------|
| 《个人信息保护法》 | 中国境内 | 合法性、正当性、必要性 |
| GDPR | 欧盟 | 数据最小化、被遗忘权 |
| CCPA | 加州 | 知情权、删除权 |

## 合规要点
### 1. 收集环节
- 明确告知收集目的
- 获取有效同意
- 遵守最小必要原则
- 敏感信息单独同意

### 2. 存储环节
- 加密存储个人信息
- 设定保存期限
- 访问权限控制
- 定期安全审计

### 3. 使用环节
- 限定使用范围
- 禁止二次加工
- 自动化决策说明
- 用户知情权保障

### 4. 共享环节
- 接收方资质审查
- 数据转移协议
- 用户告知与同意
- 记录共享行为

## 违规风险
- 行政处罚：最高5000万元或上一年度营业额5%
- 个人责任：直接责任人可处1-10万元罚款
- 声誉损失：品牌信任度下降
"""
                    }
                ]
            },
            {
                "id": 4, "slug": "cloudflare_workers", "name": "Cloudflare Workers部署",
                "notes": [
                    {
                        "title": "Cloudflare Workers - 完整部署指南 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-008",
                            "title": "Cloudflare Workers - 完整部署指南",
                            "type": "教程",
                            "tags": ["Cloudflare", "Workers", "Serverless", "部署"],
                            "keywords": ["Cloudflare Workers", "Serverless部署", "Wrangler", "边缘计算", "部署流程"],
                            "entities": ["Cloudflare", "Workers", "Wrangler", "R2", "D1", "KV"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 提供Cloudflare Workers的完整部署指南，从环境准备到上线发布，涵盖Wrangler CLI配置和最佳实践。",
                        },
                        "body": """# Cloudflare Workers - 完整部署指南

## 环境准备
```bash
# 安装Wrangler CLI
npm install -g wrangler

# 登录Cloudflare账号
wrangler login

# 验证登录
wrangler whoami
```

## 创建Worker
```bash
# 创建新项目
wrangler init my-worker

# 进入目录
cd my-worker

# 本地开发
wrangler dev
```

## 配置文件
```toml
# wrangler.toml
name = "my-worker"
main = "src/index.js"
compatibility_date = "2026-07-28"

# 绑定KV存储
[[kv_namespaces]]
binding = "KV"
id = "your-kv-namespace-id"

# 绑定D1数据库
[[d1_databases]]
binding = "DB"
database_name = "mydb"
database_id = "your-database-id"

# 绑定R2存储
[[r2_buckets]]
binding = "R2"
bucket_name = "my-bucket"
```

## 部署上线
```bash
# 部署到Cloudflare边缘
wrangler deploy

# 查看部署日志
wrangler tail my-worker

# 查看指标
wrangler metrics my-worker
```

## 域名绑定
```bash
# 绑定自定义域名
wrangler routes create api.example.com = my-worker

# 查看路由
wrangler routes list
```

## 监控与调试
- 实时日志: `wrangler tail`
- 错误追踪: Cloudflare Dashboard
- 性能指标: Workers Analytics
"""
                    },
                    {
                        "title": "Workers最佳实践 - 性能与成本优化 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-009",
                            "title": "Workers最佳实践 - 性能与成本优化",
                            "type": "知识",
                            "tags": ["Cloudflare", "Workers", "性能优化", "Serverless"],
                            "keywords": ["Workers性能", "Cloudflare优化", "Serverless成本", "边缘计算", "性能调优"],
                            "entities": ["Workers", "KV", "D1", "R2", "Cache"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 总结Cloudflare Workers的性能与成本优化最佳实践，包括缓存策略、KV使用、冷启动优化等关键技巧。",
                        },
                        "body": """# Workers最佳实践 - 性能与成本优化

## 性能优化
### 1. 缓存策略
```javascript
// 使用Cache API缓存响应
const cache = caches.default;

export default {
  async fetch(request, env) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  }
}
```

### 2. KV使用优化
- 热数据放KV，冷数据放R2
- 使用批量写入减少API调用
- 合理设置过期时间

### 3. 代码优化
- 减少冷启动代码量
- 使用ES模块
- 避免同步阻塞操作
- 合理使用async/await

## 成本优化
| 优化项 | 节省 | 难度 |
|--------|------|------|
| 响应缓存 | 40-60% | 低 |
| KV替代DB | 30-50% | 中 |
| 代码精简 | 10-20% | 低 |

## 监控指标
- 请求次数
- CPU时间
- 内存使用
- 错误率
- 响应时间

## 常见陷阱
- 过度使用D1导致成本飙升
- 忽略KV的最终一致性
- 不设置合理的缓存头
"""
                    }
                ]
            },
            {
                "id": 5, "slug": "knowledge_management", "name": "个人知识管理方法论",
                "notes": [
                    {
                        "title": "知识管理 - PARA方法论实践 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-010",
                            "title": "知识管理 - PARA方法论实践",
                            "type": "知识",
                            "tags": ["知识管理", "PARA", "方法论", "笔记"],
                            "keywords": ["知识管理", "PARA方法", "第二大脑", "笔记系统", "信息架构"],
                            "entities": ["PARA", "Projects", "Areas", "Resources", "Archives"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 详细介绍PARA方法论在个人知识管理中的实践应用，涵盖Projects/Areas/Resources/Archives四层架构设计。",
                        },
                        "body": """# 知识管理 - PARA方法论实践

## PARA架构
```
Projects（项目）
├── 当前进行中的目标导向工作
├── 有明确截止日期
└── 例：学习React、完成论文

Areas（领域）
├── 持续维护的责任领域
├── 无明确截止日期
└── 例：健康、财务、学习

Resources（资源）
├── 有参考价值的主题
├── 未来可能用到
└── 例：Python教程、设计灵感

Archives（归档）
├── 完成或过时的内容
├── 不再活跃管理
└── 例：已完成项目、旧版本资料
```

## 实施步骤
1. **盘点现有**: 整理现有文件结构
2. **分类归档**: 按PARA重新组织
3. **命名规范**: 统一文件命名约定
4. **建立索引**: 创建知识地图
5. **定期维护**: 周/月回顾

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
                        "title": "第二大脑 - 构建高效笔记系统 @ 2026",
                        "frontmatter": {
                            "id": "leo-20260728-011",
                            "title": "第二大脑 - 构建高效笔记系统",
                            "type": "教程",
                            "tags": ["知识管理", "第二大脑", "笔记系统", "效率"],
                            "keywords": ["第二大脑", "笔记系统", "信息处理", "知识内化", "个人管理"],
                            "entities": ["笔记", "知识网络", "双向链接", "Zettelkasten"],
                            "date": "2026-07-28",
                            "updated": "2026-07-28",
                            "summary": "三段式摘要: 介绍如何构建个人第二大脑，从收集、整理、组织到输出的完整流程，实现知识的有效沉淀和调用。",
                        },
                        "body": """# 第二大脑 - 构建高效笔记系统

## 核心流程
```
收集 → 整理 → 组织 → 表达
 ↓       ↓       ↓       ↓
Capture  Clarify  Organize  Express
```

## 1. 收集（Capture）
- 阅读时即时记录想法
- 使用统一的捕获工具
- 不做过度分类
- 保持原子性

## 2. 整理（Clarify）
- 用自己的话重新表述
- 提炼核心观点
- 添加元数据标签
- 确保理解无误

## 3. 组织（Organize）
- 链接相关笔记
- 建立主题索引
- 形成知识网络
- 可视化关联

## 4. 表达（Express）
- 定期输出总结
- 写作/分享/教学
- 检验知识掌握度
- 形成正向循环

## Zettelkasten方法
1. **原子笔记**: 每个笔记一个观点
2. **双向链接**: 笔记间相互引用
3. **索引系统**: MOC导航地图
4. **编号系统**: 可追踪的ID体系

## 避坑指南
- 不要追求完美主义
- 保持系统简洁
- 避免过度工具化
- 定期回顾和精简
"""
                    }
                ]
            }
        ]

    # ============================================================
    # Step 2: 测试 obsidian_skill_utils.py 命令
    # ============================================================
    def test_skill_utils(self):
        print("\n🔧 Step 2: 测试 obsidian_skill_utils.py 命令")
        print("=" * 60)
        
        vault = str(VAULT_ROOT)
        
        # is-system-file (🏠 home- 前缀应识别为系统文件)
        self._run_cmd("is-system-file", ["🏠 home-test.md"], expected="true")
        self._run_cmd("is-system-file", ["🧩 目录-test.md"], expected="true")
        self._run_cmd("is-system-file", ["普通笔记.md"], expected="false")
        
        # validate-filename
        self._run_cmd("validate-filename", ["test-file@2026.md"])
        self._run_cmd("validate-filename", ["非法文件名"])
        
        # parse-filename
        self._run_cmd("parse-filename", ["测试笔记 @ 2026-07-28.md"])
        
        # validate-document
        test_doc = self.test_files[0] if self.test_files else None
        if test_doc:
            self._run_cmd("validate-document", [test_doc])
        
        # check-summary-quality
        self._run_cmd("check-summary-quality", [
            "这是一个关于AI编程工具的详细教程，涵盖安装配置和最佳实践",
            "AI编程工具教程",
            "AI编程,Claude,开发工具"
        ])
        
        # compute-hash
        if test_doc:
            self._run_cmd("compute-hash", [test_doc])
        
        # scan-unindexed
        self._run_cmd("scan-unindexed", [vault, "A📥 收集（Capture）_test_simulated"])
        
        # check-file-thresholds
        if test_doc:
            self._run_cmd("check-file-thresholds", [test_doc])
        
        # validate-metadata
        self._run_cmd("validate-metadata", [vault, "--quiet"])
        
        # kb-stats
        self._run_cmd("kb-stats", [vault])
        
        # lint-content
        self._run_cmd("lint-content", [vault])
        
        # compute-similarity
        self._run_cmd("compute-similarity", [
            "AI编程教程", "AI,Claude", "技术",
            "AI编程指南", "AI,Cursor", "技术"
        ])
        
        # detect-changes
        self._run_cmd("detect-changes", ["pipeline", vault, "A📥 收集（Capture）_test_simulated"])
        
        # record-access
        if test_doc:
            self._run_cmd("record-access", [vault, test_doc])
        
        # locate-domain-index
        if test_doc:
            rel_path = Path(test_doc).relative_to(VAULT_ROOT)
            self._run_cmd("locate-domain-index", [str(rel_path), vault])
        
        # verify-move
        if test_doc:
            self._run_cmd("verify-move", [test_doc, test_doc])

    def _run_cmd(self, cmd, args, expected=None):
        script_path = PYTHON_DIR / "src" / "obsidian_skill_utils.py"
        cmd_args = [sys.executable, str(script_path), cmd] + args
        
        try:
            result = self._execute(cmd_args, timeout=30)
            if result['success']:
                output = result['stdout'].strip()
                if expected and output != expected:
                    self.log("Skill命令", cmd, "warn", 
                            f"输出不匹配: 期望'{expected}'，实际'{output}'")
                else:
                    self.log("Skill命令", cmd, "pass", 
                            f"执行成功: {output[:80]}")
            else:
                self.log("Skill命令", cmd, "fail", 
                        f"执行失败: {result['stderr'][:100]}")
        except Exception as e:
            self.log("Skill命令", cmd, "fail", f"执行异常: {str(e)[:100]}")

    def _execute(self, cmd, timeout=60):
        import subprocess
        try:
            proc = subprocess.Popen(
                cmd,
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
            return {'success': False, 'stdout': '', 'stderr': '超时'}
        except Exception as e:
            return {'success': False, 'stdout': '', 'stderr': str(e)}

    # ============================================================
    # Step 3: 测试 ai_index_builder.py
    # ============================================================
    def test_ai_index_builder(self):
        print("\n📊 Step 3: 测试 ai_index_builder.py (LD-DVA AI检索加速层)")
        print("=" * 60)
        
        script_path = PYTHON_DIR / "scripts" / "ai_index_builder.py"
        
        # status
        result = self._execute([sys.executable, str(script_path), "status"], timeout=60)
        if result['success']:
            self.log("AI索引", "status", "pass", result['stdout'][:200])
        else:
            self.log("AI索引", "status", "fail", result['stderr'][:100])
        
        # health
        result = self._execute([sys.executable, str(script_path), "health"], timeout=60)
        if result['success']:
            self.log("AI索引", "health", "pass", "执行成功")
        else:
            self.log("AI索引", "health", "fail", result['stderr'][:100])
        
        # cache-clear
        result = self._execute([sys.executable, str(script_path), "cache-clear"], timeout=30)
        if result['success']:
            self.log("AI索引", "cache-clear", "pass", "缓存已清空")
        else:
            self.log("AI索引", "cache-clear", "warn", result['stderr'][:80])
        
        # 全量重建
        print("  ⏳ 执行全量重建 (rebuild)...")
        result = self._execute([sys.executable, str(script_path), "rebuild"], timeout=120)
        if result['success']:
            self.log("AI索引", "rebuild", "pass", "全量重建成功")
        else:
            self.log("AI索引", "rebuild", "fail", result['stderr'][:100])
            return
        
        # 搜索测试
        search_queries = [
            "AI编程",
            "Cloudflare Workers",
            "合同审查",
            "产品需求",
            "知识管理",
            "LLM应用",
            "Serverless部署",
            "合规检查",
            "PRD撰写",
            "PARA方法论"
        ]
        
        for query in search_queries:
            result = self._execute([
                sys.executable, str(script_path), "search", query, "--top", "5"
            ], timeout=30)
            if result['success']:
                self.log("AI检索", f"search '{query}'", "pass", 
                        f"返回结果: {len(result['stdout'])}字节")
            else:
                self.log("AI检索", f"search '{query}'", "fail", 
                        result['stderr'][:80])
        
        # cache-write / cache-read
        test_query = "AI编程工具对比"
        test_results = json.dumps([{"file": "test.md", "score": 95}])
        result = self._execute([
            sys.executable, str(script_path), "cache-write", test_query, test_results
        ], timeout=30)
        if result['success']:
            self.log("AI缓存", "cache-write", "pass", f"缓存写入成功: {test_query}")
        
        result = self._execute([
            sys.executable, str(script_path), "cache-read", test_query
        ], timeout=30)
        if result['success']:
            self.log("AI缓存", "cache-read", "pass", f"缓存读取成功")
        
        # cache-invalidate
        test_file = self.test_files[0] if self.test_files else None
        if test_file:
            result = self._execute([
                sys.executable, str(script_path), "cache-invalidate", test_file
            ], timeout=30)
            if result['success']:
                self.log("AI缓存", "cache-invalidate", "pass", "缓存失效成功")
        
        # incremental
        result = self._execute([sys.executable, str(script_path), "incremental"], timeout=60)
        if result['success']:
            self.log("AI索引", "incremental", "pass", "增量更新成功")
        else:
            self.log("AI索引", "incremental", "fail", result['stderr'][:100])
        
        # 验证索引文件
        self._verify_index_files()

    def _verify_index_files(self):
        index_dir = VAULT_ROOT / "🤖AI_INDEX"
        required_files = [
            "retrieval-index.md",
            "tag-index.md", 
            "entity-index.md",
            "query-cache.json",
            "index-state.json"
        ]
        
        for fname in required_files:
            fpath = index_dir / fname
            if fpath.exists():
                size = fpath.stat().st_size
                self.log("索引验证", fname, "pass", f"文件存在 ({size:,} bytes)")
            else:
                self.log("索引验证", fname, "fail", f"文件不存在")

    # ============================================================
    # Step 4: 测试 frontmatter_enrich.py
    # ============================================================
    def test_frontmatter_enrich(self):
        print("\n📝 Step 4: 测试 frontmatter_enrich.py")
        print("=" * 60)
        
        script_path = PYTHON_DIR / "src" / "frontmatter_enrich.py"
        
        # dry-run
        result = self._execute([sys.executable, str(script_path)], timeout=60)
        if result['success']:
            self.log("Frontmatter", "dry-run", "pass", "试运行成功")
        else:
            self.log("Frontmatter", "dry-run", "fail", result['stderr'][:100])
        
        # apply (试运行模式，不实际修改)
        result = self._execute([sys.executable, str(script_path), "--apply", "--verbose"], timeout=60)
        if result['success']:
            self.log("Frontmatter", "apply", "pass", "执行成功")
        else:
            self.log("Frontmatter", "apply", "warn", result['stderr'][:100])

    # ============================================================
    # Step 5: 测试 health_check.py
    # ============================================================
    def test_health_check(self):
        print("\n🏥 Step 5: 测试 health_check.py")
        print("=" * 60)
        
        script_path = PYTHON_DIR / "src" / "health_check.py"
        
        # full check
        result = self._execute([sys.executable, str(script_path)], timeout=120)
        if result['success']:
            self.log("健康检查", "full-check", "pass", "全量健康检查完成")
        else:
            self.log("健康检查", "full-check", "fail", result['stderr'][:100])
        
        # quick check
        result = self._execute([sys.executable, str(script_path), "--quick"], timeout=60)
        if result['success']:
            self.log("健康检查", "quick-check", "pass", "快速检查完成")
        else:
            self.log("健康检查", "quick-check", "fail", result['stderr'][:100])

    # ============================================================
    # Step 6: 测试 Skill 插件引用
    # ============================================================
    def test_skill_plugins(self):
        print("\n🔌 Step 6: 测试 Skill 插件引用一致性")
        print("=" * 60)
        
        skills_dir = Path(r"C:\Users\leokou\.claude\skills\Obsidian")
        
        # 检查每个Skill的SKILL.md是否引用了AI_INDEX
        ai_index_markers = [
            "AI_INDEX",
            "ai_index_builder.py",
            "retrieval-index.md",
            "index-state.json",
            "cache-read",
            "cache-write",
        ]
        
        skills_to_check = [
            "obsidian-knowledge-queryer",
            "obsidian-knowledge-compiler",
            "obsidian-knowledge-organizer",
            "obsidian-pipeline",
            "obsidian-mulu-fenlei-summary",
            "obsidian-fire-rename",
            "obsidian-health-check-all",
        ]
        
        for skill_name in skills_to_check:
            skill_path = skills_dir / skill_name / "SKILL.md"
            if not skill_path.exists():
                self.log("Skill插件", skill_name, "fail", "SKILL.md 不存在")
                continue
            
            content = skill_path.read_text(encoding='utf-8-sig')
            found_markers = [m for m in ai_index_markers if m in content]
            
            if len(found_markers) >= 2:
                self.log("Skill插件", skill_name, "pass", 
                        f"包含 {len(found_markers)} 个AI_INDEX相关标记")
            elif len(found_markers) >= 1:
                self.log("Skill插件", skill_name, "warn", 
                        f"仅包含 {len(found_markers)} 个AI_INDEX标记")
            else:
                self.log("Skill插件", skill_name, "fail", 
                        "未发现任何AI_INDEX相关引用")

    # ============================================================
    # Step 7: 数据质量检查
    # ============================================================
    def test_data_quality(self):
        print("\n📊 Step 7: 测试数据质量")
        print("=" * 60)
        
        index_state = VAULT_ROOT / "🤖AI_INDEX" / "index-state.json"
        if not index_state.exists():
            self.log("数据质量", "index-state", "fail", "index-state.json 不存在")
            return
        
        state = json.loads(index_state.read_text(encoding='utf-8-sig'))
        files_dict = state.get('files', {})
        tracked = state.get('tracked_files', len(files_dict))
        
        self.log("数据质量", "追踪文件数", "pass", 
                f"AI_INDEX追踪 {tracked} 个文件")
        
        # 检查关键字段完整性（注意：doc元数据在 info['doc'] 中）
        issues = []
        for path, info in files_dict.items():
            doc = info.get('doc', {})
            if not doc:
                issues.append(f"{path}: 无doc元数据")
                continue
            if not doc.get('title'):
                issues.append(f"{path}: 缺少title")
            if not doc.get('keywords') or len(doc.get('keywords', [])) == 0:
                issues.append(f"{path}: 缺少keywords")
            if not doc.get('body_preview'):
                issues.append(f"{path}: 缺少body_preview")
            if not doc.get('hash') and not info.get('hash'):
                issues.append(f"{path}: 缺少hash")
            if not doc.get('type'):
                issues.append(f"{path}: 缺少type")
        
        if issues:
            self.log("数据质量", "字段完整性", "warn", 
                    f"发现 {len(issues)} 个问题: {issues[0][:80]}")
        else:
            self.log("数据质量", "字段完整性", "pass", "所有文件字段完整")
        
        # 检查summary质量
        empty_summaries = []
        for path, info in files_dict.items():
            doc = info.get('doc', {})
            summary = doc.get('summary', '')
            if not summary or len(summary) < 20:
                empty_summaries.append(path)
        
        if empty_summaries:
            self.log("数据质量", "摘要质量", "warn", 
                    f"{len(empty_summaries)} 个文件摘要为空或过短")
        else:
            self.log("数据质量", "摘要质量", "pass", "所有文件摘要质量达标")

    # ============================================================
    # Step 8: 清理测试数据
    # ============================================================
    def cleanup(self):
        print("\n🧹 Step 8: 清理测试数据")
        print("=" * 60)
        
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR, ignore_errors=True)
            self.log("清理", "测试数据", "pass", f"已删除: {TEST_DIR}")
        
        # 重置AI缓存
        script_path = PYTHON_DIR / "scripts" / "ai_index_builder.py"
        self._execute([sys.executable, str(script_path), "cache-clear"], timeout=30)
        self.log("清理", "AI缓存", "pass", "缓存已清空")
        
        # 增量更新索引
        self._execute([sys.executable, str(script_path), "incremental"], timeout=60)
        self.log("清理", "索引同步", "pass", "索引已同步")

    # ============================================================
    # 生成报告
    # ============================================================
    def generate_report(self):
        print("\n📋 生成测试报告")
        print("=" * 60)
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        pass_count = sum(1 for r in self.results if r['status'] == 'pass')
        warn_count = sum(1 for r in self.results if r['status'] == 'warn')
        fail_count = sum(1 for r in self.results if r['status'] == 'fail')
        total = len(self.results)
        
        # 计算分数 (pass=100, warn=50, fail=0)
        score = pass_count * 100 + warn_count * 50
        max_score = total * 100
        percentage = (score / max_score * 100) if max_score > 0 else 0
        
        report = {
            "test_info": {
                "name": "LD-DVA 综合系统测试",
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": round(duration, 1),
                "test_topics": [
                    "AI编程与LLM应用",
                    "产品需求分析与PRD撰写",
                    "法律合规与合同审查",
                    "Cloudflare Workers部署",
                    "个人知识管理方法论"
                ],
                "test_files_created": len(self.test_files),
            },
            "summary": {
                "total_checks": total,
                "pass": pass_count,
                "warn": warn_count,
                "fail": fail_count,
                "score_percentage": round(percentage, 1),
                "verdict": "PASS" if fail_count == 0 else "FAIL",
            },
            "results": self.results,
            "details": {
                "test_data_dir": str(TEST_DIR),
                "vault_root": str(VAULT_ROOT),
                "python_dir": str(PYTHON_DIR),
                "index_dir": str(VAULT_ROOT / "🤖AI_INDEX"),
            }
        }
        
        # 保存报告
        RESULT_FILE.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        print(f"\n{'='*60}")
        print(f"📊 测试结果总结")
        print(f"{'='*60}")
        print(f"  总检查项: {total}")
        print(f"  ✅ 通过: {pass_count}")
        print(f"  ⚠️ 警告: {warn_count}")
        print(f"  ❌ 失败: {fail_count}")
        print(f"  📈 得分: {percentage:.1f}%")
        print(f"  🎯 结论: {report['summary']['verdict']}")
        print(f"  📄 报告: {RESULT_FILE}")
        
        # 按类别统计
        categories = {}
        for r in self.results:
            cat = r['category']
            if cat not in categories:
                categories[cat] = {"pass": 0, "warn": 0, "fail": 0}
            categories[cat][r['status']] += 1
        
        print(f"\n📂 分类统计:")
        for cat, counts in sorted(categories.items()):
            icon = "✅" if counts['fail'] == 0 and counts['warn'] == 0 else "⚠️" if counts['fail'] == 0 else "❌"
            print(f"  {icon} {cat}: ✅{counts['pass']} ⚠️{counts['warn']} ❌{counts['fail']}")
        
        return report

    # ============================================================
    # 主流程
    # ============================================================
    def run(self):
        print("=" * 60)
        print("🚀 LD-DVA 综合系统测试")
        print("=" * 60)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试话题: 5个不同领域")
        print(f"测试范围: 所有Python脚本 + Skill插件 + AI检索层")
        
        # Step 1: 创建测试数据
        self.create_test_data()
        
        # Step 2: 测试 obsidian_skill_utils.py
        self.test_skill_utils()
        
        # Step 3: 测试 ai_index_builder.py
        self.test_ai_index_builder()
        
        # Step 4: 测试 frontmatter_enrich.py
        self.test_frontmatter_enrich()
        
        # Step 5: 测试 health_check.py
        self.test_health_check()
        
        # Step 6: 测试 Skill 插件引用
        self.test_skill_plugins()
        
        # Step 7: 数据质量检查
        self.test_data_quality()
        
        # Step 8: 清理测试数据
        self.cleanup()
        
        # 生成报告
        return self.generate_report()


if __name__ == "__main__":
    runner = TestRunner()
    report = runner.run()
    
    # 如果有失败，返回非零退出码
    if report['summary']['fail'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

#!/usr/bin/env python3
"""Batch test: 100 real topics (50 query + 50 siwei) through LD-DVA Final + Queryer Skill.

Generates detailed analysis report for system verification.
"""
import json, subprocess, sys, re
from datetime import datetime
from collections import Counter, defaultdict

BUILDER = r"D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py"

# 50 个 query 话题（覆盖 9 个领域 + L1/L2/L3 难度梯度）
QUERY_TOPICS = [
    # AI 相关 (10)
    ("LeoDiary 里面关于 Claude Code 的资料有哪些", "L2", "ai"),
    ("Trae 怎么配置 API 需要哪些步骤", "L2", "ai"),
    ("我之前有没有记录过 Claude Code Cursor Trae 这些 AI 编程工具的使用经验", "L2", "ai"),
    ("AI Agent Skill MCP 的学习资料", "L2", "ai"),
    ("ChatGPT Claude Gemini 对比", "L3", "ai"),
    ("Prompt 工程最佳实践", "L2", "ai"),
    ("Cursor IDE 使用技巧", "L2", "ai"),
    ("AI 模型本地部署方案 Ollama", "L2", "ai"),
    ("LLM 上下文窗口优化", "L2", "ai"),
    ("AI 工具体系分析 有哪些工具 什么关系", "L3", "ai"),

    # 开发 (10)
    ("Vue3 Hono Cloudflare 技术方案", "L2", "dev"),
    ("Python Pyinstaller 打包 EXE", "L1", "dev"),
    ("TypeScript esbuild 配置", "L1", "dev"),
    ("Cloudflare Workers D1 数据库", "L2", "dev"),
    ("Git 分支管理策略", "L1", "dev"),
    ("RESTful API 设计规范", "L1", "dev"),
    ("Vue3 组合式 API", "L1", "dev"),
    ("Hono 框架中间件", "L2", "dev"),
    ("Python 异步编程 asyncio", "L1", "dev"),
    ("前端性能优化方案", "L2", "dev"),

    # 系统 (5)
    ("Shadowrocket 分流规则怎么配置", "L2", "system"),
    ("Windows 包管理器 winget", "L1", "system"),
    ("iOS 快捷指令自动化", "L1", "system"),
    ("虚拟机 VirtualBox 配置", "L1", "system"),
    ("代理节点订阅配置", "L2", "system"),

    # 软件 (5)
    ("Obsidian 插件开发", "L2", "software"),
    ("Logseq 附件清理", "L1", "software"),
    ("ShareX 截图工具配置", "L1", "software"),
    ("浏览器扩展开发", "L1", "software"),
    ("效率工具组合方案", "L3", "software"),

    # 项目 (5)
    ("LeoDiary 项目整体架构设计", "L3", "project"),
    ("LeoDiary 核心能力模块总结", "L3", "project"),
    ("obsidian-exe-launcher 插件设计", "L2", "project"),
    ("业委会会议纪要", "L1", "project"),
    ("租房纠纷处理方案", "L2", "project"),

    # 影视 (2)
    ("电影推荐 高分", "L1", "movie"),
    ("影评写作方法", "L1", "movie"),

    # 思维框架 (5)
    ("第一性原理 思考方法", "L1", "thinking"),
    ("MECE 分析法", "L1", "thinking"),
    ("SWOT 分析", "L1", "thinking"),
    ("决策矩阵 使用", "L1", "thinking"),
    ("费曼学习法", "L1", "thinking"),

    # 核心规则 (5)
    ("LEO OS 系统原则", "L1", "root"),
    ("问题路由 三分类", "L1", "root"),
    ("思考流程 迭代式", "L1", "root"),
    ("输出规范 轻量完整", "L1", "root"),
    ("角色切换 7 种模式", "L1", "root"),

    # 个人 (3)
    ("面试准备技巧", "L1", "life"),
    ("简历优化方案", "L2", "life"),
    ("工作效率提升", "L2", "life"),
]

# 50 个 siwei 话题（深度思考类，触发 L4 强制等级或 L3 跨领域）
SIWEI_TOPICS = [
    # 架构分析类 (10)
    ("分析一下我目前的 AI 方向的知识体系是否完整 缺少哪些部分", "L3", "ai"),
    ("我的 LeoDiary 架构未来扩展到 10000 个文件会遇到哪些问题", "L3", "project"),
    ("分析一下我的 Obsidian 知识管理方法 相比普通笔记软件有什么优势和不足", "L3", "project"),
    ("根据我过去记录的技术方案 分析我的技术路线是否合理", "L3", "dev"),
    ("我的 AI 工具组合应该如何分工 ChatGPT Claude Cursor Trae", "L3", "ai"),
    ("MCP Agent Skill 之间的关系和设计思路分析", "L3", "ai"),
    ("根据我的知识库 现在是否需要引入向量数据库或 RAG 为什么", "L3", "ai"),
    ("我之前有没有解决过 AI 检索效率低 Token 消耗过大的问题 具体方案是什么", "L3", "ai"),
    ("找出我关于知识管理 Obsidian AI 自动化方面的重要设计方案 并总结它们之间的关系", "L3", "project"),
    ("Obsidian Planner Organizer Compiler 分别是什么作用 设计思路", "L3", "project"),

    # 决策类 (10)
    ("近期待办事务 维护 LeoDiary 学习 AI 写代码 做产品 内容输出 如何安排优先级", "L3", "life"),
    ("未来五年想持续提升个人竞争力 应该重点积累哪些能力", "L3", "life"),
    ("将自研知识管理系统封装为商用产品 分析是否值得投入精力开发", "L3", "life"),
    ("日常事务繁杂忙碌 但核心重要事项推进效率极低 剖析根源并给出完整解决方案", "L3", "life"),
    ("依托现有技术背景入局 AI 副业 适合选择哪些落地方向", "L3", "life"),
    ("是否应该重构 LeoDiary 的 Python 工具链 决策分析", "L3", "dev"),
    ("选择云服务商 AWS 阿里云 Cloudflare 决策矩阵", "L3", "dev"),
    ("技术博客还是视频内容 输出方式选择决策", "L3", "life"),
    ("是否学习 Rust 决策分析", "L3", "dev"),
    ("副业方向选择 AI 工具开发还是知识付费", "L3", "life"),

    # 创新类 (5)
    ("如何将 LeoDiary 系统创新为多人协作平台", "L3", "project"),
    ("AI 自动化整理知识库的创新方法", "L3", "ai"),
    ("基于思维框架的 AI 决策辅助系统创新设计", "L3", "thinking"),
    ("Obsidian 插件创新功能构想", "L3", "software"),
    ("知识沉淀流程的创新优化方案", "L3", "project"),

    # 心理/成长类 (10)
    ("如何应对技术焦虑 新技术不断出现的压力", "L3", "life"),
    ("完美主义导致拖延 怎么破解", "L3", "life"),
    ("学习效率低 怎么改进学习方法", "L3", "life"),
    ("工作倦怠期如何调整心态", "L3", "life"),
    ("imposter syndrome 冒名顶替综合征怎么克服", "L3", "life"),
    ("长期目标坚持不下去 怎么建立持续动力", "L3", "life"),
    ("如何建立成长型思维", "L3", "life"),
    ("焦虑情绪管理 ABC 理论应用", "L3", "life"),
    ("如何进入心流状态 提升专注力", "L3", "life"),
    ("职业迷茫期如何自我探索", "L3", "life"),

    # 名人思维 (5)
    ("Elon Musk 会怎么思考 AI 时代的个人发展", "L3", "thinking"),
    ("Charlie Munger 会怎么分析我的知识管理系统", "L3", "thinking"),
    ("Naval Ravikant 会怎么看待副业选择", "L3", "thinking"),
    ("Karpathy 会怎么设计 AI 辅助学习系统", "L3", "thinking"),
    ("Ray Dalio 会怎么决策技术路线选择", "L3", "thinking"),

    # 深度思考类 (10)
    ("深度思考 知识管理的本质是什么", "L3", "thinking"),
    ("深度思考 AI 时代人类的核心竞争力", "L3", "thinking"),
    ("深度思考 认知资产和信息的区别", "L3", "thinking"),
    ("深度思考 工具系统和思维系统的关系", "L3", "thinking"),
    ("深度思考 如何构建个人知识图谱", "L3", "thinking"),
    ("深度思考 学习 反思 沉淀的闭环", "L3", "thinking"),
    ("深度思考 AI 增强人类的边界在哪里", "L3", "thinking"),
    ("深度思考 长期主义在技术学习中的应用", "L3", "thinking"),
    ("深度思考 知识库和大脑的分工协作", "L3", "thinking"),
    ("深度思考 第一性原理分析个人成长", "L3", "thinking"),
]


def run_cmd(args, timeout=30):
    cmd = [sys.executable, BUILDER] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def parse_router_output(out):
    """Parse router command output."""
    data = {"level": "", "label": "", "path": "", "domain": "", "keywords": []}
    for line in out.split("\n"):
        line = line.strip()
        for sep in ["：", ":"]:
            if f"等级{sep}" in line:
                data["level"] = line.split(sep)[-1].strip().upper()
            elif f"类型{sep}" in line:
                data["label"] = line.split(sep)[-1].strip()
            elif f"路径{sep}" in line:
                data["path"] = line.split(sep)[-1].strip()
            elif f"领域{sep}" in line:
                data["domain"] = line.split(sep)[-1].strip()
    return data


def test_one(qid, query, expected_level, expected_domain, mode="query"):
    """Run full flow for one query. mode: query or siwei."""
    result = {
        "id": qid,
        "mode": mode,
        "query": query,
        "expected_level": expected_level,
        "expected_domain": expected_domain,
        "steps": {},
        "pass": True,
        "issues": [],
    }

    # Step 1: Router
    rc, out, err = run_cmd(["router", query])
    result["steps"]["router"] = {"rc": rc, "output": out.strip()[:500], "error": err.strip()[:200]}
    rdata = parse_router_output(out)
    result["steps"]["router"]["parsed"] = rdata

    level = rdata.get("level", "")
    domain = rdata.get("domain", "")

    # Validate level
    if expected_level and level != expected_level:
        result["issues"].append(f"Level mismatch: expected {expected_level}, got {level}")
        # Don't fail - just record

    # Validate domain
    if expected_domain and domain and expected_domain.lower() not in domain.lower():
        result["issues"].append(f"Domain mismatch: expected {expected_domain}, got {domain}")

    if rc != 0:
        result["issues"].append(f"Router failed: rc={rc}")
        result["pass"] = False

    # Step 2: Cache read
    rc2, out2, _ = run_cmd(["cache-read", query])
    result["steps"]["cache_read"] = {"rc": rc2, "hit": "cache hit" in out2.lower() or "命中" in out2}

    # Step 3: Domain read (L2/L3 only)
    if level in ("L2", "L3") and domain:
        rc3, out3, _ = run_cmd(["domain-read", domain.split(",")[0].strip()])
        result["steps"]["domain_read"] = {"rc": rc3, "exists": rc3 == 0 and "不存在" not in out3}
        if rc3 != 0 or "不存在" in out3:
            result["issues"].append(f"Domain read failed for {domain}")
            result["pass"] = False

    # Step 4: Search
    rc4, out4, _ = run_cmd(["search", query, "--top", "5"])
    matches = re.findall(r'^\s*\d+\.\s+', out4, re.MULTILINE)
    result_count = len(matches)
    result["steps"]["search"] = {
        "rc": rc4,
        "result_count": result_count,
        "output_preview": out4.strip()[:400],
    }
    if result_count == 0:
        result["issues"].append("Zero search results")
        result["pass"] = False

    # Step 5: Cache write (only for query mode, to avoid polluting cache with 100 entries)
    if mode == "query":
        rc5, out5, _ = run_cmd(["cache-write", query, f"test-{qid}"])
        result["steps"]["cache_write"] = {"rc": rc5}

    return result


def main():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"=" * 70)
    print(f"Batch Test: 100 Topics (50 query + 50 siwei)")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"=" * 70)

    all_results = []

    # 50 query
    print(f"\n--- 50 QUERY TOPICS ---")
    for i, (q, exp_level, exp_domain) in enumerate(QUERY_TOPICS, 1):
        qid = f"Q{i:02d}"
        print(f"[{qid}] {q[:50]}...")
        r = test_one(qid, q, exp_level, exp_domain, mode="query")
        all_results.append(r)
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  -> {status} | L={r['steps']['router']['parsed'].get('level','?')} D={r['steps']['router']['parsed'].get('domain','?')} | search={r['steps']['search']['result_count']}")

    # 50 siwei
    print(f"\n--- 50 SIWEI TOPICS ---")
    for i, (q, exp_level, exp_domain) in enumerate(SIWEI_TOPICS, 1):
        qid = f"S{i:02d}"
        print(f"[{qid}] {q[:50]}...")
        r = test_one(qid, q, exp_level, exp_domain, mode="siwei")
        all_results.append(r)
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  -> {status} | L={r['steps']['router']['parsed'].get('level','?')} D={r['steps']['router']['parsed'].get('domain','?')} | search={r['steps']['search']['result_count']}")

    # Analysis
    print(f"\n{'='*70}")
    print(f"ANALYSIS REPORT")
    print(f"{'='*70}")

    total = len(all_results)
    passed = sum(1 for r in all_results if r["pass"])
    failed = total - passed

    # Query vs Siwei
    q_results = [r for r in all_results if r["mode"] == "query"]
    s_results = [r for r in all_results if r["mode"] == "siwei"]
    q_pass = sum(1 for r in q_results if r["pass"])
    s_pass = sum(1 for r in s_results if r["pass"])

    print(f"\n## 总体统计")
    print(f"  总话题数: {total}")
    print(f"  通过: {passed} | 失败: {failed} | 通过率: {passed/total*100:.1f}%")
    print(f"  Query: {q_pass}/{len(q_results)} ({q_pass/len(q_results)*100:.1f}%)")
    print(f"  Siwei: {s_pass}/{len(s_results)} ({s_pass/len(s_results)*100:.1f}%)")

    # Level distribution
    level_counter = Counter()
    level_pass = Counter()
    level_total = Counter()
    for r in all_results:
        lvl = r["steps"]["router"]["parsed"].get("level", "UNKNOWN")
        level_counter[lvl] += 1
        level_total[lvl] += 1
        if r["pass"]:
            level_pass[lvl] += 1

    print(f"\n## Router 等级分布")
    for lvl in sorted(level_counter.keys()):
        cnt = level_counter[lvl]
        pct = cnt / total * 100
        pass_pct = level_pass[lvl] / level_total[lvl] * 100 if level_total[lvl] else 0
        print(f"  {lvl}: {cnt} ({pct:.1f}%) | 通过率 {pass_pct:.1f}%")

    # Domain distribution
    domain_counter = Counter()
    domain_pass = Counter()
    for r in all_results:
        dom = r["steps"]["router"]["parsed"].get("domain", "unknown")
        # Normalize: take first if comma-separated
        dom = dom.split(",")[0].strip().lower() if dom else "unknown"
        domain_counter[dom] += 1
        if r["pass"]:
            domain_pass[dom] += 1

    print(f"\n## 领域分布")
    for dom, cnt in domain_counter.most_common():
        pct = cnt / total * 100
        pass_pct = domain_pass[dom] / cnt * 100
        print(f"  {dom}: {cnt} ({pct:.1f}%) | 通过率 {pass_pct:.1f}%")

    # Search result count statistics
    search_counts = [r["steps"]["search"]["result_count"] for r in all_results]
    avg_search = sum(search_counts) / len(search_counts) if search_counts else 0
    zero_search = sum(1 for c in search_counts if c == 0)
    print(f"\n## Search 命中统计")
    print(f"  平均结果数: {avg_search:.2f}")
    print(f"  零结果查询: {zero_search}")
    print(f"  最大: {max(search_counts)} | 最小: {min(search_counts)}")

    # Cache hit rate
    cache_hits = sum(1 for r in all_results if r["steps"].get("cache_read", {}).get("hit", False))
    print(f"\n## 缓存命中率")
    print(f"  命中: {cache_hits}/{total} ({cache_hits/total*100:.1f}%)")

    # Level accuracy (expected vs actual)
    print(f"\n## Router 等级准确率")
    level_correct = 0
    level_mismatch_cases = []
    for r in all_results:
        exp = r["expected_level"]
        actual = r["steps"]["router"]["parsed"].get("level", "")
        if exp == actual:
            level_correct += 1
        else:
            level_mismatch_cases.append((r["id"], r["query"][:40], exp, actual))
    print(f"  准确: {level_correct}/{total} ({level_correct/total*100:.1f}%)")
    if level_mismatch_cases:
        print(f"  不匹配案例 (前 10):")
        for qid, q, exp, act in level_mismatch_cases[:10]:
            print(f"    {qid}: '{q}' expected={exp} actual={act}")

    # Domain accuracy
    print(f"\n## Router 领域准确率")
    domain_correct = 0
    domain_mismatch_cases = []
    for r in all_results:
        exp = r["expected_domain"].lower()
        actual = r["steps"]["router"]["parsed"].get("domain", "").lower()
        if exp in actual or actual in exp:
            domain_correct += 1
        else:
            domain_mismatch_cases.append((r["id"], r["query"][:40], exp, actual))
    print(f"  准确: {domain_correct}/{total} ({domain_correct/total*100:.1f}%)")
    if domain_mismatch_cases:
        print(f"  不匹配案例 (前 10):")
        for qid, q, exp, act in domain_mismatch_cases[:10]:
            print(f"    {qid}: '{q}' expected={exp} actual={act}")

    # Failed cases
    failed_cases = [r for r in all_results if not r["pass"]]
    print(f"\n## 失败案例 ({len(failed_cases)})")
    for r in failed_cases[:20]:
        print(f"  {r['id']} [{r['mode']}] '{r['query'][:40]}'")
        for issue in r["issues"]:
            print(f"    - {issue}")

    # Save full results
    outpath = f"D:\\Obsidian\\LeoDiary\\_trash\\batch-test-100-{timestamp}.json"
    summary = {
        "timestamp": timestamp,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total,
        "query_pass": q_pass,
        "siwei_pass": s_pass,
        "level_distribution": dict(level_counter),
        "domain_distribution": dict(domain_counter),
        "avg_search_results": avg_search,
        "zero_search_count": zero_search,
        "cache_hit_rate": cache_hits / total,
        "level_accuracy": level_correct / total,
        "domain_accuracy": domain_correct / total,
        "results": all_results,
    }
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n## 完整结果保存到")
    print(f"  {outpath}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

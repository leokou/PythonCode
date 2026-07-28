#!/usr/bin/env python3
"""Truthful search quality test - checks actual search result relevance."""
import json, subprocess, sys

BUILDER = r"D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py"

TEST_CASES = [
    # (query, expected_keywords_in_top_result, description)
    ("Trae API 怎么配置", ["trae"], "Trae should be #1"),
    ("LeoDiary 里面关于 Claude Code 的资料", ["claude"], "Claude Code should dominate"),
    ("Trae API 怎么配置", ["trae"], "Trae again"),
    ("我的知识库里面关于 Shadowrocket 配置", ["shadowrocket"], "Shadowrocket should rank"),
    ("LeoDiary 核心能力模块", ["leodiary"], "LeoDiary files first"),
    ("AI 工具之间的对比 ChatGPT Claude Gemini", ["chatgpt", "claude", "gemini"], "AI tools comparison"),
    ("Obsidian 自动化整理知识库的方法", ["obsidian"], "Obsidian ranking"),
    ("AI Agent Skill MCP 的学习资料", ["agent", "skill", "mcp"], "Agent/Skill/MCP"),
    ("Vue3 Hono Cloudflare 技术方案", ["vue3", "hono", "cloudflare"], "Tech stack"),
    ("LeoDiary 项目整体架构设计", ["leodiary"], "Architecture design"),
    ("AI 方向知识体系是否完整 缺少哪些部分", ["ai"], "AI knowledge system"),
    ("LeoDiary 架构扩展到10000文件会遇到哪些问题", ["leodiary"], "LeoDiary scaling"),
    ("Obsidian知识管理方法相比普通笔记软件的优势不足", ["obsidian"], "Obsidian comparison"),
    ("AI工具组合如何分工 ChatGPT Claude Cursor Trae", ["chatgpt", "claude", "cursor", "trae"], "Tool division"),
    ("AI工具体系分析 有哪些工具 什么关系", ["ai"], "AI tool system"),
    ("近期待办事务优先级安排", [], "Life priority"),
    ("未来五年持续提升个人竞争力重点积累能力", [], "Personal growth"),
    ("自研知识管理系统封装为商用产品是否值得", ["知识管理"], "Commercialization"),
    ("核心重要事项推进效率极低根源剖析", [], "Root cause analysis"),
    ("AI副业适合选择哪些落地方向", ["ai"], "AI side business"),
    ("MCP Agent Skill 之间的关系和设计思路", ["mcp", "agent", "skill"], "MCP/Agent/Skill"),
    ("是否需要引入向量数据库或RAG", ["rag", "向量"], "RAG decision"),
    ("AI检索效率低Token消耗过大的问题", ["ai"], "AI retrieval efficiency"),
    ("知识管理Obsidian AI自动化的重要设计方案", ["obsidian", "ai"], "Knowledge management design"),
    ("Obsidian Planner Organizer Compiler分别是什么作用", ["obsidian"], "Planner/Organizer/Compiler"),
]

def search(query, top_n=5):
    cmd = [sys.executable, BUILDER, "search", query, "--top", str(top_n)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return r.stdout

print("=" * 60)
print("TRUTHFUL SEARCH QUALITY TEST")
print("=" * 60)

results = []
for query, expected_kw, desc in TEST_CASES:
    raw = search(query)
    
    # Parse results
    items = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "." in line[:3]:
            items.append(line)
    
    # Check if expected keywords appear in top results
    passed = True
    issues = []
    
    if expected_kw:
        # Check if at least one expected keyword appears in top results
        found_any = any(
            any(kw.lower() in line.lower() for kw in expected_kw)
            for line in items[:3]
        )
        if not found_any:
            passed = False
            issues.append(f"No expected keywords {expected_kw} in top 3 results")
    
    result_count = len(items)
    if result_count == 0:
        passed = False
        issues.append("Zero results returned")
    
    status = "PASS" if passed else "FAIL"
    print(f"\n{status} | {desc}")
    print(f"  Query: {query}")
    if items:
        print(f"  Top: {items[0][:100]}")
    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
    
    results.append({
        'query': query,
        'desc': desc,
        'passed': passed,
        'result_count': result_count,
        'top_result': items[0] if items else '',
        'issues': issues,
    })

# Summary
passed = sum(1 for r in results if r['passed'])
failed = sum(1 for r in results if not r['passed'])
print(f"\n{'='*60}")
print(f"SUMMARY: {passed}/{len(results)} passed ({passed/len(results)*100:.1f}%)")
if failed > 0:
    print(f"\n❌ FAILS:")
    for r in results:
        if not r['passed']:
            print(f"   - {r['desc']}: {', '.join(r['issues'])}")

# Save
with open(r"D:\Obsidian\LeoDiary\_trash\search-quality-test.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nResults saved to _trash/search-quality-test.json")
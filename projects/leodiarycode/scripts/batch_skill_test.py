#!/usr/bin/env python3
"""Batch test: 25 queries through LD-DVA Final + Skill flow.
Outputs structured results for health check verification.
"""
import json, subprocess, sys
from datetime import datetime

BUILDER = r"D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py"

QUERIES = {
    "L1_simple": [
        ("Trae 怎么配置 API", "L2"),
        ("LeoDiary 里面关于 Claude Code 的资料", "L2"),
        ("Trae API 怎么配置", "L2"),
        ("我的知识库里面关于 Shadowrocket 配置", "L2"),
        ("LeoDiary 核心能力模块", "L2"),
        ("AI 工具之间的对比 ChatGPT Claude Gemini", "L3"),
        ("Obsidian 自动化整理知识库的方法", "L2"),
        ("AI Agent Skill MCP 的学习资料", "L2"),
        ("Vue3 Hono Cloudflare 技术方案", "L2"),
        ("LeoDiary 项目整体架构设计", "L3"),
    ],
    "L3_complex": [
        ("AI 方向知识体系是否完整 缺少哪些部分", "L3"),
        ("LeoDiary 架构扩展到10000文件会遇到哪些问题", "L3"),
        ("Obsidian知识管理方法相比普通笔记软件的优势不足", "L3"),
        ("AI工具组合如何分工 ChatGPT Claude Cursor Trae", "L3"),
        ("AI工具体系分析 有哪些工具 什么关系", "L3"),
    ],
    "L2_life": [
        ("近期待办事务优先级安排", "L2"),
        ("未来五年持续提升个人竞争力重点积累能力", "L3"),
        ("自研知识管理系统封装为商用产品是否值得", "L3"),
        ("核心重要事项推进效率极低根源剖析", "L3"),
        ("AI副业适合选择哪些落地方向", "L2"),
        ("MCP Agent Skill 之间的关系和设计思路", "L3"),
        ("是否需要引入向量数据库或RAG", "L2"),
        ("AI检索效率低Token消耗过大的问题", "L2"),
        ("知识管理Obsidian AI自动化的重要设计方案", "L3"),
        ("Obsidian Planner Organizer Compiler分别是什么作用", "L2"),
    ],
}

def run_cmd(args):
    """Run a command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, BUILDER] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

def test_query(query_id, query, expected_level=None):
    """Run full Skill flow for one query."""
    result = {
        "id": query_id,
        "query": query,
        "expected_level": expected_level,
        "steps": {},
        "pass": True,
        "issues": [],
    }

    # Step 1: Router
    rc, out, err = run_cmd(["router", query])
    result["steps"]["router"] = {"rc": rc, "output": out.strip(), "error": err.strip() if err else ""}
    rdata = {}
    for line in out.split("\n"):
        line = line.strip()
        # Handle both Chinese and English colons
        for sep in ["：", ":"]:
            if f"等级{sep}" in line or "等级" in line and sep in line:
                rdata["level"] = line.split(sep)[-1].strip().upper()
            if f"类型{sep}" in line or "类型" in line and sep in line:
                rdata["label"] = line.split(sep)[-1].strip()
            if f"路径{sep}" in line or "路径" in line and sep in line:
                rdata["path"] = line.split(sep)[-1].strip()
            if f"领域{sep}" in line or "领域" in line and sep in line:
                rdata["domain"] = line.split(sep)[-1].strip()
    result["steps"]["router"]["parsed"] = rdata

    # Validate level if expected
    if expected_level and rdata.get("level", "").upper() != expected_level.upper():
        result["issues"].append(f"Expected {expected_level}, got {rdata.get('level')}")
        result["pass"] = False

    level = rdata.get("level", "L1").upper()
    domain = rdata.get("domain", "")

    # Step 2: Cache read
    rc2, out2, err2 = run_cmd(["cache-read", query])
    result["steps"]["cache_read"] = {"rc": rc2, "output": out2.strip()}

    # Step 3: Domain read (L2/L3 only)
    if level in ("L2", "L3") and domain:
        rc3, out3, err3 = run_cmd(["domain-read", domain])
        result["steps"]["domain_read"] = {"rc": rc3, "output": out3.strip()[:500]}
        if "不存在" in out3:
            result["issues"].append(f"Domain {domain} not found")
            result["pass"] = False
    elif level == "L1":
        result["steps"]["domain_read"] = {"skipped": "L1 - direct search"}

    # Step 4: Search
    rc4, out4, err4 = run_cmd(["search", query, "--top", "5"])
    result["steps"]["search"] = {"rc": rc4, "output": out4.strip()[:800]}
    # Count results by looking for numbered items
    import re
    matches = re.findall(r'^\s+\d+\.\s+', out4, re.MULTILINE)
    result_count = len(matches)
    result["steps"]["search"]["result_count"] = result_count
    if result_count == 0:
        result["issues"].append("Zero search results")
        result["pass"] = False

    # Step 5: Cache write
    rc5, out5, err5 = run_cmd(["cache-write", query, "test"])
    result["steps"]["cache_write"] = {"rc": rc5, "output": out5.strip()}

    return result

def main():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []

    for level, queries in QUERIES.items():
        for i, item in enumerate(queries, 1):
            if isinstance(item, tuple):
                q, expected = item
            else:
                q, expected = item, None
            qid = f"{level}_{i:02d}"
            print(f"Testing {qid}: {q}...")
            r = test_query(qid, q, expected)
            results.append(r)
            status = "PASS" if r["pass"] else "FAIL"
            print(f"  {status} | issues: {len(r['issues'])}")
            if r["issues"]:
                for issue in r["issues"]:
                    print(f"    - {issue}")

    # Summary
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"])

    print(f"\n{'='*50}")
    print(f"BATCH TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Total: {len(results)} | Pass: {passed} | Fail: {failed}")
    print(f"Pass Rate: {passed/len(results)*100:.1f}%")

    # Group by level
    for level_key in QUERIES:
        group = [r for r in results if r["id"].startswith(level_key)]
        gp = sum(1 for r in group if r["pass"])
        print(f"  {level_key}: {gp}/{len(group)} passed")

    # Save results
    outpath = f"D:\\Obsidian\\LeoDiary\\_trash\\batch-test-{timestamp}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to: {outpath}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
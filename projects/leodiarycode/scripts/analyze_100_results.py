#!/usr/bin/env python3
"""Analyze batch-test-100 results: extract domain from path field and generate detailed report."""
import json, sys, re
from collections import Counter, defaultdict
from datetime import datetime

# Find latest result file
import os
import glob

files = glob.glob(r"D:\Obsidian\LeoDiary\_trash\batch-test-100-*.json")
if not files:
    print("No result file found")
    sys.exit(1)

latest = max(files, key=os.path.getmtime)
print(f"Analyzing: {latest}\n")

with open(latest, "r", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]


def extract_domain(path_str):
    """Extract domain from path string like 'domain索引(🤖 AI) → runtime搜索...'"""
    if not path_str:
        return "unknown"
    # Match patterns like: domain索引(🤖 AI) or domain索引(🧠 思维) or domain索引(xxx)
    m = re.search(r'domain索引\(([^)]+)\)', path_str)
    if m:
        return m.group(1).strip()
    # Also check for direct domain mentions
    if "AI" in path_str or "🤖" in path_str:
        return "AI"
    if "思维" in path_str or "🧠" in path_str:
        return "思维"
    if "开发" in path_str or "💻" in path_str:
        return "开发"
    if "系统" in path_str or "🪟" in path_str:
        return "系统"
    if "软件" in path_str or "🕹️" in path_str:
        return "软件"
    if "项目" in path_str or "🧁" in path_str:
        return "项目"
    if "影视" in path_str or "🎬" in path_str:
        return "影视"
    if "核心规则" in path_str or "📜" in path_str:
        return "核心规则"
    if "leo" in path_str.lower() or "🙎" in path_str:
        return "个人"
    return "unknown"


def normalize_domain(dom):
    """Normalize domain to canonical name."""
    if not dom or dom == "unknown":
        return "unknown"
    d = dom.lower()
    if "ai" in d or "🤖" in dom:
        return "AI"
    if "思维" in dom or "🧠" in dom:
        return "思维框架"
    if "开发" in dom or "💻" in dom:
        return "开发"
    if "系统" in dom or "🪟" in dom:
        return "系统"
    if "软件" in dom or "🕹️" in dom:
        return "软件"
    if "项目" in dom or "🧁" in dom:
        return "项目"
    if "影视" in dom or "🎬" in dom:
        return "影视"
    if "核心规则" in dom or "📜" in dom or "root" in d:
        return "核心规则"
    if "leo" in d or "🙎" in dom or "life" in d:
        return "个人"
    return dom


# Re-parse all results
for r in results:
    path = r["steps"]["router"]["parsed"].get("path", "")
    dom_raw = extract_domain(path)
    r["actual_domain"] = normalize_domain(dom_raw)
    r["actual_level"] = r["steps"]["router"]["parsed"].get("level", "")

# Map expected domains to canonical names
expected_map = {
    "ai": "AI",
    "dev": "开发",
    "system": "系统",
    "software": "软件",
    "project": "项目",
    "movie": "影视",
    "thinking": "思维框架",
    "root": "核心规则",
    "life": "个人",
}

for r in results:
    r["expected_domain_norm"] = expected_map.get(r["expected_domain"].lower(), r["expected_domain"])

# === ANALYSIS ===
print("=" * 70)
print("DETAILED ANALYSIS REPORT - 100 TOPICS TEST")
print("=" * 70)

total = len(results)
passed = sum(1 for r in results if r["pass"])
print(f"\n## 1. 总体统计")
print(f"  总话题数: {total}")
print(f"  通过: {passed} | 失败: {total - passed} | 通过率: {passed/total*100:.1f}%")

# Query vs Siwei
q_results = [r for r in results if r["mode"] == "query"]
s_results = [r for r in results if r["mode"] == "siwei"]
q_pass = sum(1 for r in q_results if r["pass"])
s_pass = sum(1 for r in s_results if r["pass"])
print(f"\n## 2. 模式对比")
print(f"  Query (普通查询): {q_pass}/{len(q_results)} ({q_pass/len(q_results)*100:.1f}%)")
print(f"  Siwei (深度思考): {s_pass}/{len(s_results)} ({s_pass/len(s_results)*100:.1f}%)")

# Level distribution
print(f"\n## 3. Router 等级分布")
level_counter = Counter()
level_pass = Counter()
level_by_mode = defaultdict(Counter)
for r in results:
    lvl = r["actual_level"] or "UNKNOWN"
    level_counter[lvl] += 1
    level_by_mode[r["mode"]][lvl] += 1
    if r["pass"]:
        level_pass[lvl] += 1

for lvl in sorted(level_counter.keys()):
    cnt = level_counter[lvl]
    pct = cnt / total * 100
    pass_pct = level_pass[lvl] / cnt * 100
    q_cnt = level_by_mode["query"][lvl]
    s_cnt = level_by_mode["siwei"][lvl]
    print(f"  {lvl}: {cnt} ({pct:.1f}%) | 通过率 {pass_pct:.1f}% | Query:{q_cnt} Siwei:{s_cnt}")

# Domain distribution
print(f"\n## 4. Router 领域分布（从 path 字段提取）")
domain_counter = Counter()
domain_pass = Counter()
domain_by_mode = defaultdict(Counter)
for r in results:
    dom = r["actual_domain"]
    domain_counter[dom] += 1
    domain_by_mode[r["mode"]][dom] += 1
    if r["pass"]:
        domain_pass[dom] += 1

for dom, cnt in domain_counter.most_common():
    pct = cnt / total * 100
    pass_pct = domain_pass[dom] / cnt * 100
    q_cnt = domain_by_mode["query"][dom]
    s_cnt = domain_by_mode["siwei"][dom]
    print(f"  {dom}: {cnt} ({pct:.1f}%) | 通过率 {pass_pct:.1f}% | Query:{q_cnt} Siwei:{s_cnt}")

# Level accuracy
print(f"\n## 5. Router 等级准确率（预期 vs 实际）")
level_correct = 0
level_mismatch = []
for r in results:
    exp = r["expected_level"]
    act = r["actual_level"]
    if exp == act:
        level_correct += 1
    else:
        level_mismatch.append((r["id"], r["mode"], r["query"][:50], exp, act))
print(f"  准确: {level_correct}/{total} ({level_correct/total*100:.1f}%)")
# Accuracy by mode
q_correct = sum(1 for r in q_results if r["expected_level"] == r["actual_level"])
s_correct = sum(1 for r in s_results if r["expected_level"] == r["actual_level"])
print(f"  Query 准确率: {q_correct}/{len(q_results)} ({q_correct/len(q_results)*100:.1f}%)")
print(f"  Siwei 准确率: {s_correct}/{len(s_results)} ({s_correct/len(s_results)*100:.1f}%)")

# Mismatch pattern analysis
print(f"\n## 6. 等级不匹配模式分析（{len(level_mismatch)} 个）")
mismatch_pattern = Counter()
for qid, mode, q, exp, act in level_mismatch:
    mismatch_pattern[(exp, act)] += 1
for (exp, act), cnt in mismatch_pattern.most_common():
    print(f"  {exp} → {act}: {cnt} 次")

print(f"\n  不匹配案例详情:")
for qid, mode, q, exp, act in level_mismatch[:15]:
    print(f"    {qid} [{mode}] '{q}' expected={exp} actual={act}")

# Domain accuracy
print(f"\n## 7. Router 领域准确率（预期 vs 实际）")
domain_correct = 0
domain_mismatch = []
for r in results:
    exp = r["expected_domain_norm"]
    act = r["actual_domain"]
    if exp == act:
        domain_correct += 1
    else:
        domain_mismatch.append((r["id"], r["mode"], r["query"][:50], exp, act))
print(f"  准确: {domain_correct}/{total} ({domain_correct/total*100:.1f}%)")
q_d_correct = sum(1 for r in q_results if r["expected_domain_norm"] == r["actual_domain"])
s_d_correct = sum(1 for r in s_results if r["expected_domain_norm"] == r["actual_domain"])
print(f"  Query 准确率: {q_d_correct}/{len(q_results)} ({q_d_correct/len(q_results)*100:.1f}%)")
print(f"  Siwei 准确率: {s_d_correct}/{len(s_results)} ({s_d_correct/len(s_results)*100:.1f}%)")

if domain_mismatch:
    print(f"\n  不匹配案例 (前 15):")
    for qid, mode, q, exp, act in domain_mismatch[:15]:
        print(f"    {qid} [{mode}] '{q}' expected={exp} actual={act}")

# Search statistics
print(f"\n## 8. Search 命中统计")
search_counts = [r["steps"]["search"]["result_count"] for r in results]
avg_search = sum(search_counts) / len(search_counts)
zero_search = sum(1 for c in search_counts if c == 0)
print(f"  平均结果数: {avg_search:.2f}")
print(f"  零结果查询: {zero_search}")
print(f"  最大: {max(search_counts)} | 最小: {min(search_counts)}")

# Search by level
print(f"\n  按等级分组:")
for lvl in sorted(level_counter.keys()):
    cnts = [r["steps"]["search"]["result_count"] for r in results if r["actual_level"] == lvl]
    if cnts:
        print(f"    {lvl}: avg={sum(cnts)/len(cnts):.2f} min={min(cnts)} max={max(cnts)}")

# Search by mode
print(f"\n  按模式分组:")
q_search = [r["steps"]["search"]["result_count"] for r in q_results]
s_search = [r["steps"]["search"]["result_count"] for r in s_results]
print(f"    Query: avg={sum(q_search)/len(q_search):.2f}")
print(f"    Siwei: avg={sum(s_search)/len(s_search):.2f}")

# Search result distribution
print(f"\n  结果数分布:")
search_dist = Counter(search_counts)
for cnt in sorted(search_dist.keys()):
    print(f"    {cnt} 结果: {search_dist[cnt]} 个查询")

# Cache hit rate
print(f"\n## 9. 缓存命中率")
cache_hits = sum(1 for r in results if r["steps"].get("cache_read", {}).get("hit", False))
print(f"  命中: {cache_hits}/{total} ({cache_hits/total*100:.1f}%)")

# Low search result queries (1-2 results)
print(f"\n## 10. 低结果查询（≤2 结果）")
low_results = [r for r in results if r["steps"]["search"]["result_count"] <= 2]
print(f"  共 {len(low_results)} 个查询结果数 ≤ 2")
for r in low_results[:20]:
    cnt = r["steps"]["search"]["result_count"]
    print(f"    {r['id']} [{r['mode']}] L={r['actual_level']} D={r['actual_domain']} cnt={cnt} | '{r['query'][:50]}'")

# Domain coverage check
print(f"\n## 11. 领域覆盖完整性")
all_expected_domains = set(r["expected_domain_norm"] for r in results)
all_actual_domains = set(r["actual_domain"] for r in results)
print(f"  预期领域: {sorted(all_expected_domains)}")
print(f"  实际领域: {sorted(all_actual_domains)}")
missing = all_expected_domains - all_actual_domains
if missing:
    print(f"  ❌ 缺失领域: {missing}")
else:
    print(f"  ✅ 所有预期领域均被覆盖")

# === OUTPUT FINAL SUMMARY ===
print(f"\n{'='*70}")
print(f"FINAL SUMMARY")
print(f"{'='*70}")
print(f"  ✅ 总通过率: {passed}/{total} ({passed/total*100:.1f}%)")
print(f"  ✅ Query 通过率: {q_pass}/{len(q_results)} ({q_pass/len(q_results)*100:.1f}%)")
print(f"  ✅ Siwei 通过率: {s_pass}/{len(s_results)} ({s_pass/len(s_results)*100:.1f}%)")
print(f"  ⚠️ Router 等级准确率: {level_correct}/{total} ({level_correct/total*100:.1f}%)")
print(f"  {'✅' if domain_correct/total > 0.8 else '⚠️'} Router 领域准确率: {domain_correct}/{total} ({domain_correct/total*100:.1f}%)")
print(f"  ✅ Search 平均结果数: {avg_search:.2f}")
print(f"  ✅ 零结果查询: {zero_search}")
print(f"  ℹ️ 缓存命中率: {cache_hits}/{total} ({cache_hits/total*100:.1f}%)")

# Save analysis report
analysis_path = r"D:\Obsidian\LeoDiary\_trash\analysis-100-report.md"
with open(analysis_path, "w", encoding="utf-8") as f:
    f.write(f"# 100 话题批量测试分析报告\n\n")
    f.write(f"**生成时间**: {datetime.now().isoformat()}\n")
    f.write(f"**数据源**: {latest}\n\n")
    f.write(f"## 总体结果\n\n")
    f.write(f"- 总话题数: {total}\n")
    f.write(f"- 通过: {passed} ({passed/total*100:.1f}%)\n")
    f.write(f"- Query: {q_pass}/{len(q_results)}\n")
    f.write(f"- Siwei: {s_pass}/{len(s_results)}\n\n")
    f.write(f"## Router 等级分布\n\n")
    f.write(f"| 等级 | 数量 | 占比 | 通过率 | Query | Siwei |\n")
    f.write(f"|------|------|------|--------|-------|-------|\n")
    for lvl in sorted(level_counter.keys()):
        cnt = level_counter[lvl]
        f.write(f"| {lvl} | {cnt} | {cnt/total*100:.1f}% | {level_pass[lvl]/cnt*100:.1f}% | {level_by_mode['query'][lvl]} | {level_by_mode['siwei'][lvl]} |\n")
    f.write(f"\n## Router 领域分布\n\n")
    f.write(f"| 领域 | 数量 | 占比 | 通过率 | Query | Siwei |\n")
    f.write(f"|------|------|------|--------|-------|-------|\n")
    for dom, cnt in domain_counter.most_common():
        f.write(f"| {dom} | {cnt} | {cnt/total*100:.1f}% | {domain_pass[dom]/cnt*100:.1f}% | {domain_by_mode['query'][dom]} | {domain_by_mode['siwei'][dom]} |\n")
    f.write(f"\n## 准确率\n\n")
    f.write(f"- 等级准确率: {level_correct}/{total} ({level_correct/total*100:.1f}%)\n")
    f.write(f"- 领域准确率: {domain_correct}/{total} ({domain_correct/total*100:.1f}%)\n")
    f.write(f"- Query 等级准确率: {q_correct}/{len(q_results)} ({q_correct/len(q_results)*100:.1f}%)\n")
    f.write(f"- Siwei 等级准确率: {s_correct}/{len(s_results)} ({s_correct/len(s_results)*100:.1f}%)\n\n")
    f.write(f"## Search 统计\n\n")
    f.write(f"- 平均结果数: {avg_search:.2f}\n")
    f.write(f"- 零结果查询: {zero_search}\n")
    f.write(f"- 缓存命中率: {cache_hits/total*100:.1f}%\n\n")
    f.write(f"## 等级不匹配模式\n\n")
    f.write(f"| 预期 | 实际 | 次数 |\n|------|------|------|\n")
    for (exp, act), cnt in mismatch_pattern.most_common():
        f.write(f"| {exp} | {act} | {cnt} |\n")

print(f"\n分析报告已保存: {analysis_path}")

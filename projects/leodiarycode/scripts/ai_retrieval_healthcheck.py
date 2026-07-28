#!/usr/bin/env python3
"""Full AI Retrieval Chain Health Check.
Checks all plugins, pages, configs for completeness and broken links.
"""
import os, sys, json, subprocess
from datetime import datetime

BUILDER = r"D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py"
LEODIARY = r"D:\Obsidian\LeoDiary"
SKILLS_DIR = r"C:\Users\leokou\.claude\skills\Obsidian"

checks = []
passed = 0
failed = 0

def check(name, status, detail=""):
    global passed, failed
    icon = "✅" if status else "❌"
    checks.append({"name": name, "status": "PASS" if status else "FAIL", "detail": detail})
    if status:
        passed += 1
    else:
        failed += 1
    print(f"  {icon} {name}: {detail}")

def file_exists(path):
    return os.path.exists(path)

print("=" * 60)
print("AI RETRIEVAL CHAIN - FULL HEALTH CHECK")
print("=" * 60)

# ===== 1. Python Builder =====
print("\n📦 1. Python Builder Scripts")
check("ai_index_builder_v2.py exists", file_exists(BUILDER))
check("obsidian_skill_utils.py exists", 
      file_exists(r"D:\Python\projects\leodiarycode\src\obsidian_skill_utils.py"))
check("batch_skill_test.py exists", 
      file_exists(r"D:\Python\projects\leodiarycode\scripts\batch_skill_test.py"))
check("ai_retrieval_healthcheck.py exists", 
      file_exists(r"D:\Python\projects\leodiarycode\scripts\ai_retrieval_healthcheck.py"))

# Test basic commands
print("\n🔧 1b. Builder command tests")
for cmd_name, cmd_args in [
    ("router", ["router", "test"]),
    ("cache-read", ["cache-read", "test"]),
    ("search", ["search", "test", "--top", "1"]),
]:
    try:
        r = subprocess.run([sys.executable, BUILDER] + cmd_args, 
                          capture_output=True, text=True, timeout=15)
        check(f"builder {cmd_name} works", r.returncode == 0, 
              f"rc={r.returncode}")
    except Exception as e:
        check(f"builder {cmd_name} works", False, str(e))

# ===== 2. AI_INDEX Files =====
print("\n📂 2. AI_INDEX Structure")
ai_index = os.path.join(LEODIARY, ".ai-index")
check(".ai-index directory exists", file_exists(ai_index))

required_files = [
    "protocol/AI_READ_PROTOCOL.md",
    "runtime/files.json",
    "runtime/tags.json",
    "runtime/relations.json",
    "cache/query-memory.json",
    "cache/query-stats.json",
]
for f in required_files:
    check(f".ai-index/{f}", file_exists(os.path.join(ai_index, f)))

# Domain indexes
domain_md = os.path.join(ai_index, "domain")
if file_exists(domain_md):
    domains = [f for f in os.listdir(domain_md) if f.endswith('.md')]
    check(f"Domain indexes: {len(domains)} files", len(domains) >= 5, 
          f"domains: {', '.join(sorted(domains))}")
else:
    check("Domain indexes exist", False, "directory missing")

# ===== 3. Skills =====
print("\n🧩 3. Skill Plugins")
required_skills = [
    "obsidian-knowledge-queryer",
    "obsidian-knowledge-compiler",
    "obsidian-knowledge-organizer",
    "obsidian-knowledge-planner",
    "obsidian-knowledge-Accumulate",
    "obsidian-pipeline",
    "obsidian-mulu-fenlei-summary",
    "obsidian-health-check-all",
    "obsidian-fire-rename",
]
for skill in required_skills:
    skill_dir = os.path.join(SKILLS_DIR, skill)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    check(f"{skill}/SKILL.md", file_exists(skill_md))

# Check queryer SKILL.md references builder_v2
queryer_skill = os.path.join(SKILLS_DIR, "obsidian-knowledge-queryer", "SKILL.md")
if file_exists(queryer_skill):
    with open(queryer_skill, "r", encoding="utf-8") as f:
        content = f.read()
    check("queryer SKILL.md references ai_index_builder_v2.py",
          "ai_index_builder_v2.py" in content)
    check("queryer SKILL.md has Router-driven protocol",
          "Router 驱动" in content or "router" in content.lower())
    check("queryer SKILL.md has cache-read step",
          "cache-read" in content)
    check("queryer SKILL.md has domain-read step",
          "domain-read" in content)
    check("queryer SKILL.md has cache-write step",
          "cache-write" in content)

# ===== 4. Skill Rule Files =====
print("\n⚙️ 4. Skill Rule Files")
queryer_rules = os.path.join(SKILLS_DIR, "obsidian-knowledge-queryer", "rules")
config_files = [
    "execution-level.md",
    "answer-strategy.md",
    "reasoning-pattern.md",
    "quality-check.md",
    "intent-analysis.md",
]
for cf in config_files:
    check(f"queryer/rules/{cf}", file_exists(os.path.join(queryer_rules, cf)))

# ===== 5. Knowledge Base Structure =====
print("\n📚 5. Knowledge Base Structure")
kb_dirs = [
    "1- 🤖AI 相关",
    "2- 💻开发",
    "3- 🪟系统",
    "4- 🕹️软件",
    "5- 🧁项目",
    "7- 🧠思维框架",
    "skills",
    "_trash",
]
for kd in kb_dirs:
    check(f"KB dir: {kd}", os.path.isdir(os.path.join(LEODIARY, kd)))

# ===== 6. Cross-reference integrity =====
print("\n🔗 6. Cross-Reference Integrity")

# Check that SKILL.md references match actual builder commands
skill_cmds = ["router", "cache-read", "cache-write", "domain-read", "search"]
for cmd in skill_cmds:
    with open(queryer_skill, "r", encoding="utf-8") as f:
        content = f.read()
    check(f"Skill references '{cmd}' command",
          f"ai_index_builder_v2.py {cmd}" in content or f'"{cmd}"' in content.lower())

# Check builder supports all commands
builder_cmds = ["router", "cache-read", "cache-write", "domain-read", "search", "classify"]
with open(BUILDER, "r", encoding="utf-8") as f:
    builder_content = f.read()
for bc in builder_cmds:
    check(f"Builder supports '{bc}' command",
          f"cmd_{bc.replace('-', '_')}" in builder_content or bc in builder_content)

# ===== 7. Pipeline Integration =====
print("\n🔄 7. Pipeline Integration")
pipeline_skill = os.path.join(SKILLS_DIR, "obsidian-pipeline", "SKILL.md")
if file_exists(pipeline_skill):
    with open(pipeline_skill, "r", encoding="utf-8") as f:
        content = f.read()
    check("Pipeline references queryer", "queryer" in content.lower() or "知识查询" in content)

accumulate_skill = os.path.join(SKILLS_DIR, "obsidian-knowledge-Accumulate", "SKILL.md")
if file_exists(accumulate_skill):
    check("Accumulate Skill exists", True, "deposits knowledge to Capture")

# ===== 8. Read-only Health Checks =====
print("\n💚 8. Runtime Health")

# Check AI_INDEX freshness
for idx_file in ["runtime/files.json", "runtime/tags.json"]:
    fp = os.path.join(ai_index, idx_file)
    if file_exists(fp):
        mtime = os.path.getmtime(fp)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        fresh = age_hours < 24
        check(f"{idx_file} freshness (<24h)", fresh, 
              f"age={age_hours:.1f}h old")
    else:
        check(f"{idx_file} exists", False, "file missing")

# Check query-memory has content
qm = os.path.join(ai_index, "cache", "query-memory.json")
if file_exists(qm):
    with open(qm, "r", encoding="utf-8") as f:
        qm_data = json.load(f)
    count = len(qm_data) if isinstance(qm_data, list) else len(qm_data.keys())
    check(f"query-memory.json has entries", count > 0, f"{count} entries")

# ===== SUMMARY =====
print("\n" + "=" * 60)
print(f"SUMMARY: {passed}/{passed + failed} passed ({passed/(passed+failed)*100:.1f}%)")
if failed > 0:
    print(f"\n❌ FAILED CHECKS:")
    for c in checks:
        if c["status"] == "FAIL":
            print(f"   - {c['name']}: {c['detail']}")
print("=" * 60)

# Save results
outpath = os.path.join(LEODIARY, "_trash", f"healthcheck-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
with open(outpath, "w", encoding="utf-8") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "total": passed+failed, "passed": passed, "failed": failed, "checks": checks}, f, ensure_ascii=False, indent=2)
print(f"\nResults saved to: {outpath}")

ok = failed == 0

if __name__ == "__main__":
    sys.exit(0 if ok else 1)
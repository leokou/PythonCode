import os
import shutil
import sys
import stat
from datetime import datetime

# Fix Windows console encoding for emoji output
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SOURCE = r"C:\Users\leokou\.claude\skills"
TARGETS = [
    r"C:\Users\leokou\.codex\skills",
    r"C:\Users\leokou\.trae\skills",
    r"C:\Users\leokou\.codebuddy",
    r"C:\Users\leokou\.qoderworkcn\skills",
     r"D:\project",    
]

EXCLUDE_FILES = {'desktop.ini', 'README.md', 'LICENSE', 'LEGAL.md',
                 'meta.json', 'opencode.jsonc', '.DS_Store', 'config.json'}
SYSTEM_DIRS = {'.system', '.obsidian'}
OBSIDIAN_WRAPPER = 'Obsidian'

TASK_NAME = "Skill同步其他Agent"

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "skill-sync.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def is_skill(path):
    """目录是否为有效 skill（含 SKILL.md）"""
    return os.path.isdir(path) and os.path.exists(os.path.join(path, "SKILL.md"))

def _find_nested_skill(root, max_depth=3):
    """递归搜索嵌套的 SKILL.md
    
    返回 (skill_dir, skill_name) 元组：
    - skill_dir: 应复制的目录路径
    - skill_name: 目标目录名
    
    对于 Agent-Reach 这类 SKILL.md 在 skill/ 子目录的情况，
    会向上提升一级，确保 agent_reach/ 等依赖包也被包含。
    """
    if max_depth <= 0:
        return None
    try:
        for entry in os.listdir(root):
            p = os.path.join(root, entry)
            if is_skill(p):
                # 找到 SKILL.md → 检查是否需要向上提升
                # 如果同级有其他重要目录（Python包、config等），用父目录
                siblings = os.listdir(root)
                important = {'agent_reach', 'config', 'src', 'lib', 'core',
                             'references', 'scripts', 'data', 'assets'}
                has_important = any(s in important and s != entry for s in siblings)
                if has_important:
                    return (root, os.path.basename(root))
                return (p, os.path.basename(p))
            if os.path.isdir(p):
                found = _find_nested_skill(p, max_depth - 1)
                if found:
                    return found
    except (PermissionError, OSError):
        pass
    return None

def on_rmtree_error(func, path, exc_info):
    """处理只读文件删除"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def collect_skills():
    """从源目录收集所有 skill，扁平化 Obsidian/ 嵌套
    
    返回: [(skill_name, skill_source_path), ...]
    """
    skills = []
    if not os.path.isdir(SOURCE):
        log(f"❌ 源目录不存在: {SOURCE}")
        return skills

    for name in sorted(os.listdir(SOURCE)):
        item = os.path.join(SOURCE, name)

        # 跳过系统目录和垃圾
        if name in SYSTEM_DIRS:
            log(f"  🚫 跳过系统目录: {name}")
            continue
        if name in EXCLUDE_FILES:
            continue
        if os.path.isfile(item):
            continue

        if name == OBSIDIAN_WRAPPER:
            # 扁平化 Obsidian/ 子目录下的 skill
            log(f"  📂 展开 {OBSIDIAN_WRAPPER}/ 下的 skills:")
            for sub in sorted(os.listdir(item)):
                sub_path = os.path.join(item, sub)
                if is_skill(sub_path):
                    skills.append((sub, sub_path))
                    log(f"    ✅ {sub}")
                elif os.path.isdir(sub_path):
                    log(f"    ⚠️  跳过（无 SKILL.md）: {sub}")
            continue

        if is_skill(item):
            skills.append((name, item))
            log(f"  ✅ {name}")
        elif os.path.isdir(item):
            # 深度搜索嵌套 skill（最多 3 层）
            # 例如 Agent-Reach-1.5.0/Agent-Reach-1.5.0/skill/SKILL.md
            found = _find_nested_skill(item, max_depth=3)
            if found:
                skill_dir, skill_name = found
                skills.append((name, skill_dir))
                if skill_name != name:
                    log(f"  ✅ {name} (嵌套 skill → {skill_name})")
                else:
                    log(f"  ✅ {name} (嵌套 skill)")
            else:
                log(f"  ⚠️  跳过（无 SKILL.md）: {name}")

    return skills

def sync_to_target(target, skills):
    """增量同步到单个目标目录"""
    log(f"  → {target}")

    parent = os.path.dirname(target)
    if not os.path.exists(parent):
        log(f"    ⚠️  父目录不存在，跳过")
        return

    if not os.path.exists(target):
        os.makedirs(target)

    existing = set(os.listdir(target))
    source_names = {name for name, _ in skills}

    # 1. 只删除目标中"曾是 skill（含 SKILL.md）但源已不存在"的目录
    #    保护非 skill 目录（如备份目录 python备份/skill备份）
    to_remove = set()
    for name in existing:
        if name in source_names or name in SYSTEM_DIRS or name in EXCLUDE_FILES or name == '.git':
            continue
        p = os.path.join(target, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "SKILL.md")):
            to_remove.add(name)
    removed = 0
    for name in to_remove:
        p = os.path.join(target, name)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, onerror=on_rmtree_error)
            else:
                os.unlink(p)
            removed += 1
            log(f"    🗑️  移除: {name}")
        except Exception as e:
            log(f"    ❌ 移除失败 [{name}]: {e}")

    # 2. 复制/更新 skills
    copied = updated = failed = 0
    for skill_name, skill_src in skills:
        dst = os.path.join(target, skill_name)
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst, onerror=on_rmtree_error)
                updated += 1
            else:
                copied += 1
            shutil.copytree(skill_src, dst)
            log(f"    ✅ {skill_name}")
        except PermissionError as e:
            failed += 1
            log(f"    ❌ 权限失败 [{skill_name}]: {e}")
        except Exception as e:
            failed += 1
            log(f"    ❌ 失败 [{skill_name}]: {e}")

    # 3. 验证结果
    final_items = sorted(os.listdir(target))
    log(f"    结果: +{copied} ≈{updated} 🗑️{removed} ❌{failed}")
    log(f"    现有 ({len(final_items)} 项): {final_items}")
    return copied, updated, removed, failed

def main():
    log(f"🔁 {TASK_NAME} 启动")
    log("=" * 60)
    log("LEO Skill Sync v2 启动")
    log(f"源: {SOURCE}")

    skills = collect_skills()
    log(f"共识别 {len(skills)} 个可同步 skill")

    if not skills:
        log("⚠️  无 skill 可同步，终止")
        log(f"❌ {TASK_NAME} 失败")
        return

    tc = tu = tr = tf = 0
    for target in TARGETS:
        c, u, r, f = sync_to_target(target, skills)
        tc += c; tu += u; tr += r; tf += f

    log(f"汇总: 新增{tc} 更新{tu} 移除{tr} 失败{tf}")
    log("LEO Skill Sync v2 完成")
    log(f"✅ {TASK_NAME} 成功")
    log("=" * 60 + "\n")

if __name__ == "__main__":
    main()
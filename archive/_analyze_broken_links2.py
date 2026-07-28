import re
from pathlib import Path
from collections import Counter

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

# 构建模糊匹配索引：文件名的关键词部分（去掉 @ 后面的标签和 - 分隔符）
def extract_keywords(filename):
    """从文件名中提取关键词，用于模糊匹配"""
    name = filename
    # 去掉 @ 标签
    if ' @ ' in name:
        name = name.split(' @ ')[0]
    # 去掉开头的 emoji 和编号
    name = re.sub(r'^[\U0001F300-\U0001FAFF\s\d\-]+', '', name)
    return name.strip()

fuzzy_index = {}
for stem, fpath in filename_index.items():
    kw = extract_keywords(stem)
    if kw:
        if kw not in fuzzy_index:
            fuzzy_index[kw] = []
        fuzzy_index[kw].append(stem)

broken_links = []
wiki_re = re.compile(r'\[\[([^\]|#]+)')

for f in md_files:
    try:
        content = f.read_text(encoding='utf-8')
    except:
        continue
    cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    cleaned = re.sub(r'`[^`]*`', '', cleaned)
    for match in wiki_re.finditer(cleaned):
        link = match.group(1).strip()
        if not link:
            continue
        link_name = link.split('/')[-1].split('\\')[-1].strip()
        if not link_name:
            continue
        if link_name not in filename_index:
            broken_links.append((str(f.relative_to(vault)), link, link_name))

# 分析可修复的断链
fixable = []  # (file, old_link, new_stem)
unfixable = []

for file_path, full_link, link_name in broken_links:
    found = None
    
    # 1. 精确模糊匹配
    kw = extract_keywords(link_name)
    if kw in fuzzy_index and len(fuzzy_index[kw]) == 1:
        found = fuzzy_index[kw][0]
    
    # 2. 包含匹配（短链接匹配长文件名的前缀）
    if not found:
        matches = [stem for stem in filename_index if stem.startswith(link_name) or stem.endswith(link_name)]
        if len(matches) == 1:
            found = matches[0]
    
    if found:
        fixable.append((file_path, full_link, found))
    else:
        unfixable.append((file_path, full_link, link_name))

print(f'总断链数: {len(broken_links)}')
print(f'可自动修复: {len(fixable)}')
print(f'无法自动修复: {len(unfixable)}')
print()

print('=== 可修复示例 (前20个) ===')
for f, old, new in fixable[:20]:
    print(f'  {f}: [[{old}]] → [[{new}]]')

print()
print('=== 无法修复的断链目标 (按频率) ===')
unfixable_targets = Counter(b[2] for b in unfixable)
for target, count in unfixable_targets.most_common(30):
    print(f'  {count}次: [[{target}]]')

import re
from pathlib import Path
from collections import defaultdict

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

def extract_base_name(filename):
    """提取文件名的基础部分（去掉 @ 标签和 emoji 前缀）"""
    name = filename
    if ' @ ' in name:
        name = name.split(' @ ')[0]
    # 去掉开头的 emoji 和编号
    name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\s\d\-]+', '', name)
    return name.strip()

# 构建基础名索引
base_name_index = defaultdict(list)
for stem in filename_index:
    base = extract_base_name(stem)
    if base:
        base_name_index[base].append(stem)

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

fixes = []
skipped = []

for f in md_files:
    try:
        content = f.read_text(encoding='utf-8')
    except:
        continue
    
    original_content = content
    
    for match in list(wiki_re.finditer(content)):
        full_match = match.group(0)
        link_target = match.group(1).strip()
        link_suffix = match.group(2)
        
        if not link_target:
            continue
        
        # 跳过带路径的链接（可能是相对路径或目录链接）
        if '/' in link_target or '\\' in link_target:
            continue
        
        link_name = link_target
        
        if link_name in filename_index:
            continue  # 已经存在，跳过
        
        new_target = None
        fix_type = None
        
        # 1. 基础名精确匹配（唯一匹配）
        base = extract_base_name(link_name)
        if base in base_name_index and len(base_name_index[base]) == 1:
            new_target = base_name_index[base][0]
            fix_type = '基础名匹配'
        
        # 2. 前缀匹配（唯一匹配，且链接长度 >= 6）
        if not new_target and len(link_name) >= 6:
            prefix_matches = [s for s in filename_index if s.startswith(link_name)]
            if len(prefix_matches) == 1:
                new_target = prefix_matches[0]
                fix_type = '前缀匹配'
        
        # 3. 后缀匹配（唯一匹配，且链接长度 >= 6）
        if not new_target and len(link_name) >= 6:
            suffix_matches = [s for s in filename_index if s.endswith(link_name)]
            if len(suffix_matches) == 1:
                new_target = suffix_matches[0]
                fix_type = '后缀匹配'
        
        if new_target and new_target != link_target:
            new_full = f'[[{new_target}{link_suffix}]]'
            if new_full != full_match:
                fixes.append((str(f.relative_to(vault)), full_match, new_full, fix_type))
                content = content.replace(full_match, new_full)
        else:
            skipped.append((str(f.relative_to(vault)), full_match))
    
    if content != original_content:
        f.write_text(content, encoding='utf-8')

print(f'可修复: {len(fixes)} 个')
print(f'跳过: {len(skipped)} 个')
print()
print('=== 修复列表 ===')
for f, old, new, ftype in fixes:
    print(f'  [{ftype}] {f}: {old} → {new}')

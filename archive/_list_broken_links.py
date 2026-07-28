import re
import sys
import os
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(r'd:\Python')))
from obsidian_common import should_skip_dir, should_skip_file, read_text_safe

vault = Path(r'd:\Obsidian\LeoDiary')

# 扫描所有 .md 文件（包括索引文件）
all_md_files = []
for root, dirs, files in os.walk(vault):
    dirs[:] = [d for d in dirs if not should_skip_dir(d)]
    for fname in files:
        if fname.endswith('.md'):
            all_md_files.append(Path(root) / fname)

filename_index = {f.stem for f in all_md_files}

# 目录名索引
dir_names = set()
for f in all_md_files:
    try:
        rel = f.relative_to(vault)
        for part in rel.parts[:-1]:
            dir_names.add(part)
    except ValueError:
        pass

# 基础名索引
def _extract_base_name(fname):
    name = fname
    if ' @ ' in name:
        name = name.split(' @ ')[0]
    name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\s\d\-]+', '', name)
    return name.strip()

base_name_map = {}
for stem in filename_index:
    base = _extract_base_name(stem)
    if base and base not in base_name_map:
        base_name_map[base] = stem

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

broken_links = []

for f in all_md_files:
    try:
        content = f.read_text(encoding='utf-8')
    except:
        continue
    cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    cleaned = re.sub(r'`[^`]*`', '', cleaned)
    
    for match in wiki_re.finditer(cleaned):
        link_target = match.group(1).strip()
        if not link_target:
            continue
        
        # 跳过模板语法
        if '<%' in link_target or '%>' in link_target:
            continue
        
        link_name = link_target.split('/')[-1].split('\\')[-1].strip()
        if not link_name:
            continue
        
        link_name_clean = link_name.rstrip('\\/')
        if not link_name_clean:
            continue
        
        # 1. 精确文件匹配
        if link_name_clean in filename_index:
            continue
        
        # 2. 目录链接
        if link_name_clean in dir_names:
            continue
        
        # 3. 基础名模糊匹配
        base = _extract_base_name(link_name_clean)
        if base and base in base_name_map:
            continue
        
        # 4. 前缀匹配（唯一）
        if len(link_name_clean) >= 5:
            prefix_matches = [s for s in filename_index if s.startswith(link_name_clean)]
            if len(prefix_matches) == 1:
                continue
        
        broken_links.append((str(f.relative_to(vault)), link_target, link_name_clean))

print(f'总断链数: {len(broken_links)}')
print(f'涉及文件数: {len(set(b[0] for b in broken_links))}')
print()

target_counts = Counter(b[1] for b in broken_links)
print('所有断链目标:')
for target, count in target_counts.most_common():
    files = [b[0] for b in broken_links if b[1] == target]
    print(f'  {count}次: [[{target}]]')
    for f in files[:3]:
        print(f'    ← {f}')
    if len(files) > 3:
        print(f'    ... 还有 {len(files)-3} 个文件')

import re
from pathlib import Path
from collections import Counter, defaultdict

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

# 构建完整路径索引
full_path_index = {}
for f in md_files:
    rel = str(f.relative_to(vault))
    rel_no_ext = rel[:-3]  # 去掉 .md
    full_path_index[rel_no_ext] = f
    # 也添加用正斜杠的版本
    full_path_index[rel_no_ext.replace('\\', '/')] = f

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

broken_links = []

for f in md_files:
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
        
        # 检查是否存在
        link_name = link_target.split('/')[-1].split('\\')[-1].strip()
        
        exists = False
        if link_name in filename_index:
            exists = True
        elif link_target in full_path_index:
            exists = True
        elif link_target.replace('\\', '/') in full_path_index:
            exists = True
        
        if not exists:
            broken_links.append((str(f.relative_to(vault)), link_target, link_name))

print(f'总断链数: {len(broken_links)}')
print(f'涉及文件数: {len(set(b[0] for b in broken_links))}')
print()

# 按断链目标频率排序
target_counts = Counter(b[1] for b in broken_links)
print('Top 50 断链目标:')
for target, count in target_counts.most_common(50):
    print(f'  {count}次: [[{target}]]')

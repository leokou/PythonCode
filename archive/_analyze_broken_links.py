import re
from pathlib import Path
from collections import Counter

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

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

print(f'总断链数: {len(broken_links)}')
print(f'涉及文件数: {len(set(b[0] for b in broken_links))}')
print()

target_counts = Counter(b[2] for b in broken_links)
print('Top 30 最常见断链目标:')
for target, count in target_counts.most_common(30):
    print(f'  {count}次: [[{target}]]')

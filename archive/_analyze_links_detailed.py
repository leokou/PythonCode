import re
from pathlib import Path
from collections import Counter, defaultdict

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

# 构建目录索引
dir_index = set()
for f in md_files:
    # 把所有父目录都加进去
    parts = f.relative_to(vault).parts
    for i in range(1, len(parts)):
        dir_path = '/'.join(parts[:i])
        dir_index.add(dir_path)
        dir_index.add(parts[i-1])  # 目录名本身

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

# 分类统计
categories = {
    '有效文件链接': 0,
    '目录链接（末尾带\\）': 0,
    '目录链接（纯目录名）': 0,
    '简写链接（可模糊匹配）': 0,
    '相对路径链接': 0,
    '真正断链': 0,
}

true_broken = []

def extract_base_name(filename):
    name = filename
    if ' @ ' in name:
        name = name.split(' @ ')[0]
    name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\s\d\-]+', '', name)
    return name.strip()

base_name_index = defaultdict(list)
for stem in filename_index:
    base = extract_base_name(stem)
    if base:
        base_name_index[base].append(stem)

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
        
        link_name = link_target.split('/')[-1].split('\\')[-1].strip()
        
        # 1. 精确文件匹配
        if link_name in filename_index:
            categories['有效文件链接'] += 1
            continue
        
        # 2. 末尾带 \ 或 / 的目录链接
        if link_target.endswith('\\') or link_target.endswith('/'):
            categories['目录链接（末尾带\\）'] += 1
            continue
        
        # 3. 纯目录名匹配
        if link_name in dir_index:
            categories['目录链接（纯目录名）'] += 1
            continue
        
        # 4. 简写链接（可模糊匹配到唯一文件）
        base = extract_base_name(link_name)
        if base in base_name_index and len(base_name_index[base]) == 1:
            categories['简写链接（可模糊匹配）'] += 1
            continue
        
        # 5. 前缀匹配（唯一）
        prefix_matches = [s for s in filename_index if s.startswith(link_name)]
        if len(prefix_matches) == 1:
            categories['简写链接（可模糊匹配）'] += 1
            continue
        
        # 6. 相对路径链接（含 .. 或路径分隔符）
        if '..' in link_target or '/' in link_target or '\\' in link_target:
            categories['相对路径链接'] += 1
            continue
        
        # 其他都算真正断链
        categories['真正断链'] += 1
        true_broken.append((str(f.relative_to(vault)), link_target))

print('=== 链接分类统计 ===')
for cat, count in categories.items():
    print(f'  {cat}: {count}')
print()

print(f'真正断链数: {len(true_broken)}')
print(f'涉及文件数: {len(set(b[0] for b in true_broken))}')
print()

print('=== 真正断链列表（按频率）===')
broken_targets = Counter(b[1] for b in true_broken)
for target, count in broken_targets.most_common(40):
    print(f'  {count}次: [[{target}]]')

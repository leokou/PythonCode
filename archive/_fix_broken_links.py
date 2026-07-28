import re
from pathlib import Path
from collections import defaultdict

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

def extract_keywords(filename):
    name = filename
    if ' @ ' in name:
        name = name.split(' @ ')[0]
    name = re.sub(r'^[\U0001F300-\U0001FAFF\s\d\-]+', '', name)
    return name.strip()

fuzzy_index = defaultdict(list)
for stem, fpath in filename_index.items():
    kw = extract_keywords(stem)
    if kw:
        fuzzy_index[kw].append(stem)

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

fixes = []  # (file_path, old_link_full, new_link_full)

for f in md_files:
    try:
        content = f.read_text(encoding='utf-8')
    except:
        continue
    
    original_content = content
    cleaned_for_check = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    cleaned_for_check = re.sub(r'`[^`]*`', '', cleaned_for_check)
    
    for match in wiki_re.finditer(content):
        full_match = match.group(0)
        link_target = match.group(1).strip()
        link_suffix = match.group(2)  # |alias 或 #heading
        
        if not link_target:
            continue
        
        link_name = link_target.split('/')[-1].split('\\')[-1].strip()
        if not link_name:
            continue
        
        new_target = None
        
        # 1. 去掉 .md 扩展名
        if link_name.endswith('.md'):
            no_ext = link_name[:-3]
            if no_ext in filename_index:
                new_target = link_target[:-3]
        
        # 2. 精确模糊匹配
        if not new_target:
            kw = extract_keywords(link_name)
            if kw in fuzzy_index and len(fuzzy_index[kw]) == 1:
                new_stem = fuzzy_index[kw][0]
                # 保留路径前缀
                if '/' in link_target or '\\' in link_target:
                    # 简单处理：只替换文件名部分
                    parts = re.split(r'[\\/]', link_target)
                    parts[-1] = new_stem
                    new_target = '/'.join(parts)
                else:
                    new_target = new_stem
        
        # 3. 前缀匹配（唯一匹配）
        if not new_target:
            matches = [stem for stem in filename_index 
                      if stem.startswith(link_name) or stem.endswith(link_name)]
            if len(matches) == 1:
                if '/' in link_target or '\\' in link_target:
                    parts = re.split(r'[\\/]', link_target)
                    parts[-1] = matches[0]
                    new_target = '/'.join(parts)
                else:
                    new_target = matches[0]
        
        if new_target and new_target != link_target:
            new_full = f'[[{new_target}{link_suffix}]]'
            if new_full != full_match:
                fixes.append((str(f.relative_to(vault)), full_match, new_full))
                content = content.replace(full_match, new_full)
    
    if content != original_content:
        f.write_text(content, encoding='utf-8')

print(f'共修复 {len(fixes)} 个断链')
print()
for f, old, new in fixes:
    print(f'  {f}: {old} → {new}')

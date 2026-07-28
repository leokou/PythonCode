import re
from pathlib import Path

vault = Path(r'd:\Obsidian\LeoDiary')
md_files = [f for f in vault.rglob('*.md') if '_trash' not in str(f) and '.git' not in str(f) and '.workbuddy' not in str(f)]
filename_index = {f.stem: f for f in md_files}

wiki_re = re.compile(r'\[\[([^\]|#]+)([^\]]*)\]\]')

fixes = []

for f in md_files:
    try:
        content = f.read_text(encoding='utf-8')
    except:
        continue
    
    original_content = content
    
    for match in wiki_re.finditer(content):
        full_match = match.group(0)
        link_target = match.group(1).strip()
        link_suffix = match.group(2)
        
        if not link_target:
            continue
        
        link_name = link_target.split('/')[-1].split('\\')[-1].strip()
        if not link_name:
            continue
        
        new_target = None
        
        # 1. 去掉 .md 扩展名（确定的修复）
        if link_name.endswith('.md'):
            no_ext = link_name[:-3]
            if no_ext in filename_index:
                # 重建链接路径
                if '/' in link_target or '\\' in link_target:
                    parts = re.split(r'[\\/]', link_target)
                    parts[-1] = no_ext
                    new_target = '/'.join(parts)
                else:
                    new_target = no_ext
        
        if new_target and new_target != link_target:
            new_full = f'[[{new_target}{link_suffix}]]'
            if new_full != full_match:
                fixes.append((str(f.relative_to(vault)), full_match, new_full))
                content = content.replace(full_match, new_full)
    
    if content != original_content:
        f.write_text(content, encoding='utf-8')

print(f'共修复 {len(fixes)} 个断链（仅去掉 .md 扩展名）')
for f, old, new in fixes:
    print(f'  {f}: {old} → {new}')

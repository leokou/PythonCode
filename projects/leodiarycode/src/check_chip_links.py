import os, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

vault = r'D:\Obsidian\LeoDiary'
for dname in sorted(os.listdir(vault)):
    dp = os.path.join(vault, dname)
    if not os.path.isdir(dp):
        continue
    for f in sorted(os.listdir(dp)):
        if f.startswith('\U0001f9e9 \u76ee\u5f55-') and f.endswith('.md'):
            fp = os.path.join(dp, f)
            content = open(fp, 'r', encoding='utf-8-sig').read()
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            has_subdir_links = False
            for l in links:
                parts = l.replace('\\', '/').split('/')
                if len(parts) > 1 or '\\' in l or '/' in l:
                    has_subdir_links = True
            
            print(f'{dname}/{f}: {len(links)} links')
            if has_subdir_links:
                print(f'  *** HAS SUBDIR REFERENCES ***')
            for l in links[:5]:
                print(f'  [[{l}]]')
            if len(links) > 5:
                print(f'  ...')
            print()

import os, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

vault = r'D:\Obsidian\LeoDiary'
target = os.path.join(vault, '1- \U0001f916AI \u76f8\u5173')
print(f'Checking: {target}')
print(f'Exists: {os.path.isdir(target)}')

if os.path.isdir(target):
    for f in sorted(os.listdir(target)):
        print(f)
        fp = os.path.join(target, f)
        if os.path.isfile(fp) and f.startswith('\U0001f9e9'):
            print('  *** IS CHIP FILE ***')
            
# Also check the backup
backup = r'D:\Obsidian\Backup'
if os.path.isdir(backup):
    for b in sorted(os.listdir(backup)):
        if 'LeoDiary' in b:
            print(f'\nBackup: {b}')
            ai_dir = os.path.join(backup, b, '1- \U0001f916AI \u76f8\u5173')
            if os.path.isdir(ai_dir):
                for f in sorted(os.listdir(ai_dir)):
                    print(f'  {f}')

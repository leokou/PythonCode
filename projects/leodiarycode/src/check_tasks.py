import subprocess, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ps_script = r'''
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -like "*obsidian*" -or $_.TaskPath -like "*home*" -or $_.TaskName -like "*index*" -or $_.TaskName -like "*move*" -or $_.TaskName -like "*sync*" }
if ($tasks) {
    $tasks | Format-Table TaskName, TaskPath, State -AutoSize
} else {
    Write-Output "No matching scheduled tasks found"
}
'''
r = subprocess.run(['powershell.exe', '-Command', ps_script], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
print(r.stdout)
if r.stderr.strip():
    print('ERR:', r.stderr.strip()[:200])

# ============================================================
#  git_push.ps1  日常同步：拉取 / 推送 / 拉取+推送
#  通常由 git_push.bat 调用，也可命令行运行：
#     powershell -ExecutionPolicy Bypass -File D:\Python\tools\git-scripts\git_push.ps1 -Mode sync
#  Mode: pull=只拉取, push=只推送, sync=先拉取再推送（推荐）
#  不带参数时显示菜单供选择。
#  仓库根：D:\Python\tools（独立 git 仓库，同步 cnb.cool/leokous/Python-tools）
# ============================================================

param([string]$Mode = "")

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

if ($Mode -notin @("pull", "push", "sync")) {
    Write-Host ""
    Write-Host "请选择操作："
    Write-Host "  1 - 拉取服务器代码到本地 (pull)"
    Write-Host "  2 - 提交并推送 (push)"
    Write-Host "  3 - 拉取 + 推送 (sync，推荐)"
    $choice = Read-Host "输入数字回车（默认 3）"
    switch ($choice) {
        "1" { $Mode = "pull" }
        "2" { $Mode = "push" }
        default { $Mode = "sync" }
    }
}

function Get-AuthUrl {
    $gitUser = Read-Host "Git Username（CNB，一般填 cnb）"
    $token   = Read-Host "访问令牌 Token"
    $repoUrl = git remote get-url origin
    $uri = [System.Uri]$repoUrl
    return "https://$([System.Uri]::EscapeDataString($gitUser)):$([System.Uri]::EscapeDataString($token))@$($uri.Host)$($uri.AbsolutePath)"
}

function Invoke-Git {
    param([string]$Desc, [string[]]$GitArgs)
    Write-Host ""
    Write-Host $Desc
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & git @GitArgs 2>&1
        foreach ($line in $out) { Write-Host $line.ToString() }
    } finally {
        $ErrorActionPreference = $oldEAP
    }
    return $LASTEXITCODE
}

# ---------- 检查是否已绑定远端 ----------
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$hasOrigin = [bool](git remote | Select-String "^origin$")
$ErrorActionPreference = $oldEAP
if (-not $hasOrigin) {
    Write-Host "尚未绑定远端 origin。请先运行初始化脚本："
    Write-Host "   git_init_cnb.bat"
    exit 1
}

# ---------- 当前分支 ----------
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$branch = (git branch --show-current).Trim()
$ErrorActionPreference = $oldEAP
if (-not $branch) {
    Write-Host "当前处于游离 HEAD 状态，无法同步，请先切回分支。"
    exit 1
}

# ---------- 检查本地改动 ----------
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$status = git status --short 2>&1 | Out-String
$ErrorActionPreference = $oldEAP
$hasChanges = -not [string]::IsNullOrWhiteSpace($status)

if ($hasChanges) {
    Write-Host ""
    Write-Host "本次改动清单："
    Write-Host $status
}

# ---------- 提交（push/sync 且有改动）----------
if ($Mode -ne "pull" -and $hasChanges) {
    $msg = Read-Host "请输入提交信息（直接回车默认：更新内容）"
    if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "更新内容" }
    $code = Invoke-Git "正在提交..." @("add", "-A")
    if ($code -eq 0) { $code = Invoke-Git "正在提交..." @("commit", "-m", $msg) }
    if ($code -ne 0) { Write-Host "x 提交失败"; exit 1 }
} elseif ($Mode -eq "pull" -and $hasChanges) {
    Write-Host "警告：本地有未提交改动，直接拉取可能被拒绝。"
    $ans = Read-Host "是否仍继续拉取？（y/n，默认 n）"
    if ($ans -notmatch "^[yY]") { Write-Host "已取消。"; exit 0 }
}

# ---------- 拉取（pull/sync）----------
if ($Mode -ne "push") {
    $code = Invoke-Git "正在拉取服务器代码到本地（pull --rebase）..." @("pull", "--rebase", "origin", $branch)
    if ($code -ne 0) {
        $ans = Read-Host "拉取失败，是否用令牌重试？（y/n，默认 y）"
        if ($ans -match "^[nN]") { exit 1 }
        $authUrl = Get-AuthUrl
        $code2 = Invoke-Git "使用令牌重试拉取..." @("pull", "--rebase", $authUrl, $branch)
        if ($code2 -ne 0) {
            Write-Host ""
            Write-Host "拉取仍失败：请解决冲突或检查网络后重试。"
            exit 1
        }
    }
}

# ---------- 推送（push/sync，且有改动）----------
if ($Mode -ne "pull") {
    if ($hasChanges) {
        $code = Invoke-Git "正在推送到服务器 ..." @("push", "origin", $branch)
        if ($code -ne 0) {
            $ans = Read-Host "推送失败，是否用令牌重试？（y/n，默认 y）"
            if ($ans -match "^[nN]") { exit 1 }
            $authUrl = Get-AuthUrl
            $code2 = Invoke-Git "使用令牌重试推送..." @("push", $authUrl, $branch)
            if ($code2 -ne 0) {
                Write-Host ""
                Write-Host "推送仍失败：若远端有新提交，请先拉取合并（选择模式 3）后重试。"
                exit 1
            }
        }
        Write-Host "push ok"
    } else {
        Write-Host ""
        Write-Host "本地无改动，已跳过提交与推送。"
    }
}

if ($Mode -ne "push") {
    Write-Host "sync ok"
}

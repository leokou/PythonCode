# ============================================================
#  git_init_cnb.ps1  tools 独立仓库首次推送 cnb.cool 一键初始化
#
#  用法：在【D:\Python\tools】目录打开 PowerShell 后执行：
#      powershell -ExecutionPolicy Bypass -File D:\Python\tools\git-scripts\git_init_cnb.ps1
#
#  运行后提示输入 Git Username / 访问令牌（仓库地址默认 Python-tools）
#  会自动完成：git init、首次提交、绑定 origin、分支改为 main、推送
# ============================================================

param(
    [string]$RepoUrl = "https://cnb.cool/leokous/Python-tools.git",
    [string]$GitUser,
    [string]$Token,
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Read-Required([string]$Prompt) {
    $v = Read-Host $Prompt
    while ([string]::IsNullOrWhiteSpace($v)) {
        $v = Read-Host "不能为空，$Prompt"
    }
    return $v.Trim()
}

Write-Host ""
Write-Host "==============================================="
Write-Host "  tools 独立仓库推送 cnb.cool 初始化"
Write-Host "==============================================="

# ---------- 第 1 步：收集信息 ----------
if (-not $GitUser) { $GitUser = Read-Required "第1步 请输入 Git Username（CNB 访问令牌中的，一般是 cnb）" }
if (-not $Token)   { $Token   = Read-Required "第1步 请输入访问令牌 Token" }

if ($RepoUrl -notmatch "^https?://") { throw "仓库地址必须以 http(s):// 开头" }
$uri = [System.Uri]$RepoUrl
$authUrl = "https://$([System.Uri]::EscapeDataString($GitUser)):$([System.Uri]::EscapeDataString($Token))@$($uri.Host)$($uri.AbsolutePath)"

# ---------- 第 2 步：确认 Git 仓库与首次提交 ----------
if (-not (Test-Path ".git")) {
    Write-Host "当前目录不是 Git 仓库，正在初始化 ..."
    git init
}
$head = git rev-parse --verify HEAD 2>$null
if (-not $head) {
    Write-Host ""
    Write-Host "第2步 当前仓库还没有任何提交，请先创建首次提交。"
    $initMsg = Read-Host "首次提交信息（默认：初始化项目）"
    if ([string]::IsNullOrWhiteSpace($initMsg)) { $initMsg = "初始化项目" }
    git add -A
    git commit -m $initMsg
}

# ---------- 第 3 步：绑定 origin 远端 ----------
if (git remote | Select-String "^origin$") {
    Write-Host ""
    Write-Host "已存在 origin 远端：$(git remote get-url origin)"
    $ans = Read-Host "是否覆盖为 $RepoUrl ？（y/n，默认 n）"
    if ($ans -match "^[yY]") { git remote set-url origin $RepoUrl } else { Write-Host "保留现有 origin。" }
} else {
    git remote add origin $RepoUrl
}
git branch -M $Branch

# ---------- 第 4 步：推送 ----------
Write-Host ""
Write-Host "第4步 正在推送 $Branch 到 $RepoUrl ..."
$pushOut = git push $authUrl $Branch 2>&1 | Out-String
Write-Host $pushOut
$pushOk = ($LASTEXITCODE -eq 0)

if (-not $pushOk) {
    Write-Host ""
    Write-Host "推送被拒绝（远端可能有内容或历史分叉）。正在检查远端状态 ..."
    git fetch $authUrl $Branch 2>$null | Out-Null
    $remoteCommitCount = 0
    if ($LASTEXITCODE -eq 0) {
        $remoteCommitCount = (git log FETCH_HEAD --oneline 2>$null | Measure-Object -Line).Lines
    }
    if ($remoteCommitCount -le 1) {
        $ans = Read-Host "远端提交数 $remoteCommitCount，疑似空仓库/占位仓库，是否强制覆盖？（y/n，默认 n）"
        if ($ans -match "^[yY]") {
            $forceOut = git push --force $authUrl $Branch 2>&1 | Out-String
            Write-Host $forceOut
            $pushOk = ($LASTEXITCODE -eq 0)
        }
    } else {
        Write-Host "远端有真实内容，为避免覆盖请手动处理：先 git pull --rebase 合并，再执行 git push。"
    }
}

if ($pushOk) {
    git config branch.$Branch.remote origin
    git config branch.$Branch.merge refs/heads/$Branch
    Write-Host ""
    Write-Host "push ok: $RepoUrl ($Branch)"
    Write-Host "后续日常更新请运行：git_push.ps1"
} else {
    Write-Host ""
    Write-Host "push fail: 请根据上方提示处理。"
}

# setup-access.ps1 — 给 Mac 端 agent 装 SSH 公钥（只做这一件事，可重复执行）
# 用法：管理员 PowerShell 里执行
#   irm http://100.66.36.4:8000/setup.ps1 | iex
# 或：powershell -ExecutionPolicy Bypass -File .\setup-access.ps1

$ErrorActionPreference = 'Stop'
$Key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB6VFxQwzU/oa+5OazDXuGEQViGarvVhXN53uJClq+SP pc-agent@macbook-pro-3'

function Add-Key([string]$Path) {
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType File -Path $Path | Out-Null }
    $cur = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($cur -notmatch [regex]::Escape($Key)) { Add-Content -LiteralPath $Path -Value $Key -Encoding Ascii }
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# 1) 普通用户路径（非管理员账户走这里）
$userKeyFile = Join-Path $env:USERPROFILE '.ssh\authorized_keys'
Add-Key $userKeyFile
icacls.exe $userKeyFile /inheritance:r /grant:r "$($env:USERNAME):F" /grant:r "SYSTEM:F" | Out-Null

# 2) Administrators 组成员：Windows OpenSSH 默认读 ProgramData 下这个文件
if ($isAdmin) {
    $adminKeyFile = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
    Add-Key $adminKeyFile
    icacls.exe $adminKeyFile /inheritance:r /grant:r "SYSTEM:F" /grant:r "Administrators:F" | Out-Null
}

Write-Output '--- OK: 公钥已安装 ---'
Write-Output ('user     : ' + (whoami))
Write-Output ('computer : ' + $env:COMPUTERNAME)
Write-Output ('elevated : ' + $isAdmin)
Write-Output ('user file: ' + $userKeyFile)
if ($isAdmin) { Write-Output ('admin file: ' + (Join-Path $env:ProgramData 'ssh\administrators_authorized_keys')) }

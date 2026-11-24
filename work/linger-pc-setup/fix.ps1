# fix.ps1 — 把 Mac 端公钥写进 Windows OpenSSH 的 administrators_authorized_keys（自提权）
# 用法（普通 PowerShell 即可）：
#   irm http://100.66.36.4:8000/fix.ps1 | iex
# 行为：非管理员时自动请求提权（UAC 点「是」），提权后写 key、修 ACL、打印诊断，
#       并把诊断 JSON POST 回 Mac 的暂存服务（http://100.66.36.4:8000/report/adminkey）。

$ErrorActionPreference = 'Stop'
$Key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB6VFxQwzU/oa+5OazDXuGEQViGarvVhXN53uJClq+SP pc-agent@macbook-pro-3'
$Url = 'http://100.66.36.4:8000/fix.ps1'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Output '需要管理员权限，正在请求提权：请在弹窗里点「是」。'
    $tmp = Join-Path $env:TEMP 'linger-fix-admin.ps1'
    Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $tmp)
    Write-Output '已发出提权请求。新窗口跑完会显示 OK；窗口停留 15 秒。'
    return
}

# ---- 已提权 ----
$adminFile = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
$userFile = Join-Path $env:USERPROFILE '.ssh\authorized_keys'

function Add-Key([string]$Path) {
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType File -Path $Path | Out-Null }
    $cur = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($cur -notmatch [regex]::Escape($Key)) { Add-Content -LiteralPath $Path -Value $Key -Encoding Ascii }
}

Add-Key $adminFile
Add-Key $userFile
icacls.exe $adminFile /inheritance:r /grant:r 'SYSTEM:F' /grant:r 'Administrators:F' | Out-Null
icacls.exe $userFile /inheritance:r /grant:r "$($env:USERNAME):F" /grant:r 'SYSTEM:F' | Out-Null

# ---- 诊断 ----
$diag = [ordered]@{
    at               = (Get-Date).ToString('s')
    whoami           = (whoami)
    computer         = $env:COMPUTERNAME
    elevated         = $true
    adminFile        = $adminFile
    adminExists      = (Test-Path -LiteralPath $adminFile)
    adminKeyPresent  = ((Get-Content -LiteralPath $adminFile -Raw -ErrorAction SilentlyContinue) -match 'ssh-ed25519')
    adminAcl         = (icacls.exe $adminFile | Out-String)
    userFile         = $userFile
    userExists       = (Test-Path -LiteralPath $userFile)
    userKeyPresent   = ((Get-Content -LiteralPath $userFile -Raw -ErrorAction SilentlyContinue) -match 'ssh-ed25519')
    sshdService      = (Get-Service sshd -ErrorAction SilentlyContinue).Status
    sshdConfig       = (Get-Content 'C:\ProgramData\ssh\sshd_config' -ErrorAction SilentlyContinue |
                        Select-String -Pattern 'AuthorizedKeysFile|PubkeyAuthentication|Match Group administrators' -Context 0, 2 | Out-String)
    adminsGroup      = (net localgroup Administrators 2>$null | Out-String)
}

$posted = $false
try {
    Invoke-RestMethod -Uri 'http://100.66.36.4:8000/report/adminkey' -Method Post -Body ($diag | ConvertTo-Json -Depth 6) -ContentType 'application/json' -TimeoutSec 20 | Out-Null
    $posted = $true
} catch { $posted = $false }

Write-Output '--- OK ---'
Write-Output ('whoami      : ' + (whoami))
Write-Output ('admin file  : ' + $adminFile)
Write-Output ('key present : ' + $diag.adminKeyPresent)
Write-Output ('sshd        : ' + $diag.sshdService)
Write-Output ('reported    : ' + $posted)
Write-Output ''
Write-Output '15 秒后窗口自动关闭。'
Start-Sleep -Seconds 15

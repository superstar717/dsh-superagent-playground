# prep.ps1 — Linger PC 体检 / 底座准备（Windows 10/11 x64）
# 默认只读体检：powershell -ExecutionPolicy Bypass -File .\prep.ps1
# 应用安全设置（电源高性能/AC 不休眠/长路径/建目录，需管理员）：
#   powershell -ExecutionPolicy Bypass -File .\prep.ps1 -Apply
# 输出：F:\AI\logs\prep-<时间>.json（有 F: 时）并打印摘要

param([switch]$Apply, [switch]$AllowDefenderExclusion)

$ErrorActionPreference = 'Continue'
$report = [ordered]@{}
$report.generatedAt = (Get-Date).ToString('s')
$report.computer = $env:COMPUTERNAME
$report.user = (whoami)
$report.elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# ---- OS ----
$os = Get-CimInstance Win32_OperatingSystem
$report.os = [ordered]@{ caption = $os.Caption; version = $os.Version; build = $os.BuildNumber; arch = $os.OSArchitecture }
$report.powershell = $PSVersionTable.PSVersion.ToString()

# ---- CPU / RAM ----
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$report.cpu = [ordered]@{ name = $cpu.Name.Trim(); cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors; virtualizationFirmware = $cpu.VirtualizationFirmwareEnabled; avx2 = $null }
$report.ramGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)

# ---- 磁盘 ----
$report.disks = @()
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $report.disks += [ordered]@{ letter = $_.DeviceID; fs = $_.FileSystem; sizeGB = [math]::Round($_.Size / 1GB, 1); freeGB = [math]::Round($_.FreeSpace / 1GB, 1) }
}

# ---- GPU / 驱动 ----
$report.gpus = @()
Get-CimInstance Win32_VideoController | ForEach-Object {
    $report.gpus += [ordered]@{ name = $_.Name; driverVersion = $_.DriverVersion; driverDate = $_.DriverDate }
}
try { $nv = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null } catch { $nv = $null }
$report.nvidiaSmi = if ($nv) { ($nv -join '; ') } else { 'nvidia-smi 不可用（未装驱动或不在 PATH）' }
try { $report.cudaVersion = ((& nvidia-smi 2>$null) | Select-String 'CUDA Version').ToString().Trim() } catch { $report.cudaVersion = $null }

# ---- 页面文件 ----
$report.pagefile = if (Get-CimInstance Win32_PageFileUsage) { (Get-CimInstance Win32_PageFileUsage | ForEach-Object { "$($_.Name) $($_.AllocatedBaseSize)MB" }) -join '; ' } else { '系统管理/未设置' }

# ---- 电源 ----
$report.powerScheme = ((& powercfg /getactivescheme) -join '').Trim()
try {
    $sub = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>$null | Select-String 'AC Power Setting Index' | Select-Object -First 1).ToString()
    $report.acStandbySeconds = $sub
} catch { $report.acStandbySeconds = $null }

# ---- 长路径 ----
$report.longPathsEnabled = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled

# ---- 服务/依赖 ----
$report.opensshService = (Get-Service sshd -ErrorAction SilentlyContinue).Status
try { $report.tailscale = (Get-Process tailscaled -ErrorAction SilentlyContinue).Id } catch { $report.tailscale = $null }
try { $report.defender = (Get-MpComputerStatus).RealTimeProtectionEnabled } catch { $report.defender = $null }

# ---- 判定 ----
$checks = [ordered]@{}
$f = $report.disks | Where-Object { $_.letter -eq 'F:' } | Select-Object -First 1
$e = $report.disks | Where-Object { $_.letter -eq 'E:' } | Select-Object -First 1
$checks.F_disk = if ($f) { "F: $($f.fs) $($f.freeGB)/$($f.sizeGB) GB free" } else { 'F: 不存在' }
$checks.E_disk = if ($e) { "E: $($e.fs) $($e.freeGB)/$($e.sizeGB) GB free" } else { 'E: 不存在' }
$checks.F_space_ok_39GB = if ($f) { $f.freeGB -ge 45 } else { $false }
$checks.F_space_ok_80GB = if ($f) { $f.freeGB -ge 90 } else { $false }
$checks.ram_ok_125B = ($report.ramGB -ge 32)
$checks.ram_64GB = ($report.ramGB -ge 60)
$checks.gpu_12GB = ($report.nvidiaSmi -match '12288MiB|12GB|12 GiB|12282MiB|12288')
$checks.win10_11_x64 = ($report.os.arch -eq '64-bit' -and ([int]($report.os.build) -ge 19041))
$report.checks = $checks

# ---- 可选：应用底座设置 ----
if ($Apply) {
    if (-not $report.elevated) { Write-Warning '-Apply 需要管理员 PowerShell，已跳过设置' }
    else {
        $report.applied = @()
        # 电源：高性能 + AC 不休眠/不关屏
        & powercfg /setactive SCHEME_MIN | Out-Null
        & powercfg /change standby-timeout-ac 0 | Out-Null
        & powercfg /change hibernate-timeout-ac 0 | Out-Null
        & powercfg /change monitor-timeout-ac 0 | Out-Null
        $report.applied += 'power: 高性能 + AC 不休眠/不关屏'
        # 长路径
        Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1 -Type DWord
        $report.applied += 'longPaths=1'
        # 目录
        $dirs = @()
        if ($f) { $dirs += 'F:\AI', 'F:\AI\models', 'F:\AI\logs' }
        if ($e) { $dirs += 'E:\AI', 'E:\AI\backup' }
        foreach ($d in $dirs) { if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }
        $report.applied += ('dirs: ' + ($dirs -join ', '))
        # 可选 Defender 排除（默认不动安全设置）
        if ($AllowDefenderExclusion -and $f) {
            Add-MpPreference -ExclusionPath 'F:\AI' -ErrorAction SilentlyContinue
            $report.applied += 'defender exclusion: F:\AI'
        }
    }
}

# ---- 输出 ----
$logDir = if (Test-Path 'F:\') { 'F:\AI\logs' } else { $env:TEMP }
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$out = Join-Path $logDir ('prep-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
$report | ConvertTo-Json -Depth 6

Write-Output ''
Write-Output ("[prep] report -> " + $out)
if ($checks.ram_ok_125B) { Write-Output '[prep] RAM 满足 125B（>=32GB）' } else { Write-Output '[prep] RAM 不足：125B 需 >=32GB，当前 ' + $report.ramGB + 'GB（等 64GB 升级）' }
if (-not $checks.F_space_ok_39GB) { Write-Output '[prep] F: 空间不足 45GB，模型请换盘或清理' }

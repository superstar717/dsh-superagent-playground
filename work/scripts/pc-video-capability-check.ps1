<#
12G 显存 PC「口播视频」能力体检（Windows 原生）
用法：
  powershell -ExecutionPolicy Bypass -File .\pc-video-capability-check.ps1
只读探测，不安装任何东西。AI 模型栈建议在 WSL2 里另跑 pc-video-capability-check.sh。

注意：本脚本在 macOS 上编写，尚未在真实 Windows 上实跑（作者环境无 PowerShell）。
     若报错，回传完整输出即可，通常是某条命令不存在导致的。
#>
$ErrorActionPreference = 'SilentlyContinue'

function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

$gpuOk = 0; $gpuName = ''; $vramMb = 0; $driver = ''; $cuda = ''
if (Have 'nvidia-smi') {
    & nvidia-smi *> $null
    if ($LASTEXITCODE -eq 0) {
        $gpuOk = 1
        $gpuName = [string](& nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
        $gpuName = $gpuName.Trim()
        $vramRaw = [string](& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
        $digits = $vramRaw -replace '\D', ''
        if ($digits) { $vramMb = [int]$digits }
        $driver = [string](& nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
        $driver = $driver.Trim()
        $cudaText = [string]((& nvidia-smi 2>$null) -join "`n")
        if ($cudaText -match 'CUDA Version:\s*([0-9.]+)') { $cuda = $Matches[1] }
    }
}
$vramGb = [int][math]::Round($vramMb / 1024.0)

$ramGb = 0
$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
if ($cs -and $cs.TotalPhysicalMemory) { $ramGb = [int][math]::Round($cs.TotalPhysicalMemory / 1GB) }

$diskFreeGb = 0
if ($env:USERPROFILE) {
    $driveLetter = $env:USERPROFILE.Substring(0, 1)
    $d = Get-PSDrive -Name $driveLetter -ErrorAction SilentlyContinue
    if ($d -and $d.Free) { $diskFreeGb = [int][math]::Round($d.Free / 1GB) }
}

$ffmpegVer = ''; $nvenc = 'none'
if (Have 'ffmpeg') {
    $ffLine = [string](& ffmpeg -version 2>$null | Select-Object -First 1)
    $ffParts = $ffLine -split ' '
    if ($ffParts.Count -ge 3) { $ffmpegVer = $ffParts[2] }
    $encText = [string]((& ffmpeg -hide_banner -encoders 2>$null) -join "`n")
    $found = @()
    foreach ($e in @('h264_nvenc', 'hevc_nvenc', 'av1_nvenc')) {
        if ($encText -match $e) { $found += $e }
    }
    if ($found.Count -gt 0) { $nvenc = $found -join ',' }
}
$nodeVer = ''
if (Have 'node') { $nodeVer = [string](& node -v 2>$null); $nodeVer = $nodeVer.Trim().TrimStart('v') }
$pyVer = ''
if (Have 'python') { $pyVer = [string](& python -V 2>$null); $pyVer = $pyVer.Trim() -replace '^Python\s*', '' }
$wsl = '未安装'
if (Have 'wsl') { $wsl = ([string](& wsl --status 2>$null)) -replace '\s+', ' '; if (-not $wsl) { $wsl = '已安装（--status 无输出）' } }

function Verdict($need, $tier, $label) {
    if ($vramGb -ge $need) { return "A`t$label" }
    return "$tier`t$label"
}

Write-Host '== 12G 显存 PC 口播视频能力体检（Windows 原生）=='
if ($gpuName) { Write-Host ("GPU        : " + $gpuName) } else { Write-Host 'GPU        : 未检测到 NVIDIA GPU' }
Write-Host ("显存       : $vramGb GB ($vramMb MB)")
if ($driver) { Write-Host ("驱动/CUDA  : $driver / $cuda") } else { Write-Host '驱动/CUDA  : n/a' }
Write-Host ("内存       : $ramGb GB")
Write-Host ("可用磁盘   : $diskFreeGb GB（模型盘建议 >=100GB）")
Write-Host ("Node/Python: " + $(if ($nodeVer) { $nodeVer } else { 'n/a' }) + ' / ' + $(if ($pyVer) { $pyVer } else { 'n/a' }))
Write-Host ("ffmpeg     : " + $(if ($ffmpegVer) { $ffmpegVer } else { 'n/a' }) + "；NVENC: $nvenc")
Write-Host ("WSL        : $wsl")
Write-Host ''
Write-Host '== 分档（A 够用 / B 降配 / C 只够草稿 / D 不够）=='
if ($gpuOk -eq 0) {
    Write-Host '—  剪辑/字幕/模板渲染（CPU 路径）：本机无 NVIDIA GPU，AI 加速环节不可用'
} else {
    $rows = @(
        (Verdict 6  'A' '剪辑 1080p（剪映/达芬奇，NVENC 编码）'),
        (Verdict 6  'A' 'TTS 声音克隆（CosyVoice2 fp16 6-8G / GPT-SoVITS 6G+）'),
        (Verdict 4  'A' 'ASR 字幕（faster-whisper turbo ~2G；SenseVoice CPU 已够快）'),
        (Verdict 6  'A' '唇形/人像驱动（MuseTalk 6G+ / LivePortrait 6G）'),
        (Verdict 8  'A' 'LatentSync 1.5 256x256 唇形（官方 8G；1.6 512 需 18G）'),
        (Verdict 10 'A' 'Real-ESRGAN 1080p 2x + RIFE 补帧（叠加约 10.8G）'),
        (Verdict 8  'A' '达芬奇 1080p 剪辑/调色（免费版单卡）'),
        (Verdict 16 'B' '达芬奇 4K 时间线（建议代理/优化媒体）'),
        (Verdict 14 'C' 'HunyuanVideo 1.5 720p 本地出片（官方 14G 起）'),
        (Verdict 24 'C' 'Wan2.2 TI2V-5B 本地出片（官方 24G 起）'),
        (Verdict 80 'D' 'Wan2.2 A14B 官方路径（80G 起）→ 走云端')
    )
    foreach ($row in $rows) {
        $parts = $row -split "`t", 2
        if ($parts.Count -eq 2) { Write-Host ('{0,-2} {1}' -f $parts[0], $parts[1]) }
    }
}
Write-Host ''
Write-Host '说明：阈值来自公开口径（官方 README / 社区实测），非本机实测。'
Write-Host '      要验证速度，跑 10s 参考音的 TTS 基准与 10s 唇形基准，记录 RTF 和显存峰值。'
Write-Host '提示：AI 模型栈建议装在 WSL2（Windows 只装显卡驱动，WSL2 内只装 CUDA toolkit），'
Write-Host '      在 WSL2 里执行 bash pc-video-capability-check.sh 可得到 Linux 侧事实。'

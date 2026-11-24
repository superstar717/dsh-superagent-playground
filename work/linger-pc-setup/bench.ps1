# bench.ps1 — 量 PolyStrata / Strata 本地模型的实际速度（OpenAI 兼容 API）
# 用法（PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\bench.ps1
#   powershell -ExecutionPolicy Bypass -File .\bench.ps1 -BaseUrl http://127.0.0.1:8080/v1 -Runs 3
# 产出：F:\AI\logs\bench-<时间>.json + 屏幕摘要
# 口径：端到端 tok/s = completion_tokens / 总耗时（含首 token 等待）；另记 prompt_tokens 与耗时。
# 注意：不追求与官方 45.5 tok/s 完全同口径，只保证同一台机、同一模型、可重复。

param(
    [string]$BaseUrl = 'http://127.0.0.1:8080/v1',
    [string]$Model = '',
    [int]$Runs = 3,
    [int]$MaxTokens = 128,
    [int]$LongPromptTokens = 8000,
    [string]$OutDir = 'F:\AI\logs'
)

$ErrorActionPreference = 'Stop'
$headers = @{ 'Content-Type' = 'application/json' }

function Invoke-Chat([string]$Prompt, [int]$MaxTok) {
    $body = @{
        model      = $Model
        messages   = @(@{ role = 'user'; content = $Prompt })
        max_tokens = $MaxTok
        stream     = $false
    } | ConvertTo-Json -Depth 6

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-RestMethod -Uri "$BaseUrl/chat/completions" -Method Post -Headers $headers -Body $body -TimeoutSec 3600
    $sw.Stop()

    $usage = $resp.usage
    $completion = if ($usage) { [int]$usage.completion_tokens } else { $null }
    $promptTok = if ($usage) { [int]$usage.prompt_tokens } else { $null }
    [ordered]@{
        elapsedSec      = [math]::Round($sw.Elapsed.TotalSeconds, 2)
        promptTokens    = $promptTok
        completionTokens = $completion
        tokPerSec       = if ($completion -and $sw.Elapsed.TotalSeconds -gt 0) { [math]::Round($completion / $sw.Elapsed.TotalSeconds, 2) } else { $null }
        preview         = ($resp.choices[0].message.content -replace '\s+', ' ').Substring(0, [Math]::Min(120, $resp.choices[0].message.content.Length))
    }
}

# 0) 状态与模型
$status = $null
try { $status = Invoke-RestMethod -Uri "$([regex]::Replace($BaseUrl,'/v1/?$',''))/v1/status" -TimeoutSec 30 } catch { }
if (-not $Model) {
    try {
        $models = Invoke-RestMethod -Uri "$BaseUrl/models" -TimeoutSec 30
        $Model = $models.data[0].id
    } catch {
        $Model = 'qwen3.8-flash-next'
    }
}
Write-Output ("[bench] base=$BaseUrl model=$Model")

$report = [ordered]@{
    at      = (Get-Date).ToString('s')
    baseUrl = $BaseUrl
    model   = $Model
    status  = $status
    short   = @()
    long    = @()
}

# 1) 短提示，重复 Runs 次（第一次含加载/预热，另记）
$shortPrompt = '用三句话解释 MoE（混合专家）模型为什么能省显存。'
for ($i = 0; $i -lt $Runs; $i++) {
    $r = Invoke-Chat $shortPrompt $MaxTokens
    $report.short += $r
    Write-Output ("[bench] short#{0} {1}s {2} tok {3} tok/s" -f ($i + 1), $r.elapsedSec, $r.completionTokens, $r.tokPerSec)
}

# 2) 长提示（约 LongPromptTokens 个 token；按 1 token ≈ 0.7 汉字粗估）
$chunk = '本地大模型把权重放在显存、内存和固态硬盘之间分层调度，冷专家按需读取，热专家常驻显存。'
$repeat = [Math]::Max(1, [int]($LongPromptTokens * 1.4 / $chunk.Length))
$longPrompt = ($chunk * $repeat) + "`n请用一句话总结上面这段的意思。"
$long = Invoke-Chat $longPrompt 64
$report.long += $long
Write-Output ("[bench] long {0}s promptTok={1} {2} tok/s" -f $long.elapsedSec, $long.promptTokens, $long.tokPerSec)

# 3) 落盘
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$out = Join-Path $OutDir ('bench-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Output ("[bench] report -> " + $out)

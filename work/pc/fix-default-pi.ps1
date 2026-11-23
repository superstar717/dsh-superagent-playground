# 2026-11-23 bench-125b: populate Pi's DEFAULT agent dir (~/.pi/agent) which Linger's gate reads
$dir = 'C:\Users\Administrator\.pi\agent'
[System.IO.File]::WriteAllText("$dir\auth.json", '{"localmodels": {"type": "api_key", "key": "sk-local-123456"}}')
$models = Get-Content 'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent\models.json' -Raw
[System.IO.File]::WriteAllText("$dir\models.json", $models)
[System.IO.File]::WriteAllText("$dir\settings.json", '{"defaultProvider": "localmodels", "defaultModel": "localmodels-byok"}')
[System.IO.File]::WriteAllText("$dir\mcp-auth.json", '{}')
icacls $dir /inheritance:r /grant:r "PC-20230915XMXX\Administrator:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
Get-ChildItem $dir | Select-Object Name,Length | Format-Table -AutoSize | Out-String -Width 60
Write-Host '=== pi default-dir run ==='
$env:PI_CODING_AGENT_DIR = $dir
$pi = 'C:\Users\Administrator\.simplexai\runtime\harness\tools\pi\1.5.2\pi.exe'
& $pi -p '用三个字回答：天空为什么是蓝色' 2>&1 | Out-String
Write-Host '=== websocket module? ==='
& E:\anaconda3\python.exe -c "import websocket; print('ws ok')" 2>&1

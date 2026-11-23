# 2026-11-23 bench-125b: run Pi non-interactively against the gateway to verify credentials/model
$env:PI_CODING_AGENT_DIR = 'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent'
$pi = 'C:\Users\Administrator\.simplexai\runtime\harness\tools\pi\1.5.2\pi.exe'
& $pi --version
Write-Host '=== probe run ==='
& $pi -p '1+1等于几？只答数字' 2>&1 | Out-String

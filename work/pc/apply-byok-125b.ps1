# 2026-11-23 bench-125b: official switch via cmd stdin redirection (PowerShell pipe mangled the JSON)
$env:PYTHONPATH = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\modules'
$py = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\python\python.exe'
cmd /c "`"$py`" -s -B -m localmodels source apply --mode byok --runtime pi --config-stdin --json < C:\Users\Administrator\byok-apply.json"
Write-Host '=== status after ==='
cmd /c "`"$py`" -s -B -m localmodels source status --json"

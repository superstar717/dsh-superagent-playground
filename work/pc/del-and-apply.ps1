# 2026-11-23 bench-125b: delete sftp-tainted state files (apply recreates them with private DACLs), then apply BYOK
Remove-Item "C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok.json" -Force
Remove-Item "C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok-home\.pi\agent\models.json" -Force
$py = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\python\python.exe'
$mods = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\modules'
$env:PYTHONPATH = $mods
cmd /c "`"$py`" -s -B -m localmodels source apply --mode byok --runtime pi --config-stdin --json < C:\Users\Administrator\byok-apply.json"
Write-Host '=== status after ==='
cmd /c "`"$py`" -s -B -m localmodels source status --json"

# 2026-11-23 bench-125b: restore private DACLs on state files overwritten via sftp, then apply BYOK
icacls "C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok.json" /inheritance:r /grant:r "Administrator:F" "SYSTEM:F" | Out-Null
icacls "C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok-home\.pi\agent\models.json" /inheritance:r /grant:r "Administrator:F" "SYSTEM:F" | Out-Null
$py = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\python\python.exe'
$mods = 'C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\modules'
$env:PYTHONPATH = $mods
& $py -c "import os;[print(p, oct(os.stat(p).st_mode & 0o777)) for p in [r'C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok.json', r'C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok-home\.pi\agent\models.json']]"
cmd /c "`"$py`" -s -B -m localmodels source apply --mode byok --runtime pi --config-stdin --json < C:\Users\Administrator\byok-apply.json"
Write-Host '=== status after ==='
cmd /c "`"$py`" -s -B -m localmodels source status --json"

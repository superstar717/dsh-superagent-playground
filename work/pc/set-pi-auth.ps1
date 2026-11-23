# 2026-11-23 bench-125b: configure the gateway API key in Pi auth.json (Linger gate wants a credential entry)
$new = 'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent\auth.json'
$old = 'C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok-home\.pi\agent\auth.json'
$json = '{"localmodels": {"type": "api_key", "key": "sk-local-123456"}}'
[System.IO.File]::WriteAllText($new, $json)
[System.IO.File]::WriteAllText($old, $json)
$py = 'E:\anaconda3\python.exe'
& $py -c "import os;[print(p, oct(os.stat(p).st_mode & 0o777)) for p in [r'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent\auth.json']]"
$env:PI_CODING_AGENT_DIR = 'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent'
$pi = 'C:\Users\Administrator\.simplexai\runtime\harness\tools\pi\1.5.2\pi.exe'
& $pi -p '1+1等于几？只答数字' 2>&1 | Out-String

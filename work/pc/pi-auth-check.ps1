$pi = 'C:\Users\Administrator\.simplexai\runtime\harness\tools\pi\1.5.2\pi.exe'
Write-Host '=== check provider localmodels ==='
& $pi auth check --provider localmodels --json 2>&1 | Out-String
Write-Host '=== check model localmodels-byok ==='
& $pi auth check --model localmodels-byok --json 2>&1 | Out-String
Write-Host '=== login (env key, non-interactive) ==='
$env:LOCALMODELS_API_KEY = 'sk-local-123456'
& $pi auth login localmodels --api-key 2>&1 | Out-String
Write-Host '=== check again ==='
& $pi auth check --provider localmodels --json 2>&1 | Out-String

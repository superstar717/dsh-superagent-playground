$pi = 'C:\Users\Administrator\.simplexai\runtime\harness\tools\pi\1.5.2\pi.exe'
& $pi auth --help 2>&1 | Out-String
Write-Host '=== status ==='
& $pi auth status 2>&1 | Out-String

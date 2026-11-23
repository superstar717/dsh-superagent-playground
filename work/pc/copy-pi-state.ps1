# 2026-11-23 bench-125b: bring Pi runtime pieces (auth/bin/mcp-auth/models-store) into the new byok-home
$old = 'C:\Users\Administrator\.simplexai\runtime\localmodels\state\byok-home\.pi\agent'
$new = 'C:\Users\Administrator\.local\state\localmodels\byok-home\.pi\agent'
foreach ($name in @('auth.json','mcp-auth.json','models-store.json')) {
  Copy-Item (Join-Path $old $name) (Join-Path $new $name) -Force
}
Copy-Item (Join-Path $old 'bin') (Join-Path $new 'bin') -Recurse -Force
icacls $new /inheritance:r /grant:r "PC-20230915XMXX\Administrator:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
Get-ChildItem $new | Select-Object Name | Format-Table -AutoSize | Out-String -Width 60

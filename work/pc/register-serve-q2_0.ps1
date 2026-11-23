# 2026-11-23 bench-125b ticket: register the Q2_0 serve task the same way as pc_serve_qwen36
# (Administrator + InteractiveToken, because the venv python has a Store-python home that breaks under SYSTEM)
$action   = New-ScheduledTaskAction -Execute 'F:\AI\logs\run-serve-q2_0.bat'
$trigger  = New-ScheduledTaskTrigger -Once -At '2026-11-24T00:00:00'
$principal = New-ScheduledTaskPrincipal -UserId 'PC-20230915XMXX\Administrator' -LogonType Interactive -RunLevel HighestAvailable
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'pc_serve_q2_0' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
Start-ScheduledTask -TaskName 'pc_serve_q2_0'

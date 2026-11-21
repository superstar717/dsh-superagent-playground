@echo off
set LOG=F:\AI\logs\q2_0-download.log
set PY=E:\anaconda3\python.exe
if not exist "%PY%" goto nopython
"%PY%" -u "C:\Users\Administrator\q2_0_download.py"
echo EXITCODE=%ERRORLEVEL% >> "%LOG%"
goto :eof
:nopython
echo %DATE% %TIME% MISSING venv python: %PY% >> "%LOG%"
exit /b 2

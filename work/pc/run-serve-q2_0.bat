@echo off
rem 2026-11-23 bench-125b ticket: serve Qwen3.8-Flash-Next Q2_0 on 127.0.0.1:8080
rem same interpreter as setup's own run-q2_0.bat (E:\anaconda3\python.exe), minus --open, plus log redirect
cd /d "F:\AI\PolyStrata\PolyStrata-main"
"E:\anaconda3\python.exe" "F:\AI\PolyStrata\PolyStrata-main\serve\server.py" --engine strata --config "F:\AI\PolyStrata\PolyStrata-main\strata-q2_0.json" --port 8080 >> F:\AI\logs\serve-q2_0.log 2>> F:\AI\logs\serve-q2_0.err.log
echo SERVE_EXIT=%ERRORLEVEL% >> F:\AI\logs\serve-q2_0.log

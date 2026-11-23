@echo off
rem 2026-11-23 bench-125b ticket: built-in benchmark against the running Q2_0 server on 8080
rem anaconda python (all stdlib deps), SYSTEM-safe; results table to log, raw JSON to q2_0-bench.json
cd /d F:\AI\PolyStrata\PolyStrata-main
"E:\anaconda3\python.exe" "F:\AI\PolyStrata\PolyStrata-main\polystrata.py" benchmark --model q2_0 --json F:\AI\logs\q2_0-bench.json > F:\AI\logs\q2_0-bench.log 2>&1
echo BENCH_EXIT=%ERRORLEVEL% >> F:\AI\logs\q2_0-bench.log

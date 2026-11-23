@echo off
rem 2026-11-23 bench-125b ticket: install/configure Qwen3.8-Flash-Next Q2_0 (66.4GB, already downloaded)
rem Engine check passed: strata-poly 0.1.45 >= MIN_ENGINE; model shards + .done on D: (NVMe)
rem 20:58 fix: direct PyPI stalled >6min under SYSTEM; use Tsinghua mirror (AGENTS.md sec.9 policy)
set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_DEFAULT_TIMEOUT=60
E:\anaconda3\python.exe F:\AI\PolyStrata\PolyStrata-main\setup.py --family qwen --model Q2_0 --context 32768 --source modelscope --data-dir D:\AI\PolyStrata-data --no-start --yes > F:\AI\logs\q2_0-setup.log 2>&1
echo SETUP_EXIT=%ERRORLEVEL% >> F:\AI\logs\q2_0-setup.log

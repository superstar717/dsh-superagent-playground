@echo off
title PolyStrata Q2_0
cd /d "F:\AI\PolyStrata\PolyStrata-main"
"E:\anaconda3\python.exe" "F:\AI\PolyStrata\PolyStrata-main\serve\server.py" "--engine" "strata" "--config" "F:\AI\PolyStrata\PolyStrata-main\strata-q2_0.json" "--port" "8080" "--open"
if errorlevel 1 pause

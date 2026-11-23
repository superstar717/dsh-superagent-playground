@echo off
rem 2026-11-23 bench-125b ticket: Bifrost gateway (Linger's model middleman) on 18480 -> PolyStrata 125B on 8080
rem same wiring the Setup wizard used on 11-21 (provider localmodels-byok base_url http://127.0.0.1:8080)
cd /d "C:\Users\Administrator\.local\share\localmodels\bifrost"
"C:\Users\Administrator\.local\share\localmodels\tools\bifrost-v2.3.0-localmodels.6\bifrost-http.exe" -app-dir "C:\Users\Administrator\.local\share\localmodels\bifrost" -port 18480 >> "C:\Users\Administrator\.local\share\localmodels\bifrost\bifrost-stdout.log" 2>&1
echo BIFROST_EXIT=%ERRORLEVEL% >> "C:\Users\Administrator\.local\share\localmodels\bifrost\bifrost-stdout.log"

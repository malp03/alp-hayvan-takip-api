@echo off
setlocal
cd /d "%~dp0"
python tools\run_smoke_tests.py
pause

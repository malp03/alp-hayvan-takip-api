@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller alp_ziraat_hayvan_takip.spec --noconfirm
powershell -ExecutionPolicy Bypass -File installer\make_installer.ps1
pause

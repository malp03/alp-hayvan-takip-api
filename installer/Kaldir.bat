@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
if errorlevel 1 (
    echo.
    echo Kaldirma islemi tamamlanamadi.
    pause
    exit /b 1
)
echo.
echo Kaldirma islemi tamamlandi.
pause

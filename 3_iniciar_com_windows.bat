@echo off
cd /d "%~dp0"
echo ================================================
echo   Orbit Spotlight - Iniciar com o Windows
echo ================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_inicializacao.ps1"
echo.
pause

@echo off
cd /d "%~dp0"
echo ============================================
echo   CtrlK - Iniciar com o Windows (prioridade)
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_inicializacao.ps1"
echo.
pause

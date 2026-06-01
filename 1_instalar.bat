@echo off
echo ===================================
echo   CtrlK Launcher — Instalando...
echo ===================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Python nao encontrado.
    echo Baixe em: https://www.python.org/downloads/
    echo Marque "Add Python to PATH" na instalacao!
    pause
    exit /b 1
)

echo Python encontrado. Instalando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install PyQt5 --quiet

echo.
echo [OK] Instalacao concluida!
echo Execute "2_executar.bat" para abrir o CtrlK.
echo.
pause

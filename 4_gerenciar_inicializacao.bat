@echo off
chcp 65001 >nul
title Gerenciar inicializacao com o Windows
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gerenciar_inicializacao.ps1"
echo.
pause

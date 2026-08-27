@echo off
chcp 65001 > nul
title Resolver Captcha e Salvar Sessao - Controle de Fluxo

echo ======================================================================
echo    🔑 LOGIN ASSISTIDO E RESOLUCAO DE CAPTCHA
echo ======================================================================
echo.

cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python login_assistido.py

echo.
pause

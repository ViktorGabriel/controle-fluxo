@echo off
chcp 65001 > nul
title Resolver Captcha e Salvar Sessao - Controle de Fluxo

echo ======================================================================
echo    🔑 LOGIN ASSISTIDO E RESOLUCAO DE CAPTCHA
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Executavel standalone
if exist "dist\ResolverCaptcha\ResolverCaptcha.exe" (
    echo [*] Abrindo via executavel standalone (.exe)...
    dist\ResolverCaptcha\ResolverCaptcha.exe
    goto :FIM
)

:: 2. Python Portatil
if exist "python_portable\python.exe" (
    python_portable\python.exe login_assistido.py
    goto :FIM
)

:: 3. Venv local
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe login_assistido.py
    goto :FIM
)

:: 4. Python do sistema
python login_assistido.py

:FIM
echo.
pause

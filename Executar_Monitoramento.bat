@echo off
chcp 65001 > nul
title Controle de Fluxo Viario - Monitoramento Automatico

echo ======================================================================
echo    🚗 CONTROLE DE FLUXO VIARIO - EXECUTAVEL DE MONITORAMENTO
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Se existir o executavel standalone compilado (.exe), executa direto sem precisar de Python
if exist "dist\ControleFluxoViario\ControleFluxoViario.exe" (
    echo [*] Executando via executavel standalone (.exe)...
    echo.
    dist\ControleFluxoViario\ControleFluxoViario.exe
    goto :FIM
)

:: 2. Se existir Python Portatil na pasta, usa o interpretador portatil
if exist "python_portable\python.exe" (
    echo [*] Executando via Python Portatil embutido...
    echo.
    python_portable\python.exe main.py
    goto :FIM
)

:: 3. Se existir ambiente virtual venv, ativa e executa
if exist "venv\Scripts\python.exe" (
    echo [*] Executando via ambiente virtual (venv)...
    echo.
    venv\Scripts\python.exe main.py
    goto :FIM
)

:: 4. Fallback: Usa o Python do sistema
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [*] Executando via Python do sistema...
    python main.py
    goto :FIM
)

echo [ERRO] Nao foi possivel encontrar o executavel nem o Python no sistema.
echo Por favor, coloque o executavel na pasta 'dist' ou instale o Python 3.10+
pause
exit /b 1

:FIM
echo.
echo ======================================================================
echo    🏁 Execucao concluida! Pressione qualquer tecla para fechar.
echo ======================================================================
pause > nul

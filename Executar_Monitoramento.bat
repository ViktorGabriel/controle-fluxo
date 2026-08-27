@echo off
chcp 65001 > nul
title Controle de Fluxo Viario - Monitoramento Automatico

echo ======================================================================
echo    🚗 CONTROLE DE FLUXO VIARIO - EXECUTAVEL DE MONITORAMENTO
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Verifica se o Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no sistema.
    echo Por favor, instale o Python 3.10+ do site python.org
    echo.
    pause
    exit /b 1
)

:: 2. Cria ambiente virtual se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo [*] Criando ambiente virtual isolado (venv)...
    python -m venv venv
    echo [*] Instalando dependencias e navegadores...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    playwright install chromium
) else (
    call venv\Scripts\activate.bat
)

echo [*] Iniciando execucao do monitoramento...
echo.
python main.py

echo.
echo ======================================================================
echo    🏁 Execucao concluida! Pressione qualquer tecla para fechar.
echo ======================================================================
pause > nul

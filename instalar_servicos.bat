@echo off
REM ============================================================
REM  ViniAI — Instalacao de servicos Windows (NSSM)
REM  Execute como Administrador
REM ============================================================
setlocal EnableDelayedExpansion

REM ── Caminhos do projeto ──────────────────────────────────────────────────────
set "RAIZ=%~dp0"
if "%RAIZ:~-1%"=="\" set "RAIZ=%RAIZ:~0,-1%"

set "FASTAPI_DIR=%RAIZ%\ai_service_base\ai_service"
set "FASTAPI_EXE=%FASTAPI_DIR%\.venv\Scripts\uvicorn.exe"

set "BACKEND_DIR=%RAIZ%\backend"
set "FRONTEND_DIR=%RAIZ%\frontAI"
set "SERVE_JS=%FRONTEND_DIR%\node_modules\serve\build\main.js"

set "LOG_DIR=%RAIZ%\logs"
set "NODE=C:\Program Files\nodejs\node.exe"

REM ── Localizar NSSM ───────────────────────────────────────────────────────────
set "NSSM=nssm"
where nssm >nul 2>&1
if errorlevel 1 (
    if exist "C:\nssm\nssm.exe" (
        set "NSSM=C:\nssm\nssm.exe"
    ) else (
        echo [ERRO] NSSM nao encontrado no PATH nem em C:\nssm\nssm.exe
        echo Baixe em https://nssm.cc/download e coloque em C:\nssm\
        pause
        exit /b 1
    )
)

REM ── Verificar Node.js ────────────────────────────────────────────────────────
if not exist "%NODE%" (
    echo [ERRO] Node.js nao encontrado em: %NODE%
    echo Verifique se o Node.js esta instalado corretamente.
    pause
    exit /b 1
)

REM ── Verificar uvicorn (.venv) ────────────────────────────────────────────────
if not exist "%FASTAPI_EXE%" (
    echo [AVISO] uvicorn nao encontrado em .venv. Criando ambiente virtual...
    pushd "%FASTAPI_DIR%"
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt --only-binary :all: --quiet
    deactivate
    popd
    echo [OK] Ambiente virtual criado.
)

REM ── Criar pasta de logs ──────────────────────────────────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo [OK] Pasta de logs: %LOG_DIR%

REM ═══════════════════════════════════════════════════════════════════════════════
echo.
echo ======================================================
echo  [1/2] Build do Backend (TypeScript ^> JavaScript)
echo ======================================================
pushd "%BACKEND_DIR%"
call npm install --silent
if errorlevel 1 (
    echo [ERRO] npm install falhou no Backend.
    popd
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo [ERRO] npm run build falhou no Backend.
    popd
    pause
    exit /b 1
)
popd
echo [OK] Backend compilado.

REM ═══════════════════════════════════════════════════════════════════════════════
echo.
echo ======================================================
echo  [2/2] Build do Frontend (Vite)
echo ======================================================
pushd "%FRONTEND_DIR%"
call npm install --silent
if errorlevel 1 (
    echo [ERRO] npm install falhou no Frontend.
    popd
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo [ERRO] npm run build falhou no Frontend.
    popd
    pause
    exit /b 1
)
popd
echo [OK] Frontend compilado.

REM ═══════════════════════════════════════════════════════════════════════════════
echo.
echo ======================================================
echo  Configurando servicos NSSM
echo ======================================================

REM ── Remover servicos existentes ──────────────────────────────────────────────
for %%S in (ViniAI-FastAPI ViniAI-Backend ViniAI-Frontend) do (
    sc query %%S >nul 2>&1
    if not errorlevel 1 (
        echo Removendo servico existente: %%S
        "%NSSM%" stop %%S confirm >nul 2>&1
        timeout /t 2 /nobreak >nul
        "%NSSM%" remove %%S confirm >nul 2>&1
    )
)

REM ── Servico 1: ViniAI-FastAPI (Python/uvicorn — porta 8000) ─────────────────
echo.
echo Criando ViniAI-FastAPI...
"%NSSM%" install ViniAI-FastAPI "%FASTAPI_EXE%"
"%NSSM%" set ViniAI-FastAPI AppParameters "app.main:app --host 0.0.0.0 --port 8000"
"%NSSM%" set ViniAI-FastAPI AppDirectory "%FASTAPI_DIR%"
"%NSSM%" set ViniAI-FastAPI DisplayName "ViniAI FastAPI"
"%NSSM%" set ViniAI-FastAPI Description "IA de consulta de producao fabril - porta 8000"
"%NSSM%" set ViniAI-FastAPI Start SERVICE_AUTO_START
"%NSSM%" set ViniAI-FastAPI AppStdout "%LOG_DIR%\fastapi_stdout.log"
"%NSSM%" set ViniAI-FastAPI AppStderr "%LOG_DIR%\fastapi_stderr.log"
"%NSSM%" set ViniAI-FastAPI AppRotateFiles 1
"%NSSM%" set ViniAI-FastAPI AppRotateBytes 5242880
"%NSSM%" set ViniAI-FastAPI AppRestartDelay 3000
echo [OK] ViniAI-FastAPI criado.

REM ── Servico 2: ViniAI-Backend (Node.js — porta 4000) ────────────────────────
echo.
echo Criando ViniAI-Backend...
"%NSSM%" install ViniAI-Backend "%NODE%"
"%NSSM%" set ViniAI-Backend AppParameters "dist\server.js"
"%NSSM%" set ViniAI-Backend AppDirectory "%BACKEND_DIR%"
"%NSSM%" set ViniAI-Backend DisplayName "ViniAI Backend"
"%NSSM%" set ViniAI-Backend Description "Servico de autenticacao ViniAI - porta 4000"
"%NSSM%" set ViniAI-Backend Start SERVICE_AUTO_START
"%NSSM%" set ViniAI-Backend AppStdout "%LOG_DIR%\backend_stdout.log"
"%NSSM%" set ViniAI-Backend AppStderr "%LOG_DIR%\backend_stderr.log"
"%NSSM%" set ViniAI-Backend AppRotateFiles 1
"%NSSM%" set ViniAI-Backend AppRotateBytes 5242880
"%NSSM%" set ViniAI-Backend AppRestartDelay 3000
echo [OK] ViniAI-Backend criado.

REM ── Servico 3: ViniAI-Frontend (serve estatico — porta 3003) ─────────────────
echo.
echo Criando ViniAI-Frontend...
"%NSSM%" install ViniAI-Frontend "%NODE%"
"%NSSM%" set ViniAI-Frontend AppParameters "\"%SERVE_JS%\" -s dist -l 3003"
"%NSSM%" set ViniAI-Frontend AppDirectory "%FRONTEND_DIR%"
"%NSSM%" set ViniAI-Frontend DisplayName "ViniAI Frontend"
"%NSSM%" set ViniAI-Frontend Description "Frontend ViniAI - porta 3003"
"%NSSM%" set ViniAI-Frontend Start SERVICE_AUTO_START
"%NSSM%" set ViniAI-Frontend AppStdout "%LOG_DIR%\frontend_stdout.log"
"%NSSM%" set ViniAI-Frontend AppStderr "%LOG_DIR%\frontend_stderr.log"
"%NSSM%" set ViniAI-Frontend AppRotateFiles 1
"%NSSM%" set ViniAI-Frontend AppRotateBytes 5242880
"%NSSM%" set ViniAI-Frontend AppRestartDelay 3000
echo [OK] ViniAI-Frontend criado.

REM ═══════════════════════════════════════════════════════════════════════════════
echo.
echo ======================================================
echo  Iniciando servicos...
echo ======================================================
"%NSSM%" start ViniAI-FastAPI
"%NSSM%" start ViniAI-Backend
"%NSSM%" start ViniAI-Frontend

timeout /t 5 /nobreak >nul

REM ── Status final ─────────────────────────────────────────────────────────────
echo.
echo ======================================================
echo  Status dos servicos
echo ======================================================
"%NSSM%" status ViniAI-FastAPI
"%NSSM%" status ViniAI-Backend
"%NSSM%" status ViniAI-Frontend

echo.
echo ======================================================
echo  Portas em uso (deve aparecer 8000, 4000 e 3003)
echo ======================================================
netstat -ano | findstr "8000\|4000\|3003"

echo.
echo ======================================================
echo  Instalacao concluida!
echo ======================================================
echo.
echo Comandos uteis:
echo   nssm status  ViniAI-FastAPI
echo   nssm start   ViniAI-FastAPI
echo   nssm stop    ViniAI-FastAPI
echo   nssm restart ViniAI-FastAPI
echo   nssm remove  ViniAI-FastAPI confirm
echo.
echo Substituir FastAPI por Backend ou Frontend conforme necessario.
echo Logs em: %LOG_DIR%
echo.
pause

@echo off
REM ============================================================
REM  ViniAI — Servico FastAPI (NSSM)
REM  Execute como Administrador
REM ============================================================
setlocal

set "FASTAPI_DIR=C:\Users\Martins\Documents\ViniAi\ai_service_base\ai_service"
set "UVICORN=%FASTAPI_DIR%\.venv\Scripts\uvicorn.exe"
set "LOG_DIR=C:\Users\Martins\Documents\ViniAi\logs"

REM ── Verificar NSSM ───────────────────────────────────────────────────────────
set "NSSM=nssm"
where nssm >nul 2>&1
if errorlevel 1 (
    if exist "C:\metabase\nssm\nssm.exe" (
        set "NSSM=C:\metabase\nssm\nssm.exe"
    ) else (
        echo [ERRO] NSSM nao encontrado. Coloque o nssm.exe em C:\nssm\ ou no PATH.
        pause
        exit /b 1
    )
)

REM ── Verificar uvicorn no .venv ───────────────────────────────────────────────
if not exist "%UVICORN%" (
    echo [ERRO] uvicorn nao encontrado em: %UVICORN%
    echo Execute primeiro: cd ai_service_base\ai_service ^&^& iniciar.bat
    pause
    exit /b 1
)

REM ── Criar pasta de logs ──────────────────────────────────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM ── Remover servico anterior se existir ──────────────────────────────────────
sc query ViniAI-FastAPI >nul 2>&1
if not errorlevel 1 (
    echo Removendo servico existente...
    "%NSSM%" stop ViniAI-FastAPI confirm >nul 2>&1
    timeout /t 2 /nobreak >nul
    "%NSSM%" remove ViniAI-FastAPI confirm
)

REM ── Criar servico ────────────────────────────────────────────────────────────
echo.
echo Criando ViniAI-FastAPI...
"%NSSM%" install ViniAI-FastAPI "%UVICORN%"
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

REM ── Iniciar ──────────────────────────────────────────────────────────────────
echo.
echo Iniciando servico...
"%NSSM%" start ViniAI-FastAPI

timeout /t 4 /nobreak >nul

REM ── Verificar ────────────────────────────────────────────────────────────────
echo.
echo === Status ===
"%NSSM%" status ViniAI-FastAPI

echo.
echo === Porta 8000 ===
netstat -ano | findstr "8000"

echo.
echo Logs: %LOG_DIR%\fastapi_stdout.log
echo.
echo Comandos uteis:
echo   nssm stop    ViniAI-FastAPI
echo   nssm start   ViniAI-FastAPI
echo   nssm restart ViniAI-FastAPI
echo   nssm remove  ViniAI-FastAPI confirm
echo.
pause

@echo off
title PrintSight Dev Starter

echo =============================================
echo  PrintSight - Starting Dev Servers
echo =============================================

:: ── Step 1: Start PostgreSQL ──────────────────
echo [1/4] Starting PostgreSQL service...
sc query postgresql-x64-18 | findstr /i "RUNNING" >nul 2>&1
if %errorlevel% == 0 (
    echo        PostgreSQL already running.
) else (
    net start postgresql-x64-18 >nul 2>&1
    if %errorlevel% == 0 (
        echo        PostgreSQL started.
    ) else (
        echo [!] Could not start PostgreSQL. Run as Administrator or start it manually.
        pause
        exit /b 1
    )
)

:: ── Step 2: Kill anything on port 8001 ────────
echo [2/4] Freeing port 8001...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8001 "') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ── Step 3: Start Backend ─────────────────────
echo [3/4] Starting Backend  (http://localhost:8001) ...
start "PrintSight Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port 8001"

:: Wait up to 10s for backend to be ready
echo        Waiting for backend to be ready...
set TRIES=0
:WAIT_LOOP
timeout /t 2 /nobreak >nul
curl -s http://localhost:8001/health >nul 2>&1
if %errorlevel% == 0 goto BACKEND_READY
set /a TRIES+=1
if %TRIES% LSS 5 goto WAIT_LOOP
echo [!] Backend did not start in time - check the Backend window for errors.
goto START_FRONTEND

:BACKEND_READY
echo        Backend is up!

:: ── Step 4: Start Frontend ────────────────────
:START_FRONTEND
echo [4/4] Starting Frontend (http://localhost:5173) ...
start "PrintSight Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo =============================================
echo  Services started:
echo    PostgreSQL -> localhost:5432
echo    Backend    -> http://localhost:8001
echo    API Docs   -> http://localhost:8001/docs
echo    Frontend   -> http://localhost:5173
echo =============================================
echo.
echo Press any key to close this launcher...
pause >nul

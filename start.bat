@echo off
title PrintSight Dev Starter

echo =============================================
echo  PrintSight - Starting Dev Servers
echo =============================================

:: ── Step 1: Verify database connectivity ──────
echo [1/3] Checking database connection...
python -c "import psycopg2; psycopg2.connect(host='69.62.84.73', port=5432, user='postgres', password='G8umzPMoCWIQDoTKGAy4hXdDE1GS0XafmAt4SJ57YjnwDnaXON9QDr17RrjoktL3', dbname='printsight'); print('Database connected.')" >nul 2>&1
if %errorlevel% == 0 (
    echo        Cloud database reachable.
) else (
    echo [!] Cannot reach cloud database. Check your network connection.
    pause
    exit /b 1
)

:: ── Step 2: Kill anything on port 8001 ────────
echo [2/3] Freeing port 8001...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8001 "') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ── Step 3: Start Backend ─────────────────────
echo [3/3] Starting Backend  (http://localhost:8001) ...
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
echo    PostgreSQL -> 69.62.84.73:5432/printsight
echo    Backend    -> http://localhost:8001
echo    API Docs   -> http://localhost:8001/docs
echo    Frontend   -> http://localhost:5173
echo =============================================
echo.
echo Press any key to close this launcher...
pause >nul

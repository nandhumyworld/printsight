@echo off
title PrintSight Docker Deploy (Dev)

echo =============================================
echo  PrintSight - Docker Redeploy (Dev)
echo =============================================

:: ── Step 1: Verify Docker is running ───────────
echo [1/4] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker is not running. Start Docker Desktop and try again.
    pause
    exit /b 1
)
echo        Docker is running.

:: ── Step 2: Verify database connectivity ───────
echo [2/4] Checking database connection...
python -c "import psycopg2; psycopg2.connect(host='69.62.84.73', port=5432, user='postgres', password='G8umzPMoCWIQDoTKGAy4hXdDE1GS0XafmAt4SJ57YjnwDnaXON9QDr17RrjoktL3', dbname='printsight'); print('ok')" >nul 2>&1
if %errorlevel% == 0 (
    echo        Cloud database reachable.
) else (
    echo [!] Cannot reach cloud database. Check your network connection.
    pause
    exit /b 1
)

:: ── Step 3: Build images ────────────────────────
echo [3/4] Building Docker images (this may take a minute)...
cd /d "%~dp0"
docker compose -f docker-compose.dev.yml build --no-cache
if %errorlevel% neq 0 (
    echo [!] Docker build failed. Check the output above.
    pause
    exit /b 1
)
echo        Build complete.

:: ── Step 4: Start containers ────────────────────
echo [4/4] Starting containers...
docker compose -f docker-compose.dev.yml up -d
if %errorlevel% neq 0 (
    echo [!] Failed to start containers. Check the output above.
    pause
    exit /b 1
)

:: Wait for backend health check
echo        Waiting for backend to be ready...
set TRIES=0
:WAIT_LOOP
timeout /t 3 /nobreak >nul
curl -s http://localhost:8001/health >nul 2>&1
if %errorlevel% == 0 goto READY
set /a TRIES+=1
if %TRIES% LSS 10 goto WAIT_LOOP
echo [!] Backend did not respond in time. Run: docker compose -f docker-compose.dev.yml logs backend
goto DONE

:READY
echo        Backend is up!

:DONE
echo.
echo =============================================
echo  Dev deployment complete:
echo    PostgreSQL -> 69.62.84.73:5432/printsight
echo    Backend    -> http://localhost:8001
echo    API Docs   -> http://localhost:8001/docs
echo    Frontend   -> http://localhost:5173
echo =============================================
echo.
echo  Useful commands:
echo    docker compose -f docker-compose.dev.yml logs -f backend
echo    docker compose -f docker-compose.dev.yml logs -f frontend
echo    docker compose -f docker-compose.dev.yml ps
echo.
echo Press any key to close...
pause >nul

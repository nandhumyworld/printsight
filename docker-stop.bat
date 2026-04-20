@echo off
title PrintSight Docker Stop (Dev)

echo =============================================
echo  PrintSight - Docker Stop (Dev)
echo =============================================

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker is not running. Nothing to stop.
    pause
    exit /b 0
)

cd /d "%~dp0"

echo.
echo  [1] Stop containers (keeps images + data)
echo  [2] Stop and remove containers
echo  [3] Full clean (stop + remove containers, images, volumes)
echo.
set /p MODE="Choose option (1/2/3): "

if "%MODE%"=="1" goto STOP_ONLY
if "%MODE%"=="2" goto STOP_DOWN
if "%MODE%"=="3" goto FULL_CLEAN

echo [!] Invalid option. Defaulting to stop only.

:STOP_ONLY
echo.
echo Stopping containers...
docker compose -f docker-compose.dev.yml stop
echo Done. Containers stopped (data preserved).
goto END

:STOP_DOWN
echo.
echo Stopping and removing containers...
docker compose -f docker-compose.dev.yml down
echo Done. Containers removed (volumes preserved).
goto END

:FULL_CLEAN
echo.
echo [!] This will delete all containers, images, and volumes for this project.
set /p CONFIRM="Are you sure? (yes/N): "
if /i not "%CONFIRM%"=="yes" (
    echo Cancelled.
    goto END
)
docker compose -f docker-compose.dev.yml down --volumes --rmi all
echo Done. Full clean complete.

:END
echo.
echo =============================================
echo  Containers status:
docker compose -f docker-compose.dev.yml ps 2>nul
echo =============================================
echo.
echo Press any key to close...
pause >nul

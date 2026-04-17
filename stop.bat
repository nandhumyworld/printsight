@echo off
title PrintSight Dev Stopper

echo Stopping PrintSight dev servers...

:: Kill uvicorn directly
taskkill /F /IM "uvicorn.exe" >nul 2>&1

:: Kill python processes running uvicorn (venv case)
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /i "PID"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr /i "uvicorn" >nul 2>&1
    if not errorlevel 1 (
        taskkill /F /PID %%a >nul 2>&1
        echo   Killed backend process %%a
    )
)

:: Kill node/vite (frontend)
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq node.exe" /fo list 2^>nul ^| findstr /i "PID"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr /i "vite" >nul 2>&1
    if not errorlevel 1 (
        taskkill /F /PID %%a >nul 2>&1
        echo   Killed frontend process %%a
    )
)

echo   Backend and Frontend stopped.
echo.

:: Ask whether to also stop PostgreSQL
set /p STOP_PG="Stop PostgreSQL service too? (y/N): "
if /i "%STOP_PG%"=="y" (
    net stop postgresql-x64-18 >nul 2>&1
    echo   PostgreSQL stopped.
) else (
    echo   PostgreSQL left running.
)

echo Done.
timeout /t 2 /nobreak >nul

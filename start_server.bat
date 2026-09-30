@echo off
cd /d "%~dp0"
title PDF Auto Rename Web Service

if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo ========================================================
echo  Starting PDF Auto Rename Web Service
echo  Access via: http://localhost:8000
echo ========================================================
echo.

:: Automatically open default browser after a brief delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

"%PY%" -m uvicorn app:app --host 0.0.0.0 --port 8000
pause

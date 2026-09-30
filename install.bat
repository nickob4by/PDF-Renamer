@echo off
setlocal EnableDelayedExpansion
title PDF Auto Rename - Requirements Installer

cd /d "%~dp0"

echo ===================================================================
echo               PDF AUTO RENAME - REQUIREMENTS INSTALLER
echo                       for DASURECO Web Service
echo ===================================================================
echo.

REM -------------------------------------------------------------------
REM 1. Check Python
REM -------------------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    where py >nul 2>&1
    if %errorlevel% equ 0 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD goto :no_python

echo [OK] Python found:
%PYTHON_CMD% --version
echo.
goto :check_vcredist

:no_python
echo [ERROR] Python was not found in your system PATH.
echo.
echo Please install Python 3.10 - 3.12 [64-bit] from:
echo   https://www.python.org/downloads/
echo.
echo IMPORTANT: Check the box "Add Python to PATH" during installation.
echo.
where winget >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Attempting automated installation via Windows winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo If Python was just installed, please close and reopen this installer.
)
pause
exit /b 1

REM -------------------------------------------------------------------
REM 2. Check Visual C++ Redistributable (x64)
REM -------------------------------------------------------------------
:check_vcredist
echo [CHECK] Checking for Microsoft Visual C++ 2015-2022 Redistributable [x64]...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Installed >nul 2>&1
if %errorlevel% equ 0 goto :vcredist_ok

echo [INFO] Visual C++ Redistributable [x64] not detected.
echo Downloading and installing Microsoft Visual C++ Redistributable...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://aka.ms/vs/17/release/vc_redist.x64.exe', 'vc_redist.x64.exe')"
if exist "vc_redist.x64.exe" (
    echo Installing Visual C++ Redistributable...
    start /wait vc_redist.x64.exe /install /passive /norestart
    del /f /q vc_redist.x64.exe >nul 2>&1
    echo [OK] Visual C++ Redistributable installed.
) else (
    echo [WARNING] Could not automatically download vc_redist.x64.exe.
    echo Please install it manually from: https://aka.ms/vs/17/release/vc_redist.x64.exe
)
goto :setup_venv

:vcredist_ok
echo [OK] Visual C++ Redistributable [x64] is already installed.
echo.

REM -------------------------------------------------------------------
REM 3. Setup Virtual Environment (venv)
REM -------------------------------------------------------------------
:setup_venv
if exist "venv\Scripts\python.exe" goto :venv_exists

echo [SETUP] Creating Python virtual environment in .\venv...
%PYTHON_CMD% -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment created.
echo.
goto :install_reqs

:venv_exists
echo [OK] Existing virtual environment found in .\venv.
echo.

REM -------------------------------------------------------------------
REM 4. Upgrade pip and install requirements
REM -------------------------------------------------------------------
:install_reqs
echo [SETUP] Upgrading pip, setuptools, and wheel...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
echo.

echo [SETUP] Installing dependencies from requirements.txt...
echo This may take a few minutes [downloading PaddleOCR, PyMuPDF, FastAPI, etc.]...
venv\Scripts\pip.exe install --no-cache-dir -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo.
echo [OK] All dependencies installed successfully!
echo.

REM -------------------------------------------------------------------
REM 5. Pre-warm PaddleOCR Model Cache
REM -------------------------------------------------------------------
echo [SETUP] Pre-downloading OCR model files [one-time setup]...
venv\Scripts\python.exe -c "from paddleocr import PaddleOCR; print('Initializing OCR model cache...'); PaddleOCR(lang='en', show_log=False)"
echo [OK] OCR models are cached and ready.
echo.

REM -------------------------------------------------------------------
REM 6. Verification
REM -------------------------------------------------------------------
echo [CHECK] Verifying installation...
venv\Scripts\python.exe -c "import fastapi, uvicorn, fitz, rapidfuzz, openpyxl, paddleocr; print('Verification passed: All core modules loaded successfully!')"
echo.

echo ===================================================================
echo                      INSTALLATION COMPLETE!
echo ===================================================================
echo.
echo You can now start the web application anytime by running:
echo     start_server.bat
echo.
echo Or by double-clicking 'start_server.bat' in this folder.
echo The app will open at: http://localhost:8000
echo ===================================================================
echo.

set /p "START_NOW=Do you want to start the web app now? (Y/N): "
if /i "!START_NOW!"=="Y" (
    echo.
    echo Starting server...
    start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
    venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
)

pause

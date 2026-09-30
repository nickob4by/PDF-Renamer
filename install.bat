@echo off
setlocal enabledelayedexpansion
title PDF Auto Rename - Requirements Installer

cd /d "%~dp0"

echo ===================================================================
echo               PDF AUTO RENAME - REQUIREMENTS INSTALLER
echo                       for DASURECO Web Service
echo ===================================================================
echo.

:: -------------------------------------------------------------------
:: 1. Check Python
:: -------------------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found in your system PATH.
    echo.
    echo Please install Python 3.10 - 3.12 (64-bit) from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check "Add Python to PATH" during setup.
    echo.
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Attempting to install Python via Windows winget...
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        echo.
        echo Please restart this installer after Python installation completes.
    )
    pause
    exit /b 1
)

echo [OK] Python found:
%PYTHON_CMD% --version
echo.

:: -------------------------------------------------------------------
:: 2. Check Visual C++ Redistributable (x64)
:: -------------------------------------------------------------------
echo [CHECK] Checking for Microsoft Visual C++ 2015-2022 Redistributable (x64)...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Installed >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Visual C++ Redistributable (x64) not detected.
    echo Downloading and installing Microsoft Visual C++ Redistributable...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://aka.ms/vs/17/release/vc_redist.x64.exe', 'vc_redist.x64.exe')"
    if exist "vc_redist.x64.exe" (
        echo Installing Visual C++ Redistributable...
        start /wait vc_redist.x64.exe /install /passive /norestart
        del /f /q vc_redist.x64.exe >nul 2>&1
        echo [OK] Visual C++ Redistributable installed.
    ) else (
        echo [WARNING] Could not automatically download vc_redist.x64.exe.
        echo Please manually install it from: https://aka.ms/vs/17/release/vc_redist.x64.exe
    )
) else (
    echo [OK] Visual C++ Redistributable (x64) is already installed.
)
echo.

:: -------------------------------------------------------------------
:: 3. Setup Virtual Environment (venv)
:: -------------------------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment in .\venv...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Existing virtual environment found in .\venv.
)
echo.

:: -------------------------------------------------------------------
:: 4. Upgrade pip and install requirements
:: -------------------------------------------------------------------
echo [SETUP] Upgrading pip, setuptools, and wheel...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
echo.

echo [SETUP] Installing dependencies from requirements.txt...
echo This may take a few minutes (downloading PaddleOCR, PyMuPDF, FastAPI, etc.)...
venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo.
echo [OK] All dependencies installed successfully!
echo.

:: -------------------------------------------------------------------
:: 5. Pre-warm PaddleOCR Model Cache
:: -------------------------------------------------------------------
echo [SETUP] Pre-downloading OCR model files (one-time setup)...
venv\Scripts\python.exe -c "from paddleocr import PaddleOCR; print('Initializing OCR model cache...'); PaddleOCR(lang='en', show_log=False)"
echo [OK] OCR models are cached and ready.
echo.

:: -------------------------------------------------------------------
:: 6. Verification
:: -------------------------------------------------------------------
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

set /p START_NOW="Do you want to start the web app now? (Y/N): "
if /i "!START_NOW!"=="Y" (
    echo.
    echo Starting server...
    start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
    venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
)

pause

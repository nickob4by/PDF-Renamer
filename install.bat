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

REM Check default user installation path
if not defined PYTHON_CMD (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
    )
)

if not defined PYTHON_CMD (
    if exist "C:\Python312\python.exe" (
        set "PYTHON_CMD=C:\Python312\python.exe"
        set "PATH=C:\Python312;C:\Python312\Scripts;!PATH!"
    )
)

if defined PYTHON_CMD goto :python_ready

:install_python
echo [INFO] Python was not detected on this system.
echo [SETUP] Automatically downloading official Python 3.12 [64-bit]...
set "PY_INSTALLER=python_installer.exe"

REM Download via curl or powershell
curl.exe -L -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe" 2>nul
if not exist "%PY_INSTALLER%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe', 'python_installer.exe')"
)

if not exist "%PY_INSTALLER%" (
    echo [ERROR] Failed to download Python installer.
    echo Please manually download and install Python 3.12 from:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [SETUP] Installing Python 3.12 quietly...
start /wait %PY_INSTALLER% /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 SimpleInstall=1
del /f /q %PY_INSTALLER% >nul 2>&1

REM Refresh PATH in current session
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [WARNING] Python installation finished, but python.exe was not detected immediately.
    echo Please restart install.bat to continue setup.
    pause
    exit /b 1
)

echo [OK] Python 3.12 installed successfully!
echo.

:python_ready
echo [OK] Python found:
%PYTHON_CMD% --version
echo.
goto :check_vcredist

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

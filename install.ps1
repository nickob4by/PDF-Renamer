<#
.SYNOPSIS
    Automated Requirements Installer for PDF Auto Rename (DASURECO)
.DESCRIPTION
    Checks Python version, installs Visual C++ Redistributable (if missing),
    creates Python venv, installs requirements.txt, and pre-downloads OCR models.
#>

$ErrorActionPreference = "Stop"

Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "              PDF AUTO RENAME - REQUIREMENTS INSTALLER             " -ForegroundColor Cyan
Write-Host "                      for DASURECO Web Service                     " -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
$pyCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = "py"
}

if (-not $pyCmd) {
    Write-Host "[ERROR] Python was not found in your system PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10 - 3.12 (64-bit) from: https://www.python.org/downloads/"
    Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    exit 1
}

$pyVer = & $pyCmd --version
Write-Host "[OK] Python found: $pyVer" -ForegroundColor Green
Write-Host ""

# 2. Check Visual C++ Redistributable (x64)
Write-Host "[CHECK] Checking for Microsoft Visual C++ 2015-2022 Redistributable (x64)..." -ForegroundColor Yellow
$vcKey = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
$vcInstalled = $false

if (Test-Path $vcKey) {
    $val = (Get-ItemProperty -Path $vcKey -Name "Installed" -ErrorAction SilentlyContinue).Installed
    if ($val -eq 1) { $vcInstalled = $true }
}

if (-not $vcInstalled) {
    Write-Host "[INFO] Downloading Microsoft Visual C++ Redistributable..." -ForegroundColor Yellow
    $installerUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    $installerPath = Join-Path $PSScriptRoot "vc_redist.x64.exe"
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Host "[SETUP] Running Visual C++ installer..." -ForegroundColor Yellow
    Start-Process -FilePath $installerPath -ArgumentList "/install /passive /norestart" -Wait
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Visual C++ Redistributable installed." -ForegroundColor Green
} else {
    Write-Host "[OK] Visual C++ Redistributable (x64) is already installed." -ForegroundColor Green
}
Write-Host ""

# 3. Setup Virtual Environment (venv)
$venvDir = Join-Path $PSScriptRoot "venv"
$venvPy = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "[SETUP] Creating Python virtual environment in .\venv..." -ForegroundColor Yellow
    & $pyCmd -m venv $venvDir
    Write-Host "[OK] Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "[OK] Existing virtual environment found in .\venv." -ForegroundColor Green
}
Write-Host ""

# 4. Upgrade pip and install requirements
Write-Host "[SETUP] Upgrading pip, setuptools, and wheel..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip setuptools wheel

Write-Host "[SETUP] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host "This may take a few minutes (downloading PaddleOCR, PyMuPDF, FastAPI, etc.)..."
$reqFile = Join-Path $PSScriptRoot "requirements.txt"
& $venvPy -m pip install -r $reqFile
Write-Host "[OK] All dependencies installed successfully!" -ForegroundColor Green
Write-Host ""

# 5. Pre-warm PaddleOCR Model
Write-Host "[SETUP] Pre-downloading OCR model files (one-time setup)..." -ForegroundColor Yellow
& $venvPy -c "from paddleocr import PaddleOCR; print('Initializing OCR model cache...'); PaddleOCR(lang='en', show_log=False)"
Write-Host "[OK] OCR models are cached and ready." -ForegroundColor Green
Write-Host ""

# 6. Verification
Write-Host "[CHECK] Verifying installation..." -ForegroundColor Yellow
& $venvPy -c "import fastapi, uvicorn, fitz, rapidfuzz, openpyxl, paddleocr; print('Verification passed: All core modules loaded successfully!')"
Write-Host ""

Write-Host "===================================================================" -ForegroundColor Green
Write-Host "                      INSTALLATION COMPLETE!                       " -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "Start the application anytime with: .\start_server.bat"
Write-Host "App URL: http://localhost:8000"
Write-Host ""

# Fix "ModuleNotFoundError: No module named 'zk'" on Windows
# Run with: PowerShell -ExecutionPolicy Bypass -File fix_zk_module.ps1

Write-Host "=====================================" -ForegroundColor Green
Write-Host "    ZKTeco 'zk' Module Fix Script" -ForegroundColor Green  
Write-Host "=====================================" -ForegroundColor Green

# Navigate to backend directory
Set-Location $PSScriptRoot
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Yellow

# Check if venv exists
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Check Git installation
Write-Host "Checking Git installation..." -ForegroundColor Yellow
git --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Git not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id Git.Git -e --source winget
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Please install Git manually from https://git-scm.com/" -ForegroundColor Red
        exit 1
    }
}

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install pyzk from GitHub
Write-Host "Installing pyzk from GitHub..." -ForegroundColor Yellow
pip install git+https://github.com/zeidanbm/pyzk.git@9cd5731543e3839a94962403c7ad7a5e9c872bac
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub install failed, trying PyPI version..." -ForegroundColor Yellow
    pip install pyzk
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install pyzk" -ForegroundColor Red
        exit 1
    }
}

# Test zk module import
Write-Host "Testing zk module import..." -ForegroundColor Yellow
python -c "from zk import ZK; print('[OK] zk module imported successfully')"
if ($LASTEXITCODE -eq 0) {
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "    SUCCESS: zk module fixed!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "You can now run: build_backend.bat" -ForegroundColor Yellow
} else {
    Write-Host "ERROR: zk module still cannot be imported" -ForegroundColor Red
    Write-Host "Try manual installation:" -ForegroundColor Yellow
    Write-Host "1. pip install pyzk" -ForegroundColor Yellow
    Write-Host "2. pip install git+https://github.com/fananimi/pyzk.git" -ForegroundColor Yellow
    exit 1
}

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
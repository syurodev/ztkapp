# ==============================================================
# ZKTeco Desktop - Complete Build Script (PowerShell)
# Usage: PowerShell -ExecutionPolicy Bypass -File build-all.ps1
# ==============================================================

param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$Verbose
)

# Set error handling
$ErrorActionPreference = "Stop"

# Get project root
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PROJECT_ROOT

Write-Host "======================================" -ForegroundColor Green
Write-Host " ZKTeco Desktop - Full Build Script" -ForegroundColor Green  
Write-Host "======================================" -ForegroundColor Green
Write-Host "Project root: $PROJECT_ROOT" -ForegroundColor Blue
Write-Host ""

# Function to log with colors
function Write-Log {
    param($Message, $Color = "White")
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
}

function Write-Success {
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# Check system requirements
Write-Log "Checking system requirements..." "Cyan"

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error-Custom "Python 3 is required but not installed"
}
$pythonVersion = (python --version).Split(' ')[1]
Write-Log "Found Python $pythonVersion" "Blue"

# Check Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error-Custom "Node.js is required but not installed"
}
$nodeVersion = node --version
Write-Log "Found Node.js $nodeVersion" "Blue"

# Check package manager (prefer bun)
$pkgManager = "npm"
if (Get-Command bun -ErrorAction SilentlyContinue) {
    $pkgManager = "bun"
    Write-Log "Using bun package manager" "Blue"
} else {
    Write-Warning "bun not found, using npm as package manager"
}

# Check Rust/Cargo for Tauri
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Error-Custom "Rust/Cargo is required for Tauri. Install from https://rustup.rs/"
}
$rustVersion = (rustc --version).Split(' ')[1]
Write-Log "Found Rust $rustVersion" "Blue"

Write-Host ""

# ===================
# Backend Build
# ===================
if (-not $SkipBackend) {
    Write-Log "Building Backend..." "Cyan"
    Set-Location "$PROJECT_ROOT\backend"

    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "venv")) {
        Write-Log "Creating Python virtual environment..." "Yellow"
        python -m venv venv
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to create virtual environment"
        }
    }

    # Activate virtual environment
    Write-Log "Activating virtual environment..." "Yellow"
    & "venv\Scripts\Activate.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to activate virtual environment"
    }

    # Upgrade pip
    Write-Log "Upgrading pip..." "Yellow"
    python -m pip install --upgrade pip

    # Check Git for pyzk installation
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Warning "Git not found. Installing via winget..."
        try {
            winget install --id Git.Git -e --source winget
        } catch {
            Write-Warning "Failed to install Git via winget. Please install manually from https://git-scm.com/"
        }
    }

    # Install pyzk separately first
    Write-Log "Installing pyzk dependency..." "Yellow"
    try {
        pip install git+https://github.com/zeidanbm/pyzk.git@9cd5731543e3839a94962403c7ad7a5e9c872bac
        Write-Success "pyzk installed from GitHub"
    } catch {
        Write-Warning "GitHub install failed, trying PyPI fallback..."
        pip install pyzk
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install pyzk"
        }
    }

    # Install remaining dependencies
    Write-Log "Installing Python dependencies..." "Yellow"
    if (Test-Path "requirements-windows.txt") {
        Write-Log "Using Windows-specific requirements..." "Blue"
        pip install -r requirements-windows.txt
    } else {
        Write-Log "Using default requirements..." "Blue"
        pip install -r requirements.txt
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to install Python dependencies"
    }

    # Verify zk module can be imported
    Write-Log "Verifying zk module installation..." "Yellow"
    python -c "from zk import ZK; print('✓ zk module imported successfully')"
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "zk module cannot be imported"
    }

    # Clean previous builds
    Write-Log "Cleaning previous backend builds..." "Yellow"
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

    # Build with PyInstaller
    Write-Log "Building backend executable..." "Yellow"
    if (Test-Path "zkteco-backend.spec") {
        Write-Log "Using existing spec file..." "Blue"
        pyinstaller --clean --noconfirm zkteco-backend.spec
    } else {
        Write-Log "Creating new spec file..." "Blue"
        pyinstaller --name "zkteco-backend" --onefile --console --noconfirm `
                    --hidden-import=zkteco.config.settings `
                    --hidden-import=zkteco.config.config_manager_sqlite `
                    --hidden-import=zkteco.database.models `
                    --hidden-import=zkteco.services `
                    --hidden-import=zkteco.controllers `
                    --hidden-import=sqlite3 `
                    --hidden-import=flask_cors `
                    --add-data="zkteco;zkteco" `
                    service_app.py
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Backend build failed"
    }

    # Verify executable was created
    if (-not (Test-Path "dist\zkteco-backend.exe")) {
        Write-Error-Custom "Backend build failed - executable not found"
    }

    $fileSize = [math]::Round((Get-Item "dist\zkteco-backend.exe").Length / 1MB, 2)
    Write-Success "Backend executable created: dist\zkteco-backend.exe ($fileSize MB)"

    # Create architecture-specific copy for Tauri
    Copy-Item "dist\zkteco-backend.exe" "dist\zkteco-backend-x86_64-pc-windows-msvc.exe"
    Write-Success "Created architecture-specific copy: dist\zkteco-backend-x86_64-pc-windows-msvc.exe"

    Set-Location $PROJECT_ROOT
    Write-Host ""
}

# ===================
# Frontend Build  
# ===================
if (-not $SkipFrontend) {
    Write-Log "Building Frontend..." "Cyan"
    Set-Location "$PROJECT_ROOT\frontend"

    # Install frontend dependencies
    Write-Log "Installing frontend dependencies..." "Yellow"
    if ($pkgManager -eq "bun") {
        bun install
    } else {
        npm install
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to install frontend dependencies"
    }

    # Build frontend
    Write-Log "Building frontend assets..." "Yellow"
    if ($pkgManager -eq "bun") {
        bun run build
    } else {
        npm run build
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to build frontend"
    }

    # Build Tauri app
    Write-Log "Building Tauri desktop application..." "Yellow"
    if ($pkgManager -eq "bun") {
        bunx tauri build
    } else {
        npx tauri build
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to build Tauri app"
    }

    Set-Location $PROJECT_ROOT
    Write-Host ""
}

# ===================
# Final Output
# ===================
Write-Log "Build completed successfully!" "Green"

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "       BUILD RESULTS" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green

# Backend results
if (-not $SkipBackend) {
    Write-Host "Backend:" -ForegroundColor Blue
    Write-Host "  📁 Executable: backend\dist\zkteco-backend.exe"
    Write-Host "  📁 Architecture-specific: backend\dist\zkteco-backend-x86_64-pc-windows-msvc.exe"
    Write-Host "  📊 Size: $fileSize MB"
}

# Frontend/Tauri results
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "Frontend/Desktop App:" -ForegroundColor Blue
    $bundleDir = "frontend\src-tauri\target\release\bundle"
    if (Test-Path $bundleDir) {
        $msiFiles = Get-ChildItem "$bundleDir\msi\*.msi" -ErrorAction SilentlyContinue
        $exeFiles = Get-ChildItem "$bundleDir\exe\*.exe" -ErrorAction SilentlyContinue
        
        if ($msiFiles) {
            foreach ($file in $msiFiles) {
                Write-Host "  💿 Installer: $($file.Name)"
            }
        }
        if ($exeFiles) {
            foreach ($file in $exeFiles) {
                Write-Host "  📱 Executable: $($file.Name)"
            }
        }
    }
}

Write-Host ""
Write-Host "🎉 All builds completed successfully!" -ForegroundColor Green
Write-Host "💡 You can find all build artifacts in:" -ForegroundColor Blue
Write-Host "   - backend\dist\ (Python executables)"
Write-Host "   - frontend\src-tauri\target\release\bundle\ (Desktop installers)"
Write-Host ""

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
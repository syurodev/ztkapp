# PowerShell script to build backend executable
param(
    [switch]$Windowed = $false
)

# Navigate to the backend directory
Set-Location -Path $PSScriptRoot

Write-Host "Building backend executable with PyInstaller..." -ForegroundColor Green

# Check if virtual environment exists and activate it
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
} elseif (Test-Path "venv\Scripts\activate.bat") {
    Write-Host "Activating virtual environment (batch)..." -ForegroundColor Yellow
    & cmd /c "venv\Scripts\activate.bat && set"
} else {
    Write-Warning "venv not found. Using system python."
}

# Check if spec file exists, if so use it, otherwise create new one
if (Test-Path "zkteco-backend.spec") {
    Write-Host "Using existing spec file with custom configuration..." -ForegroundColor Cyan
    & pyinstaller zkteco-backend.spec
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Creating new spec file..." -ForegroundColor Yellow
    
    # Prepare PyInstaller arguments
    $pyinstallerArgs = @(
        "--name", "zkteco-backend",
        "--onefile",
        "--noconfirm",
        "service_app.py"
    )
    
    # Add windowed flag if specified
    if ($Windowed) {
        $pyinstallerArgs += "--windowed"
    }
    
    # Run PyInstaller
    & pyinstaller @pyinstallerArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Initial PyInstaller run failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
    
    # Add hidden imports to the spec file
    Write-Host "Adding hidden imports to spec file..." -ForegroundColor Yellow
    
    $specContent = Get-Content "zkteco-backend.spec" -Raw
    $updatedContent = $specContent -replace 
        'hiddenimports=\[\]', 
        "hiddenimports=['zkteco.config.settings', 'zkteco.config.config_manager']"
    
    Set-Content "zkteco-backend.spec" -Value $updatedContent
    
    # Rebuild with the updated spec
    Write-Host "Rebuilding with updated spec file..." -ForegroundColor Yellow
    & pyinstaller zkteco-backend.spec
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Final PyInstaller run failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

# Verify the executable was created
$exePath = "dist\zkteco-backend.exe"
if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    Write-Host "Backend build complete!" -ForegroundColor Green
    Write-Host "Executable: $exePath" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($fileInfo.Length / 1MB, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Error "Build failed: Executable not found at $exePath"
    exit 1
}

# Copy executable with architecture suffix for Tauri
$archSuffix = "x86_64-pc-windows-msvc.exe"
$targetPath = "dist\zkteco-backend-$archSuffix"

Copy-Item $exePath $targetPath -Force
Write-Host "Created architecture-specific copy: $targetPath" -ForegroundColor Green
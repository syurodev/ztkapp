@echo off
setlocal EnableDelayedExpansion

REM Navigate to the backend directory
cd /d "%~dp0"

echo ====================================
echo    ZKTeco Backend Build Script
echo ====================================

REM Check Python version compatibility
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and add it to PATH
    goto :error
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Check if virtual environment exists and create if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        goto :error
    )
)

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found, using system Python
)

REM Install/upgrade required packages
echo Installing/upgrading dependencies...
pip install --upgrade pip
pip install --upgrade pyinstaller

REM Install Git if not present (needed for pyzk dependency)
git --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Git not found. pyzk installation may fail.
    echo Please install Git from https://git-scm.com/ and restart.
)

REM Install pyzk separately first (common issue on Windows)
echo Installing pyzk from GitHub...
pip install git+https://github.com/zeidanbm/pyzk.git@9cd5731543e3839a94962403c7ad7a5e9c872bac
if errorlevel 1 (
    echo WARNING: Failed to install pyzk from GitHub, trying alternative...
    pip install pyzk
    if errorlevel 1 (
        echo ERROR: Failed to install pyzk. Please check your Git installation.
        goto :error
    )
)

REM Install remaining dependencies
echo Installing remaining dependencies...
if exist "requirements-windows.txt" (
    echo Using Windows-specific requirements...
    pip install -r requirements-windows.txt
) else (
    echo Using default requirements...
    pip install -r requirements.txt
)
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    goto :error
)

REM Verify zk module can be imported
echo Verifying zk module installation...
python -c "from zk import ZK; print('✓ zk module imported successfully')"
if errorlevel 1 (
    echo ERROR: zk module cannot be imported. Installation failed.
    goto :error
)

REM Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Clean old spec file to ensure fresh build
if exist "zkteco-backend.spec" (
    echo Removing old spec file...
    del "zkteco-backend.spec"
)

echo Building backend executable with PyInstaller...
pyinstaller --name "zkteco-backend" ^
            --onefile ^
            --console ^
            --noconfirm ^
            --clean ^
            --hidden-import=flask ^
            --hidden-import=flask.json ^
            --hidden-import=flask.templating ^
            --hidden-import=werkzeug ^
            --hidden-import=werkzeug.security ^
            --hidden-import=requests ^
            --hidden-import=psutil ^
            --hidden-import=zk ^
            --hidden-import=zk.base ^
            --hidden-import=zk.user ^
            --hidden-import=zk.attendance ^
            --hidden-import=zk.finger ^
            --hidden-import=zk.const ^
            --hidden-import=zk.exception ^
            --hidden-import=sqlite3 ^
            --hidden-import=dotenv ^
            --hidden-import=chrono ^
            --collect-all=flask ^
            --collect-all=zk ^
            --add-data="src/app;app" ^
            --add-data="src/pyzk/zk;zk" ^
            service_app.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed
    goto :error
)

REM Verify build success
if exist "dist\zkteco-backend.exe" (
    echo.
    echo ====================================
    echo     BUILD SUCCESSFUL!
    echo ====================================
    echo.
    echo ⚡ UAC ADMIN PRIVILEGES ENABLED:
    echo   - Executable will prompt for admin rights
    echo   - Required for device access on Windows
    
    REM Get file size
    for %%A in ("dist\zkteco-backend.exe") do (
        set SIZE=%%~zA
        set /a SIZE_MB=!SIZE!/1024/1024
    )
    
    echo Executable: dist\zkteco-backend.exe
    echo Size: !SIZE_MB!MB
    
    REM Create architecture-specific copy for Tauri
    copy "dist\zkteco-backend.exe" "dist\zkteco-backend-x86_64-pc-windows-msvc.exe" >nul
    echo Created: dist\zkteco-backend-x86_64-pc-windows-msvc.exe
    
    echo.
    echo Build completed successfully!
) else (
    echo ERROR: Build failed - executable not found
    goto :error
)

goto :end

:error
echo.
echo ====================================
echo        BUILD FAILED!
echo ====================================
echo.
echo Troubleshooting tips:
echo 1. Ensure Python 3.8+ is installed and added to PATH
echo 2. Install Git from https://git-scm.com/ (required for pyzk)
echo 3. Check if all dependencies are installed: pip install -r requirements.txt
echo 4. Try deleting venv folder and run script again
echo 5. Check for antivirus blocking PyInstaller
echo 6. If pyzk fails: pip install pyzk (fallback to PyPI version)
echo 7. Manual install: pip install git+https://github.com/zeidanbm/pyzk.git
echo.

:end
pause
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
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    goto :error
)

REM Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Check if spec file exists
if exist "zkteco-backend.spec" (
    echo Using existing spec file...
    pyinstaller --clean --noconfirm zkteco-backend.spec
) else (
    echo Creating new spec file...
    pyinstaller --name "zkteco-backend" --onefile --console --noconfirm ^
                --hidden-import=zkteco.config.settings ^
                --hidden-import=zkteco.config.config_manager_sqlite ^
                --hidden-import=zkteco.database.models ^
                --hidden-import=zkteco.services ^
                --hidden-import=zkteco.controllers ^
                --hidden-import=sqlite3 ^
                --add-data="zkteco;zkteco" ^
                service_app.py
)

REM Verify build success
if exist "dist\zkteco-backend.exe" (
    echo.
    echo ====================================
    echo     BUILD SUCCESSFUL!
    echo ====================================
    
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
echo 1. Ensure Python 3.8+ is installed
echo 2. Check if all dependencies are installed: pip install -r requirements.txt
echo 3. Try deleting venv folder and run script again
echo 4. Check for antivirus blocking PyInstaller
echo.

:end
pause
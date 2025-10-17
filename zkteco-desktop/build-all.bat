@echo off
setlocal EnableDelayedExpansion

REM ==============================================================
REM ZKTeco Desktop - Complete Build Script (Windows)
REM ==============================================================

cd /d "%~dp0"
set PROJECT_ROOT=%CD%

echo ======================================
echo  ZKTeco Desktop - Full Build Script
echo ======================================
echo Project root: %PROJECT_ROOT%
echo.

REM Check system requirements
echo [INFO] Checking system requirements...

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3 is required but not installed
    goto :error
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Found Python %PYTHON_VERSION%

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is required but not installed
    goto :error
)
for /f %%i in ('node --version 2^>^&1') do set NODE_VERSION=%%i
echo [INFO] Found Node.js %NODE_VERSION%

REM Check package manager (prefer bun)
bun --version >nul 2>&1
if errorlevel 1 (
    set PKG_MANAGER=npm
    echo [WARNING] bun not found, using npm as package manager
) else (
    set PKG_MANAGER=bun
    echo [INFO] Using bun package manager
)

REM Check Rust/Cargo for Tauri
cargo --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Rust/Cargo is required for Tauri but not installed
    echo Please install from https://rustup.rs/
    goto :error
)
for /f "tokens=2" %%i in ('rustc --version 2^>^&1') do set RUST_VERSION=%%i
echo [INFO] Found Rust %RUST_VERSION%

echo.

REM ===================
REM Backend Build
REM ===================
echo [INFO] Building Backend...
cd /d "%PROJECT_ROOT%\backend"

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        goto :error
    )
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found, using system Python
)

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Check Git for pyzk installation
git --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Git not found. Installing via winget...
    winget install --id Git.Git -e --source winget
    if errorlevel 1 (
        echo [WARNING] Failed to install Git via winget. pyzk installation may fail.
        echo Please install Git manually from https://git-scm.com/
    )
)

REM Install pyzk separately first (common Windows issue)
echo [INFO] Installing pyzk dependency...
pip install git+https://github.com/zeidanbm/pyzk.git@9cd5731543e3839a94962403c7ad7a5e9c872bac
if errorlevel 1 (
    echo [WARNING] GitHub install failed, trying PyPI fallback...
    pip install pyzk
    if errorlevel 1 (
        echo [ERROR] Failed to install pyzk. Please check your Git installation.
        goto :error
    )
)

REM Install remaining dependencies
echo [INFO] Installing Python dependencies...
if exist "requirements-windows.txt" (
    echo [INFO] Using Windows-specific requirements...
    pip install -r requirements-windows.txt
) else (
    echo [INFO] Using default requirements...
    pip install -r requirements.txt
)
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies
    goto :error
)

REM Verify zk module can be imported
echo [INFO] Verifying zk module installation...
python -c "from zk import ZK; print('[OK] zk module imported successfully')"
if errorlevel 1 (
    echo [ERROR] zk module cannot be imported. Installation failed.
    goto :error
)

REM Clean previous builds
echo [INFO] Cleaning previous backend builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Force remove old spec file to ensure a fresh build from command args
if exist "zkteco-backend.spec" (
    echo [INFO] Removing outdated zkteco-backend.spec file...
    del "zkteco-backend.spec"
)

REM Clean old spec file to ensure fresh build
if exist "zkteco-backend.spec" (
    echo [INFO] Removing old spec file...
    del "zkteco-backend.spec"
)

REM Build with PyInstaller
echo [INFO] Building backend executable...
pyinstaller --name "zkteco-backend" ^
            --onefile ^
            --console ^
            --noconfirm ^
            --clean -p src -p src/pyzatt ^
            --hidden-import=flask ^
            --hidden-import=flask.json ^
            --hidden-import=werkzeug ^
            --hidden-import=requests ^
            --hidden-import=psutil ^
            --hidden-import=zk ^
            --hidden-import=pyzatt ^
            --hidden-import=sqlite3 ^
            --hidden-import=dotenv ^
            --hidden-import=chrono ^
            --hidden-import=flask_cors ^
            --hidden-import=sentry_sdk ^
            --hidden-import=apscheduler ^
            --hidden-import=logging.handlers ^
            --hidden-import=app.models.door ^
            --hidden-import=app.models.door_access_log ^
            --hidden-import=app.repositories.door_repository ^
            --hidden-import=app.repositories.door_access_repository ^
            --collect-all=flask ^
            --collect-all=zk ^
            --collect-all=pyzatt ^
            --add-data="src/app;app" ^
            service_app.py

if errorlevel 1 (
    echo [ERROR] Backend build failed
    goto :error
)

REM Verify executable was created
if not exist "dist\zkteco-backend.exe" (
    echo [ERROR] Backend build failed - executable not found
    goto :error
)

for %%A in ("dist\zkteco-backend.exe") do (
    set SIZE=%%~zA
    set /a SIZE_MB=!SIZE!/1024/1024
)
echo [SUCCESS] Backend executable created: dist\zkteco-backend.exe (!SIZE_MB!MB)

REM Create architecture-specific copy for Tauri
copy "dist\zkteco-backend.exe" "dist\zkteco-backend-x86_64-pc-windows-msvc.exe" >nul
echo [SUCCESS] Created architecture-specific copy: dist\zkteco-backend-x86_64-pc-windows-msvc.exe

echo.

REM ===================
REM Frontend Build
REM ===================
echo [INFO] Building Frontend...
cd /d "%PROJECT_ROOT%\frontend"

REM Install frontend dependencies
echo [INFO] Installing frontend dependencies...
if "%PKG_MANAGER%"=="bun" (
    bun install
) else (
    npm install
)
if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies
    goto :error
)

REM Build frontend
echo [INFO] Building frontend assets...
if "%PKG_MANAGER%"=="bun" (
    bun run build
) else (
    npm run build
)
if errorlevel 1 (
    echo [ERROR] Failed to build frontend
    goto :error
)

REM Build Tauri app
echo [INFO] Building Tauri desktop application...
if "%PKG_MANAGER%"=="bun" (
    bunx tauri build
) else (
    npx tauri build
)
if errorlevel 1 (
    echo [ERROR] Failed to build Tauri app
    goto :error
)

echo.

REM ===================
REM Final Output
REM ===================
echo [INFO] Build completed successfully!

echo.
echo ======================================
echo        BUILD RESULTS
echo ======================================

REM Backend results
echo Backend:
echo   📁 Executable: backend\dist\zkteco-backend.exe
echo   📁 Architecture-specific: backend\dist\zkteco-backend-x86_64-pc-windows-msvc.exe
echo   📊 Size: !SIZE_MB!MB

REM Frontend/Tauri results
echo.
echo Frontend/Desktop App:
set BUNDLE_DIR=frontend\src-tauri\target\release\bundle
if exist "%BUNDLE_DIR%" (
    if exist "%BUNDLE_DIR%\msi" (
        for %%f in ("%BUNDLE_DIR%\msi\*.msi") do echo   💿 Installer: %%~nxf
    )
    if exist "%BUNDLE_DIR%\exe" (
        for %%f in ("%BUNDLE_DIR%\exe\*.exe") do echo   📱 Executable: %%~nxf
    )
)

echo.
echo 🎉 All builds completed successfully!
echo 💡 You can find all build artifacts in:
echo    - backend\dist\ (Python executables)
echo    - frontend\src-tauri\target\release\bundle\ (Desktop installers)
echo.

goto :end

:error
echo.
echo ======================================
echo        BUILD FAILED!
echo ======================================
echo.
echo Troubleshooting tips:
echo 1. Ensure Python 3.8+ is installed and added to PATH
echo 2. Install Git from https://git-scm.com/ (required for pyzk)
echo 3. Install Node.js 18+ from https://nodejs.org/
echo 4. Install Rust from https://rustup.rs/
echo 5. Try deleting venv folder and run script again
echo 6. Check for antivirus blocking PyInstaller
echo.

:end
pause

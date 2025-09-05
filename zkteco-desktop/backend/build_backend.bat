@echo off
REM Navigate to the backend directory
cd /d "%~dp0"

echo Building backend executable with PyInstaller...

REM Check if virtual environment exists and activate it
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Warning: venv not found. Using system python.
)

REM Check if spec file exists, if so use it, otherwise create new one
if exist "zkteco-backend.spec" (
    echo Using existing spec file with custom configuration...
    pyinstaller zkteco-backend.spec
) else (
    echo Creating new spec file...
    REM Run PyInstaller
    REM --name: Name of the executable
    REM --onefile: Bundle everything into a single executable
    REM --windowed: Prevents a console window from appearing on Windows
    REM --noconfirm: Overwrite output directory without asking
    pyinstaller --name "zkteco-backend" --onefile --windowed --noconfirm service_app.py
    
    REM Add hidden imports to the spec file using PowerShell
    echo Adding hidden imports to spec file...
    powershell -Command "(Get-Content zkteco-backend.spec) -replace 'hiddenimports=\[\]', 'hiddenimports=[''zkteco.config.settings'', ''zkteco.config.config_manager'']' | Set-Content zkteco-backend.spec"
    
    REM Rebuild with the updated spec
    echo Rebuilding with updated spec file...
    pyinstaller zkteco-backend.spec
)

echo Backend build complete. Executable is in dist\ folder.
pause
#!/bin/bash

# Navigate to the backend directory
cd "$(dirname "$0")"

echo "Building backend executable with PyInstaller..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Warning: venv not found. Using system python."
fi

# Check if spec file exists, if so use it, otherwise create new one
if [ -f "zkteco-backend.spec" ]; then
    echo "Using existing spec file with custom configuration..."
    pyinstaller zkteco-backend.spec
else
    echo "Creating new spec file..."
    # Run PyInstaller
    # --name: Name of the executable
    # --onefile: Bundle everything into a single executable
    # --windowed: Prevents a console window from appearing on Windows
    # --noconfirm: Overwrite output directory without asking
    pyinstaller --name "zkteco-backend" --onefile --noconfirm service_app.py
    
    # Add hidden imports to the spec file
    echo "Adding hidden imports to spec file..."
    sed -i '' "s/hiddenimports=\[\]/hiddenimports=['zkteco.config.settings', 'zkteco.config.config_manager']/" zkteco-backend.spec
    
    # Rebuild with the updated spec
    echo "Rebuilding with updated spec file..."
    pyinstaller zkteco-backend.spec
fi

echo "Backend build complete. Executable is in dist/ folder."

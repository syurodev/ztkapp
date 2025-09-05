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
    
    if [ $? -ne 0 ]; then
        echo "Error: PyInstaller failed"
        exit 1
    fi
else
    echo "Creating new spec file..."
    # Run PyInstaller
    # --name: Name of the executable
    # --onefile: Bundle everything into a single executable
    # --noconfirm: Overwrite output directory without asking
    pyinstaller --name "zkteco-backend" --onefile --noconfirm service_app.py
    
    if [ $? -ne 0 ]; then
        echo "Error: Initial PyInstaller run failed"
        exit 1
    fi
    
    # Add hidden imports to the spec file
    echo "Adding hidden imports to spec file..."
    # Use different sed syntax for cross-platform compatibility
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/hiddenimports=\[\]/hiddenimports=['zkteco.config.settings', 'zkteco.config.config_manager']/" zkteco-backend.spec
    else
        # Linux
        sed -i "s/hiddenimports=\[\]/hiddenimports=['zkteco.config.settings', 'zkteco.config.config_manager']/" zkteco-backend.spec
    fi
    
    # Rebuild with the updated spec
    echo "Rebuilding with updated spec file..."
    pyinstaller zkteco-backend.spec
    
    if [ $? -ne 0 ]; then
        echo "Error: Final PyInstaller run failed"
        exit 1
    fi
fi

# Verify executable was created
EXEC_PATH="dist/zkteco-backend"
if [ -f "$EXEC_PATH" ]; then
    FILE_SIZE=$(ls -lah "$EXEC_PATH" | awk '{print $5}')
    echo "Backend build complete!"
    echo "Executable: $EXEC_PATH"
    echo "Size: $FILE_SIZE"
    
    # Create architecture-specific copies for Tauri
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Detect architecture
        if [[ $(uname -m) == "arm64" ]]; then
            ARCH_SUFFIX="aarch64-apple-darwin"
        else
            ARCH_SUFFIX="x86_64-apple-darwin"
        fi
    else
        # Linux
        ARCH_SUFFIX="x86_64-unknown-linux-gnu"
    fi
    
    TARGET_PATH="dist/zkteco-backend-$ARCH_SUFFIX"
    cp "$EXEC_PATH" "$TARGET_PATH"
    echo "Created architecture-specific copy: $TARGET_PATH"
else
    echo "Error: Build failed - executable not found at $EXEC_PATH"
    exit 1
fi

echo "Backend build complete. Executable is in dist/ folder."

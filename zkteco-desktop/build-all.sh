#!/bin/bash

# ==============================================================
# ZKTeco Desktop - Complete Build Script (macOS/Linux)
# ==============================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Navigate to project root
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN} ZKTeco Desktop - Full Build Script${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "${BLUE}Project root: ${PROJECT_ROOT}${NC}"
echo ""

# Function to log with timestamp
log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} "
}

error() {
    echo -e "${RED}[ERROR]${NC} "
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} "
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} "
}

# Check system requirements
log "Checking system requirements..."

# Check Python
if ! command -v python3 &> /dev/null; then
    error "Python 3 is required but not installed"
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log "Found Python ${PYTHON_VERSION}"

# Check Node.js
if ! command -v node &> /dev/null; then
    error "Node.js is required but not installed"
fi
NODE_VERSION=$(node --version)
log "Found Node.js ${NODE_VERSION}"

# Check if bun is available, fallback to npm
if command -v bun &> /dev/null; then
    PKG_MANAGER="bun"
    log "Using bun package manager"
else
    PKG_MANAGER="npm"
    warning "bun not found, using npm as package manager"
fi

# Check Rust/Cargo for Tauri
if ! command -v cargo &> /dev/null; then
    error "Rust/Cargo is required for Tauri but not installed. Install from https://rustup.rs/"
fi
RUST_VERSION=$(rustc --version | awk '{print $2}')
log "Found Rust ${RUST_VERSION}"

echo ""

# ===================
# Backend Build
# ===================
log "Building Backend..."
cd "${PROJECT_ROOT}/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        error "Failed to create virtual environment"
    fi
fi

# Activate virtual environment
log "Activating virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    
    # Verify activation by checking Python path
    PYTHON_PATH=$(which python)
    if [[ "$PYTHON_PATH" == *"venv"* ]]; then
        log "Virtual environment activated successfully"
    else
        warning "Virtual environment may not be active, Python path: $PYTHON_PATH"
    fi
else
    warning "Virtual environment activation script not found"
fi

# Use explicit paths to ensure we use venv's pip and python
VENV_PYTHON="./venv/bin/python"
VENV_PIP="./venv/bin/pip"

if [ ! -f "$VENV_PIP" ]; then
    error "pip not found in virtual environment at $VENV_PIP"
fi

# Upgrade pip and install dependencies
log "Installing Python dependencies..."
$VENV_PIP install --upgrade pip

# Check if Git is available for pyzk installation
if ! command -v git &> /dev/null; then
    warning "Git not found. pyzk installation may fail."
fi

# Install pyzk separately first (common issue)
log "Installing pyzk dependency..."
if $VENV_PIP install git+https://github.com/zeidanbm/pyzk.git@9cd5731543e3839a94962403c7ad7a5e9c872bac; then
    success "pyzk installed from GitHub"
else
    warning "GitHub install failed, trying PyPI fallback..."
    $VENV_PIP install pyzk || error "Failed to install pyzk"
fi

# Install remaining dependencies
$VENV_PIP install -r requirements.txt || error "Failed to install Python dependencies"

# Verify zk module can be imported
log "Verifying zk module installation..."
$VENV_PYTHON -c "from zk import ZK; print('✓ zk module imported successfully')" || error "zk module cannot be imported"

# Clean previous builds
log "Cleaning previous backend builds..."
rm -rf build dist

# Build with PyInstaller
log "Building backend executable..."
if [ -f "zkteco-backend.spec" ]; then
    log "Using existing spec file..."
    pyinstaller --clean --noconfirm zkteco-backend.spec
else
    log "Creating new spec file..."
    pyinstaller --name "zkteco-backend" --onefile --console --noconfirm \
                --hidden-import=zkteco.config.settings \
                --hidden-import=zkteco.config.config_manager_sqlite \
                --hidden-import=zkteco.database.models \
                --hidden-import=zkteco.services \
                --hidden-import=zkteco.controllers \
                --hidden-import=sqlite3 \
                --hidden-import=flask_cors \
                --hidden-import=logging.handlers \
                --hidden-import=sentry_sdk \
                --hidden-import=psutil \
                --hidden-import=requests \
                --hidden-import=dotenv \
                --hidden-import=apscheduler \
                --add-data="zkteco:zkteco" \
                service_app.py
fi

# Verify executable was created
EXEC_PATH="dist/zkteco-backend"
if [ ! -f "$EXEC_PATH" ]; then
    error "Backend build failed - executable not found at $EXEC_PATH"
fi

FILE_SIZE=$(ls -lah "$EXEC_PATH" | awk '{print $5}')
success "Backend executable created: $EXEC_PATH (${FILE_SIZE})"

# Create architecture-specific copies for Tauri
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ $(uname -m) == "arm64" ]]; then
        ARCH_SUFFIX="aarch64-apple-darwin"
    else
        ARCH_SUFFIX="x86_64-apple-darwin"
    fi
else
    ARCH_SUFFIX="x86_64-unknown-linux-gnu"
fi

TARGET_PATH="dist/zkteco-backend-$ARCH_SUFFIX"
cp "$EXEC_PATH" "$TARGET_PATH"
success "Created architecture-specific copy: $TARGET_PATH"

echo ""

# ===================
# Frontend Build  
# ===================
log "Building Frontend..."
cd "${PROJECT_ROOT}/frontend"

# Install frontend dependencies
log "Installing frontend dependencies..."
if [ "$PKG_MANAGER" = "bun" ]; then
    bun install || error "Failed to install frontend dependencies"
else
    npm install || error "Failed to install frontend dependencies"
fi

# Build frontend
log "Building frontend assets..."
if [ "$PKG_MANAGER" = "bun" ]; then
    bun run build || error "Failed to build frontend"
else
    npm run build || error "Failed to build frontend"
fi

# Build Tauri app
log "Building Tauri desktop application..."
if [ "$PKG_MANAGER" = "bun" ]; then
    bunx tauri build || error "Failed to build Tauri app"
else
    npx tauri build || error "Failed to build Tauri app"
fi

echo ""

# ===================
# Final Output
# ===================
log "Build completed successfully!"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}       BUILD RESULTS${NC}"
echo -e "${GREEN}======================================${NC}"

# Backend results
echo -e "${BLUE}Backend:${NC}"
echo "  📁 Executable: backend/dist/zkteco-backend"
echo "  📁 Architecture-specific: backend/dist/zkteco-backend-$ARCH_SUFFIX"
echo "  📊 Size: $FILE_SIZE"

# Frontend/Tauri results
echo ""
echo -e "${BLUE}Frontend/Desktop App:${NC}"
BUNDLE_DIR="frontend/src-tauri/target/release/bundle"
if [ -d "$BUNDLE_DIR" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        APP_PATH=$(find "$BUNDLE_DIR" -name "*.app" | head -1)
        DMG_PATH=$(find "$BUNDLE_DIR" -name "*.dmg" | head -1)
        [ -n "$APP_PATH" ] && echo "  📱 App Bundle: ${APP_PATH##*/}"
        [ -n "$DMG_PATH" ] && echo "  💿 Installer: ${DMG_PATH##*/}"
    else
        DEB_PATH=$(find "$BUNDLE_DIR" -name "*.deb" | head -1)
        RPM_PATH=$(find "$BUNDLE_DIR" -name "*.rpm" | head -1)
        APPIMAGE_PATH=$(find "$BUNDLE_DIR" -name "*.AppImage" | head -1)
        [ -n "$DEB_PATH" ] && echo "  📦 DEB Package: ${DEB_PATH##*/}"
        [ -n "$RPM_PATH" ] && echo "  📦 RPM Package: ${RPM_PATH##*/}"
        [ -n "$APPIMAGE_PATH" ] && echo "  🚀 AppImage: ${APPIMAGE_PATH##*/}"
    fi
fi

echo ""
echo -e "${GREEN}🎉 All builds completed successfully!${NC}"
echo -e "${BLUE}💡 You can find all build artifacts in:${NC}"
echo "   - backend/dist/ (Python executables)"
echo "   - frontend/src-tauri/target/release/bundle/ (Desktop installers)"
echo ""
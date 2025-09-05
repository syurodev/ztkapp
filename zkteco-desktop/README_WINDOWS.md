# ZKTeco Desktop App - Windows Development Guide

## 🚀 Quick Start (Windows)

### Prerequisites
- **Python 3.9+** with pip
- **Node.js 18+** and **bun** (or npm/yarn)
- **Rust** and **Tauri CLI**
- **PowerShell** (recommended) or Command Prompt

### 1. Setup Python Virtual Environment
```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Setup Frontend Dependencies
```powershell
cd frontend
bun install
```

### 3. Development Mode
```powershell
# This will automatically build backend and start frontend + Tauri
bun run tauri dev
```

## 🔧 Build Process

### Backend Build (Windows-specific)

**Option 1: PowerShell (Recommended)**
```powershell
cd backend
.\build_backend.ps1
```

**Option 2: Batch Script**
```cmd
cd backend
build_backend.bat
```

**Option 3: Cross-platform via npm**
```powershell
cd frontend
npm run build:backend:windows
```

### Full Production Build
```powershell
cd frontend
bun run tauri build
```

## 🛠 Architecture Support

The app supports multiple Windows architectures:
- **x86_64-pc-windows-msvc** (64-bit Intel/AMD)
- **aarch64-pc-windows-msvc** (ARM64 Windows)

Backend executable naming:
- Development: `zkteco-backend.exe`
- Tauri bundle: `zkteco-backend-x86_64-pc-windows-msvc.exe`

## 🐛 Troubleshooting

### Python Virtual Environment Issues
```powershell
# If activation fails, try:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or use the batch activation:
venv\Scripts\activate.bat
```

### PyInstaller Build Failures
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check Python version: `python --version` (should be 3.9+)
3. Clear PyInstaller cache: `pyinstaller --clean zkteco-backend.spec`

### Tauri Development Issues
```powershell
# Clear Tauri cache
tauri clean

# Rebuild with verbose output
tauri build --debug
```

### Backend API Not Responding
1. Check if backend sidecar is running: `netstat -ano | findstr :5001`
2. Check Tauri logs in developer tools
3. Verify backend executable exists in `backend/dist/`

## 📁 Project Structure (Windows)

```
zkteco-desktop/
├── backend/
│   ├── venv/Scripts/        # Windows virtual environment
│   ├── dist/
│   │   ├── zkteco-backend.exe
│   │   └── zkteco-backend-x86_64-pc-windows-msvc.exe
│   ├── build_backend.bat    # Windows batch script
│   ├── build_backend.ps1    # PowerShell script (recommended)
│   └── build_backend.sh     # Unix script (for WSL)
└── frontend/
    ├── src-tauri/
    │   └── target/release/bundle/msi/  # Windows installer
    └── package.json         # Cross-platform build scripts
```

## 🚢 Distribution

Windows builds produce:
- **Executable**: `frontend.exe`
- **MSI Installer**: `frontend_0.1.0_x64_en-US.msi`
- **Bundle**: Complete Windows application package

## 🔒 Code Signing (Optional)

For production distribution, configure code signing in `tauri.conf.json`:

```json
{
  "bundle": {
    "windows": {
      "certificateThumbprint": "YOUR_CERT_THUMBPRINT",
      "digestAlgorithm": "sha256",
      "timestampUrl": "http://timestamp.digicert.com"
    }
  }
}
```

## 🌐 Cross-Platform Development

This project supports development on:
- ✅ **Windows 10/11**
- ✅ **macOS** (Intel & Apple Silicon)
- ✅ **Linux** (Ubuntu, Fedora, etc.)

The build system automatically detects your platform and uses the appropriate build scripts.
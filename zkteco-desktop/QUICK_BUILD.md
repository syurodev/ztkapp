# ZKTeco Desktop - Quick Build Guide

## 🚀 Quick Start

### Prerequisites Test
```bash
npm run test:build
```

### Build Everything
```bash
# macOS/Linux
./build-all.sh

# Windows
build-all.bat
```

### Build Results
- **Backend**: `backend/dist/zkteco-backend[.exe]`  
- **Desktop App**: `frontend/src-tauri/target/release/bundle/`

## 🛠️ Individual Components

```bash
npm run build:backend          # Backend only
npm run build:frontend         # Frontend + Tauri only
npm run clean                  # Clean all builds
```

## ⚡ Requirements

- **Python 3.8+**
- **Node.js 18+** 
- **Rust/Cargo**
- **Git** (for pyzk)

## 📊 Build Times

| Platform | Full Build Time |
|----------|----------------|
| macOS    | 6-10 minutes   |
| Windows  | 9-15 minutes   |
| Linux    | 7-12 minutes   |

*First build takes longer due to dependency downloads*

## 🐛 Common Issues

**"ModuleNotFoundError: No module named 'zk'"**
```bash
# Windows users
winget install --id Git.Git -e --source winget
build-all.bat
```

**"pip: command not found"**  
```bash
# Run from project root, not backend/
cd .. && ./build-all.sh
```

## 📖 Full Documentation

See [BUILD_GUIDE.md](BUILD_GUIDE.md) for detailed instructions.
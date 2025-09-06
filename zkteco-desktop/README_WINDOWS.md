# ZKTeco Desktop - Windows Setup

## ⚡ Quick Start

### Requirements
- **Python 3.8+** (từ [python.org](https://python.org))
- **Node.js 18+** + **bun** (hoặc npm)

### Setup (Chỉ cần chạy 1 lần)
```cmd
# 1. Clone và vào thư mục
git clone <repo-url>
cd zkteco-desktop

# 2. Build backend (tự động tạo venv + install dependencies)
cd backend
build_backend.bat

# 3. Install frontend deps
cd ..\frontend
bun install
```

### Development
```cmd
cd frontend
bun run tauri dev
```

### Production Build
```cmd
cd frontend  
bun run tauri build
```

## 🔧 Build Script Cải tiến

Script `build_backend.bat` đã được cải tiến để:
- ✅ Tự động kiểm tra Python version (hỗ trợ 3.8+)
- ✅ Tự động tạo virtual environment nếu chưa có
- ✅ Auto-install/upgrade tất cả dependencies
- ✅ Clean build trước khi build mới
- ✅ Include đầy đủ hidden imports cho SQLite
- ✅ Hiển thị thông tin chi tiết về build result
- ✅ Error handling và troubleshooting tips

## 🐛 Lỗi Thường Gặp

### "ModuleNotFoundError: No module named 'zk'"
```cmd
# Nguyên nhân: pyzk dependency chưa được cài đặt đúng
# Giải pháp 1: Cài Git và chạy lại build script
winget install --id Git.Git -e --source winget
build_backend.bat

# Giải pháp 2: Cài pyzk thủ công
cd backend
call venv\Scripts\activate.bat
pip install git+https://github.com/zeidanbm/pyzk.git

# Giải pháp 3: Dùng PyPI version (fallback)
pip install pyzk

# Verify installation
python -c "from zk import ZK; print('OK')"
```

### Python không tìm thấy
```cmd
# Cài Python từ python.org và check:
python --version

# Nếu vẫn lỗi, thử:
py --version
```

### Build thất bại  
```cmd
# Xóa venv và thử lại:
rmdir /s venv
build_backend.bat

# Hoặc check antivirus blocking PyInstaller
```

### Venv activation lỗi
```cmd
# Dùng PowerShell:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Git không tìm thấy
```cmd
# Cài Git từ trang chính thức:
# https://git-scm.com/download/win
# Hoặc dùng winget:
winget install --id Git.Git -e --source winget

# Restart Command Prompt sau khi cài
```

## 📁 Output Files

Sau khi build thành công:
```
backend/dist/
├── zkteco-backend.exe                          # Main executable  
└── zkteco-backend-x86_64-pc-windows-msvc.exe  # Tauri sidecar
```

## 🎯 Production Distribution

Final build tạo ra:
- **App**: `frontend.exe`
- **Installer**: `frontend_0.1.0_x64_en-US.msi`
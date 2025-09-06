# ZKTeco Desktop - Build Guide

Hướng dẫn build toàn bộ ứng dụng ZKTeco Desktop (Backend + Frontend + Desktop App).

## 📋 Yêu cầu hệ thống

### Tất cả nền tảng:
- **Python 3.8+** - Backend API
- **Node.js 18+** - Frontend build
- **Rust/Cargo** - Tauri desktop framework
- **Git** - Download pyzk dependency

### Tùy chọn:
- **Bun** - Package manager nhanh hơn (khuyến khích)
- **npm** - Fallback nếu không có bun

## 🚀 Build Scripts

### macOS/Linux:
```bash
# Build toàn bộ ứng dụng
./build-all.sh

# Hoặc dùng npm script
npm run build:all
```

### Windows:
```cmd
# Cách 1: Batch script
build-all.bat

# Cách 2: PowerShell script (khuyến khích)
PowerShell -ExecutionPolicy Bypass -File build-all.ps1

# Cách 3: npm script
npm run build:all:windows
```

## 📂 Kết quả Build

Sau khi build thành công, bạn sẽ có:

### Backend:
- `backend/dist/zkteco-backend` - Python executable
- `backend/dist/zkteco-backend-[arch]` - Architecture-specific copy

### Desktop App:
- **macOS**: `frontend/src-tauri/target/release/bundle/dmg/` - DMG installer
- **Windows**: `frontend/src-tauri/target/release/bundle/msi/` - MSI installer  
- **Linux**: `frontend/src-tauri/target/release/bundle/deb/` - DEB package

## 🛠️ Build riêng từng phần

### Chỉ build Backend:
```bash
# macOS/Linux
cd backend && ./build_backend.sh

# Windows
cd backend && build_backend.bat

# Hoặc dùng npm scripts
npm run build:backend          # macOS/Linux
npm run build:backend:windows  # Windows
```

### Chỉ build Frontend:
```bash
npm run build:frontend
```

## 🧹 Dọn dẹp Build

```bash
# macOS/Linux
npm run clean

# Windows  
npm run clean:windows
```

## ⚙️ Build Options (PowerShell)

PowerShell script hỗ trợ các options:

```powershell
# Skip backend build
PowerShell -ExecutionPolicy Bypass -File build-all.ps1 -SkipBackend

# Skip frontend build  
PowerShell -ExecutionPolicy Bypass -File build-all.ps1 -SkipFrontend

# Verbose output
PowerShell -ExecutionPolicy Bypass -File build-all.ps1 -Verbose
```

## 🐛 Xử lý lỗi thường gặp

### 1. "ModuleNotFoundError: No module named 'zk'"
```bash
# Cài Git và chạy lại build
winget install --id Git.Git -e --source winget

# Hoặc cài pyzk thủ công
cd backend
call venv\Scripts\activate.bat
pip install git+https://github.com/zeidanbm/pyzk.git
```

### 2. "Python not found"
- Cài Python từ [python.org](https://python.org)
- Đảm bảo Python trong PATH

### 3. "Node.js not found" 
- Cài Node.js từ [nodejs.org](https://nodejs.org)
- Khuyến khích dùng version 18+

### 4. "Rust/Cargo not found"
- Cài Rust từ [rustup.rs](https://rustup.rs)
- Restart terminal sau khi cài

### 5. Tauri build lỗi
```bash
# Cập nhật Rust toolchain
rustup update

# Cài các dependencies cần thiết (Linux)
sudo apt install -y libgtk-3-dev libwebkit2gtk-4.0-dev libappindicator3-dev librsvg2-dev patchelf
```

### 6. PowerShell ExecutionPolicy lỗi
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📊 Build Times (ước tính)

| Component | macOS | Windows | Linux |
|-----------|-------|---------|-------|
| Backend   | 2-3 phút | 3-5 phút | 2-4 phút |
| Frontend  | 1-2 phút | 1-2 phút | 1-2 phút |
| Tauri     | 3-5 phút | 5-8 phút | 4-6 phút |
| **Tổng**  | **6-10 phút** | **9-15 phút** | **7-12 phút** |

*Lần build đầu sẽ lâu hơn do cần download dependencies*

## 🔧 Tuning Performance

### Tăng tốc Build:
1. **Dùng SSD** thay vì HDD
2. **Tăng RAM** (khuyến khích 8GB+)  
3. **Dùng bun** thay vì npm
4. **Enable cargo cache**:
   ```bash
   export CARGO_TARGET_DIR="$HOME/.cargo/target"
   ```

### Giảm dung lượng output:
- Dùng `--release` cho builds production
- Strip debug symbols với `--strip`
- Enable LTO (Link Time Optimization)

## 💡 Tips

- **Parallel builds**: Các scripts đã tối ưu để build song song khi có thể
- **Caching**: Dependencies được cache để lần build tiếp theo nhanh hơn  
- **Cross-platform**: Scripts tự detect OS và dùng commands phù hợp
- **Error handling**: Build dừng ngay khi có lỗi để dễ debug

## 📞 Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra log chi tiết trong terminal
2. Chạy `npm run clean` và thử lại
3. Xem phần "Xử lý lỗi thường gặp" ở trên
4. Tạo issue trên repository với log đầy đủ
# Windows Build Guide - ZKTeco Desktop

Hướng dẫn build ứng dụng trên Windows và fix lỗi backend không chạy.

## Vấn đề hiện tại

Trên Windows, bạn gặp 2 vấn đề:
1. **Backend không khởi động** - Không có tiến trình backend
2. **Không lấy được IP** (local và public)

## Nguyên nhân

### 1. Backend không khởi động
- Backend chưa được build thành executable (`.exe`)
- File executable chưa được đặt vào thư mục Tauri binaries
- Tauri không tìm thấy backend sidecar để khởi động

### 2. Không lấy được IP
- Backend cần internet để lấy public IP từ `https://api.ipify.org`
- Nếu không có internet hoặc firewall block, sẽ fallback về:
  - Local IP: `127.0.0.1`
  - Public IP: `N/A`

## Giải pháp

### Bước 1: Chuẩn bị môi trường

**Yêu cầu:**
- Python 3.8+
- Git
- PyInstaller (đã có)
- Node.js & npm

**Kiểm tra:**
```cmd
python --version
git --version
pip show pyinstaller
node --version
npm --version
```

### Bước 2: Build backend executable

**Cách 1: Sử dụng script tự động (Recommended)**

```cmd
cd zkteco-desktop
build_and_deploy.bat
```

Script này sẽ:
1. Build backend thành `.exe`
2. Tạo thư mục `frontend/src-tauri/binaries`
3. Copy executable vào Tauri

**Cách 2: Manual**

```cmd
# Build backend
cd zkteco-desktop/backend
build_backend.bat

# Tạo thư mục binaries
cd ..\frontend\src-tauri
mkdir binaries

# Copy executable
copy ..\..\backend\dist\zkteco-backend-x86_64-pc-windows-msvc.exe binaries\
```

### Bước 3: Verify

Kiểm tra file đã tồn tại:
```cmd
dir frontend\src-tauri\binaries\zkteco-backend-x86_64-pc-windows-msvc.exe
```

Nếu file tồn tại (kích thước ~30-50MB), bạn đã hoàn thành!

### Bước 4: Build Tauri app

```cmd
cd frontend
npm install
npm run tauri build
```

## Cấu trúc thư mục đúng

```
zkteco-desktop/
├── backend/
│   ├── build_backend.bat          ← Script build backend
│   └── dist/
│       └── zkteco-backend-x86_64-pc-windows-msvc.exe
│
├── frontend/
│   └── src-tauri/
│       ├── binaries/              ← Phải tạo thư mục này!
│       │   └── zkteco-backend-x86_64-pc-windows-msvc.exe  ← Copy vào đây
│       ├── src/
│       │   └── lib.rs
│       └── tauri.conf.json
│
└── build_and_deploy.bat           ← Script tự động (mới tạo)
```

## Vị trí file log trên Windows

Khi backend chạy, log sẽ được lưu tại:

**Primary:**
```
C:\Users\<username>\AppData\Local\ZKTeco\app.log
```

**Fallback:**
- `C:\Users\<username>\AppData\Roaming\ZKTeco\app.log`
- `C:\Users\<username>\zkteco_logs\app.log`
- Thư mục hiện tại

**Mở nhanh:**
1. Nhấn `Win + R`
2. Gõ: `%LOCALAPPDATA%\ZKTeco`
3. Mở file `app.log`

## Troubleshooting

### Lỗi: "Backend sidecar not found"

**Nguyên nhân:** Executable không có trong `binaries/`

**Fix:**
```cmd
# Kiểm tra file tồn tại
dir frontend\src-tauri\binaries\zkteco-backend-x86_64-pc-windows-msvc.exe

# Nếu không có, chạy lại build
build_and_deploy.bat
```

### Lỗi: "Failed to fetch public IP"

**Nguyên nhân:** Không có internet hoặc firewall block

**Fix:**
- Kiểm tra kết nối internet
- Tắt tạm thời firewall/antivirus
- Accept fallback values (127.0.0.1 và N/A)

### Lỗi: "Port 57575 already in use"

**Nguyên nhân:** Backend đã chạy hoặc port bị chiếm

**Fix:**
```cmd
# Tìm process đang dùng port
netstat -ano | findstr :57575

# Kill process (thay <PID> bằng số hiển thị)
taskkill /PID <PID> /F
```

### Lỗi: Backend crash ngay sau khi start

**Kiểm tra log:**
```cmd
type %LOCALAPPDATA%\ZKTeco\app.log
```

**Nguyên nhân thường gặp:**
1. Thiếu Python dependencies → Rebuild với `build_backend.bat`
2. Database path không tồn tại → Tự động tạo, nhưng kiểm tra permissions
3. Antivirus block → Thêm exception cho `.exe`

## Test backend manual

Trước khi build Tauri, test backend riêng:

```cmd
# Chạy executable trực tiếp
cd backend\dist
zkteco-backend-x86_64-pc-windows-msvc.exe

# Backend sẽ start trên http://0.0.0.0:57575
# Mở browser: http://localhost:57575/service/status
```

Nếu thấy response JSON → Backend hoạt động tốt!

## Network Configuration

Backend listen trên:
- Host: `0.0.0.0` (tất cả interfaces)
- Port: `57575`

Để thay đổi, set environment variables:
```cmd
set HOST=127.0.0.1
set PORT=8080
zkteco-backend-x86_64-pc-windows-msvc.exe
```

## Checklist hoàn thành

- [ ] Python 3.8+ installed
- [ ] Git installed
- [ ] PyInstaller installed
- [ ] Backend built: `build_backend.bat`
- [ ] Binaries folder created: `frontend/src-tauri/binaries`
- [ ] Executable copied to binaries
- [ ] Verified file size ~30-50MB
- [ ] Tested backend manually
- [ ] Built Tauri app: `npm run tauri build`
- [ ] Installed and tested final `.exe`

## Liên hệ

Nếu vẫn gặp vấn đề, cung cấp:
1. Nội dung file log: `%LOCALAPPDATA%\ZKTeco\app.log`
2. Output của: `build_backend.bat`
3. Kích thước file executable
4. Windows version

# Fix: ModuleNotFoundError: No module named 'app'

## Vấn đề đã sửa

Lỗi này xảy ra vì PyInstaller không include đúng module `app` khi build.

## Thay đổi

### ✅ Đã sửa trong `build_backend.bat` và `build-all.bat`:

**BEFORE (SAI):**
```batch
--add-data="zkteco;zkteco"
--hidden-import=zkteco.config.settings
--hidden-import=zkteco.database.models
```

**AFTER (ĐÚNG):**
```batch
--add-data="src/app;app"
--add-data="src/pyzk/zk;zk"
--hidden-import=flask
--hidden-import=werkzeug
--collect-all=flask
--collect-all=zk
```

## Các thay đổi chi tiết:

### 1. Add-data paths
- ✅ `--add-data="src/app;app"` - Copy thư mục `src/app` vào executable
- ✅ `--add-data="src/pyzk/zk;zk"` - Copy module `zk` từ pyzk

### 2. Hidden imports
Thêm tất cả Flask và dependencies:
- `flask`, `flask.json`, `flask.templating`
- `werkzeug`, `werkzeug.security`
- `requests`, `psutil`, `dotenv`, `chrono`
- `zk.*` modules (base, user, attendance, finger, const, exception)

### 3. Collect-all
- `--collect-all=flask` - Auto-collect tất cả Flask submodules
- `--collect-all=zk` - Auto-collect tất cả ZK submodules

### 4. Clean build
- Xóa spec file cũ trước khi build
- Sử dụng `--clean` flag để đảm bảo build sạch

## Cách sử dụng

### Option 1: Build chỉ backend
```cmd
cd zkteco-desktop\backend
build_backend.bat
```

### Option 2: Build toàn bộ app
```cmd
cd zkteco-desktop
build-all.bat
```

## Verify build thành công

Sau khi build xong, kiểm tra:

```cmd
cd backend\dist
dir zkteco-backend-x86_64-pc-windows-msvc.exe
```

File size nên ~30-50MB.

## Test backend manual

```cmd
cd backend\dist
zkteco-backend-x86_64-pc-windows-msvc.exe
```

Backend sẽ khởi động trên: `http://0.0.0.0:57575`

Test với browser: `http://localhost:57575/service/status`

Nếu thấy JSON response → Backend hoạt động!

## Next steps

Sau khi backend build thành công:

1. **Copy vào Tauri binaries:**
   ```cmd
   mkdir frontend\src-tauri\binaries
   copy backend\dist\zkteco-backend-x86_64-pc-windows-msvc.exe frontend\src-tauri\binaries\
   ```

2. **Build Tauri app:**
   ```cmd
   cd frontend
   npm install
   npm run tauri build
   ```

3. **Test final app:**
   ```cmd
   cd src-tauri\target\release
   zkteco-desktop.exe
   ```

## Troubleshooting

### Nếu vẫn lỗi "No module named 'app'"

1. **Xóa build cache:**
   ```cmd
   cd backend
   rmdir /s /q build
   rmdir /s /q dist
   del zkteco-backend.spec
   ```

2. **Verify Python path:**
   ```cmd
   python -c "import sys; print(sys.path)"
   ```

   Đảm bảo `src` directory có trong path.

3. **Test imports thủ công:**
   ```cmd
   cd backend
   python -c "import sys; sys.path.insert(0, 'src'); from app import create_app; print('OK')"
   ```

### Nếu lỗi import Flask/ZK modules

```cmd
cd backend
call venv\Scripts\activate.bat
pip install --upgrade flask werkzeug requests psutil python-dotenv
```

## Log files location

Khi backend chạy, check logs tại:
```
C:\Users\<username>\AppData\Local\ZKTeco\app.log
```

Hoặc mở nhanh:
```cmd
explorer %LOCALAPPDATA%\ZKTeco
```

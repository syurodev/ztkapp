# Cross-Platform Build Guide

## Tổng Quan

Repository này đã được cấu hình để build tự động cho tất cả nền tảng (Windows, macOS, Linux) thông qua GitHub Actions.

## Cách Sử Dụng GitHub Actions

### 1. Tự Động Build Khi Tạo Tag

Tạo tag mới để trigger build cho tất cả platforms:

```bash
# Tạo tag mới
git tag v1.0.0
git push origin v1.0.0
```

Build sẽ tự động chạy và tạo release với tất cả installers.

### 2. Manual Trigger

Có thể trigger build thủ công từ GitHub Actions tab:
1. Vào Actions tab trong GitHub repository
2. Chọn "Cross-Platform Build" workflow  
3. Click "Run workflow"

### 3. Build Khi Tạo Pull Request

Build sẽ tự động chạy khi tạo PR để test compatibility.

## Build Outputs

Mỗi platform sẽ tạo ra các files sau:

### Windows (x64)
- `*.msi` - Windows Installer package
- `*.exe` - NSIS installer

### macOS
- `*.dmg` - Disk image cho cả Intel và Apple Silicon
- `*.app` - Application bundle

### Linux (x64)
- `*.deb` - Debian package  
- `*.AppImage` - Portable application

## Build Local (Development)

### Requirements
- Rust với targets cho platforms muốn build
- Python 3.11+ và PyInstaller
- Bun hoặc npm

### Commands

```bash
# Cài đặt Rust targets
rustup target add x86_64-pc-windows-msvc
rustup target add x86_64-apple-darwin  
rustup target add aarch64-apple-darwin
rustup target add x86_64-unknown-linux-gnu

# Build cho platform hiện tại
cd frontend
bun install
bun run tauri build

# Build cho platform cụ thể (nếu có cross-compilation support)
bun run tauri build --target x86_64-pc-windows-msvc
```

## Cấu Hình Build Scripts

### Python Backend
- **Unix/macOS**: `backend/build_backend.sh`
- **Windows**: `backend/build_backend.ps1`

Scripts sẽ tự động:
- Tạo Python virtual environment
- Install dependencies  
- Build executable với PyInstaller
- Tạo architecture-specific copies cho Tauri

### Frontend
- Build script: `frontend/package.json` → `build:backend`
- Tauri config: `frontend/src-tauri/tauri.conf.json`

## Troubleshooting

### Build Fails trên GitHub Actions

1. Check Actions logs để xem error cụ thể
2. Kiểm tra Python dependencies trong `requirements.txt`
3. Verify Tauri config và permissions

### Local Build Issues

1. Kiểm tra Rust targets đã install:
   ```bash
   rustup target list --installed
   ```

2. Verify Python environment:
   ```bash  
   cd backend
   python --version
   pip list
   ```

3. Check Tauri CLI:
   ```bash
   cd frontend  
   bun run tauri --version
   ```

## Code Signing (Optional)

Để enable code signing cho distribution, cần setup GitHub secrets:
- Xem `/.github/secrets-example.md` để biết chi tiết

## Performance

- Build time: ~15-20 phút cho tất cả platforms
- Parallel builds cho better performance  
- Cached dependencies để speed up subsequent builds
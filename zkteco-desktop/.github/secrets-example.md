# GitHub Secrets Configuration

Để sử dụng GitHub Actions cross-platform build, bạn cần thiết lập các secrets sau trong repository settings:

## Required Secrets

### TAURI_PRIVATE_KEY (Optional - for automatic updates)
```
Tauri private key for code signing and automatic updates
Generate with: tauri signer generate -w ~/.tauri/myapp.key
```

### TAURI_KEY_PASSWORD (Optional)
```
Password for the Tauri private key
Used if the private key is password protected
```

## Optional Secrets for Code Signing

### Windows Code Signing
- `WINDOWS_CERTIFICATE`: Base64 encoded certificate file
- `WINDOWS_CERTIFICATE_PASSWORD`: Certificate password

### macOS Code Signing
- `APPLE_CERTIFICATE`: Base64 encoded certificate
- `APPLE_CERTIFICATE_PASSWORD`: Certificate password
- `APPLE_SIGNING_IDENTITY`: Developer ID Application
- `APPLE_ID`: Apple ID for notarization
- `APPLE_PASSWORD`: App-specific password
- `APPLE_TEAM_ID`: Team ID

## How to Set Secrets

1. Go to your GitHub repository
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with the corresponding value

## Note

- Secrets không bắt buộc để build thành công
- Chỉ cần thiết cho code signing và auto-updates
- Build sẽ hoạt động mà không cần secrets, nhưng sẽ không có code signing
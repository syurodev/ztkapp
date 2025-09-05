# ZKTeco Desktop Manager

A modern desktop application for managing ZKTeco biometric devices with a beautiful GUI built using Tauri, React, and shadcn/ui.

## Features

- 🖥️ **Modern Desktop App**: Built with Tauri for cross-platform compatibility
- 🎨 **Beautiful UI**: Designed with shadcn/ui and Tailwind CSS
- ⚡ **Fast Performance**: Rust backend with React frontend
- 🔧 **Service Management**: Start, stop, and monitor the ZKTeco service
- 👥 **User Management**: CRUD operations for device users
- 🔒 **Fingerprint Management**: Biometric data management
- 📊 **Real-time Monitoring**: Live service metrics and status
- 🌙 **Dark/Light Theme**: Supports both light and dark modes
- 📱 **Responsive Design**: Works on different screen sizes

## Architecture

```
zkteco-desktop/
├── backend/                 # Flask API Service
│   ├── service/            # System service scripts
│   ├── zkteco/            # ZKTeco API modules
│   ├── service_app.py     # Service wrapper
│   └── requirements.txt   # Python dependencies
├── frontend/               # Tauri + React GUI
│   ├── src-tauri/         # Rust Tauri backend
│   ├── src/               # React frontend
│   └── package.json       # Node dependencies
└── build/                  # Build and packaging scripts
```

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (>= 18.0.0)
- **Bun** (latest version)
- **Python** (>= 3.8.0)
- **Rust** (latest stable)
- **Git**

### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install node python rust
curl -fsSL https://bun.sh/install | bash
```

### Windows
```bash
# Install using winget
winget install OpenJS.NodeJS
winget install Python.Python.3
winget install Rustlang.Rustup

# Install Bun
powershell -c "irm bun.sh/install.ps1 | iex"
```

### Linux (Ubuntu/Debian)
```bash
# Install dependencies
sudo apt update
sudo apt install nodejs npm python3 python3-pip curl build-essential

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Bun
curl -fsSL https://bun.sh/install | bash
```

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd zkteco-desktop
   ```

2. **Install dependencies**
   ```bash
   npm run install:all
   ```

3. **Start development**
   ```bash
   # Terminal 1 - Start backend service
   npm run start:backend

   # Terminal 2 - Start frontend development
   npm run start:frontend
   ```

4. **Build for production**
   ```bash
   npm run build
   ```

## Development

### Frontend Development
```bash
cd frontend
bun run dev          # Start Vite dev server
bun run build        # Build for production
bun run tauri dev    # Start Tauri development
bun run tauri build  # Build Tauri app
```

### Backend Development
```bash
cd backend
python service_app.py              # Start service
python -m pytest                   # Run tests
source venv/bin/activate           # Activate virtual environment
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start frontend development server |
| `npm run build` | Build entire application |
| `npm run start:backend` | Start Flask backend service |
| `npm run start:frontend` | Start Tauri frontend |
| `npm run install:all` | Install all dependencies |
| `npm run clean` | Clean build artifacts |
| `npm run lint:frontend` | Lint frontend code |
| `npm run type-check` | TypeScript type checking |

## Configuration

### Backend Configuration

Create a `.env` file in the `backend/` directory:

```env
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=false
DEVICE_IP=192.168.1.100
DEVICE_PORT=4370
PASSWORD=0
USE_MOCK_DEVICE=false
HOST=127.0.0.1
PORT=5001
LOG_LEVEL=INFO
```

### Frontend Configuration

The frontend automatically connects to the backend service running on `http://127.0.0.1:5000`.

## API Endpoints

### Service Management
- `GET /service/status` - Get service status and metrics
- `POST /service/stop` - Stop the service
- `POST /service/restart` - Restart the service
- `GET /service/logs` - Get recent service logs

### User Management
- `GET /users` - Get all users
- `POST /user` - Create a new user
- `DELETE /user/{user_id}` - Delete a user

### Fingerprint Management
- `GET /user/{user_id}/fingerprint/{temp_id}` - Get fingerprint
- `POST /user/{user_id}/fingerprint` - Create fingerprint
- `DELETE /user/{user_id}/fingerprint/{temp_id}` - Delete fingerprint

### Device Management
- `GET /device/capture` - Connect to device

## Deployment

### System Service Installation

#### Linux (systemd)
```bash
cd backend/service
sudo bash install.sh
```

#### macOS (LaunchAgent)
```bash
cd backend/service
bash install.sh
```

#### Windows (Windows Service)
```powershell
cd backend\service\windows
python install_service.py install
python install_service.py start
```

### Application Packaging

The build process creates platform-specific installers:

- **macOS**: `.dmg` and `.app`
- **Windows**: `.msi` and `.exe`
- **Linux**: `.deb`, `.rpm`, and `.AppImage`

Built applications can be found in `frontend/src-tauri/target/release/bundle/`

## Troubleshooting

### Common Issues

1. **Backend service not starting**
   - Check if port 5001 is available
   - Verify Python virtual environment is activated
   - Check `.env` configuration

2. **Frontend build failures**
   - Clear node_modules: `rm -rf frontend/node_modules`
   - Reinstall dependencies: `cd frontend && bun install`
   - Check Rust installation: `rustc --version`

3. **Device connection issues**
   - Verify device IP and port in `.env`
   - Check network connectivity
   - Ensure device is powered on

4. **Permission errors**
   - Run with appropriate permissions
   - Check firewall settings
   - Verify service user permissions

### Debugging

Enable debug mode in backend:
```env
FLASK_DEBUG=true
LOG_LEVEL=DEBUG
```

View frontend console:
- Open Developer Tools in the Tauri window
- Check browser console for errors

### Logs

- **Backend logs**: `/tmp/zkteco-service.log`
- **Frontend logs**: Browser Developer Tools
- **System service logs**: Check systemd/launchd logs

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tauri](https://tauri.app/) - Desktop app framework
- [shadcn/ui](https://ui.shadcn.com/) - UI components
- [ZKTeco](https://www.zkteco.com/) - Biometric device manufacturer
- [PyZK](https://github.com/fananimi/pyzk) - Python library for ZKTeco devices

## Support

If you encounter any issues or have questions, please:

1. Check the [Troubleshooting](#troubleshooting) section
2. Search existing [Issues](https://github.com/yourusername/zkteco-desktop/issues)
3. Create a new issue with detailed information

---

Made with ❤️ using modern web technologies

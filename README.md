# ZKTeco RESTful API Project

This repository contains both the original Flask API and the new Desktop Application.

## Project Structure

```
├── .git/                   # Git repository
├── .idea/                  # IDE settings
├── zkteco-desktop/         # 🆕 Modern Desktop Application
│   ├── backend/           # Flask API service (moved from root)
│   ├── frontend/          # Tauri + React GUI
│   ├── build/             # Build scripts
│   └── README.md          # Desktop app documentation
└── README.md              # This file
```

## Quick Start

### Desktop Application (Recommended)

```bash
cd zkteco-desktop

# Install all dependencies
npm run install:all

# Start development (2 terminals)
npm run start:backend    # Terminal 1: Flask service
npm run start:frontend   # Terminal 2: Tauri GUI

# Or just frontend development
npm run dev
```

### Legacy API Only

If you need to run just the Flask API:

```bash
cd zkteco-desktop/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 service_app.py
```

## Features

- 🖥️ **Desktop GUI**: Modern Tauri application with React
- 🎨 **Beautiful UI**: shadcn/ui components with dark/light theme
- 👥 **User Management**: CRUD operations for ZKTeco users
- 📊 **Real-time Monitoring**: Service status and metrics
- 🔧 **Service Control**: Start/stop/restart backend service
- 🌐 **REST API**: Complete Flask API for device management

## Documentation

For detailed documentation, see [zkteco-desktop/README.md](zkteco-desktop/README.md).

## Migration Notice

The original Flask API files have been moved to `zkteco-desktop/backend/` and enhanced with:
- Service wrapper for system integration
- Real-time monitoring endpoints
- Better error handling
- Production deployment scripts

The desktop GUI provides an intuitive interface for all API functionality.
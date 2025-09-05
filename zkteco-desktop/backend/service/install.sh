#!/bin/bash

# ZKTeco Service Installer Script

set -e

INSTALL_DIR="/opt/zkteco"
SERVICE_USER="zkteco"
CURRENT_DIR="$(dirname "$0")"
BACKEND_DIR="$(dirname "$CURRENT_DIR")"

echo "Installing ZKTeco Service..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# Function to install on Linux
install_linux() {
    echo "Installing on Linux..."
    
    # Create user if not exists
    if ! id "$SERVICE_USER" &>/dev/null; then
        sudo useradd -r -s /bin/false "$SERVICE_USER"
    fi
    
    # Create install directory
    sudo mkdir -p "$INSTALL_DIR"
    
    # Copy files
    sudo cp -r "$BACKEND_DIR"/* "$INSTALL_DIR/"
    sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    
    # Create virtual environment
    sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/venv"
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    # Install systemd service
    sudo cp "$CURRENT_DIR/linux/zkteco.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable zkteco.service
    
    echo "Service installed. Start with: sudo systemctl start zkteco.service"
}

# Function to install on macOS
install_macos() {
    echo "Installing on macOS..."
    
    MACOS_INSTALL_DIR="/Applications/ZKTeco.app/Contents/Resources"
    
    # Create application bundle structure
    sudo mkdir -p "$MACOS_INSTALL_DIR"
    
    # Copy files
    sudo cp -r "$BACKEND_DIR"/* "$MACOS_INSTALL_DIR/"
    
    # Create virtual environment
    python3 -m venv "$MACOS_INSTALL_DIR/venv"
    "$MACOS_INSTALL_DIR/venv/bin/pip" install -r "$MACOS_INSTALL_DIR/requirements.txt"
    
    # Install LaunchAgent
    cp "$CURRENT_DIR/macos/com.zkteco.service.plist" ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.zkteco.service.plist
    
    echo "Service installed. It will start automatically on login."
}

# Install based on OS
case $OS in
    linux)
        install_linux
        ;;
    macos)
        install_macos
        ;;
esac

echo "Installation completed successfully!"
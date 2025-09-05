import os

def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0)."""
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError(f"invalid truth value {val!r}")

SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key-for-desktop-app")
DEBUG = bool(strtobool(os.getenv("FLASK_DEBUG", "false")))

# Use default values for legacy config fields - no config manager import at startup
# These are used only for backward compatibility, new code should use device-specific configs
DEVICE_IP = '192.168.1.201'
DEVICE_PORT = 4370
DEVICE_PASSWORD = 0

LOG_FILE_SIZE = os.getenv("LOG_FILE_SIZE", "10485760")

import logging
import sys
from logging.handlers import RotatingFileHandler
import os


def get_user_log_dir():
    """Get user-writable directory for log files"""
    if os.name == 'nt':  # Windows
        # Use LOCALAPPDATA (e.g., C:\Users\username\AppData\Local\ZKTeco)
        appdata = os.getenv('LOCALAPPDATA')
        if appdata:
            log_dir = os.path.join(appdata, 'ZKTeco')
        else:
            # Fallback to APPDATA
            appdata = os.getenv('APPDATA')
            log_dir = os.path.join(appdata, 'ZKTeco') if appdata else os.path.join(os.path.expanduser('~'), 'ZKTeco')
    else:  # Unix/Linux/macOS
        # Use ~/.local/share/ZKTeco or /tmp as fallback
        log_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', 'ZKTeco')
        if not os.access(os.path.dirname(log_dir), os.W_OK):
            log_dir = '/tmp'
    
    # Create directory if it doesn't exist
    try:
        os.makedirs(log_dir, exist_ok=True)
    except (OSError, PermissionError):
        # Fallback to temp directory
        log_dir = os.path.join(os.path.expanduser('~'), 'zkteco_logs')
        try:
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            # Last resort - current directory
            log_dir = os.getcwd()
    
    return log_dir


def create_log_handler():
    # Log file size from .env or default to 10MB
    log_file_size = int(os.getenv('LOG_FILE_SIZE', 10485760))

    # Set up logging with user-writable directory
    log_dir = get_user_log_dir()
    log_file_path = os.path.join(log_dir, 'app.log')
    handler = RotatingFileHandler(log_file_path, maxBytes=log_file_size, backupCount=3)

    # Define the formatter and set it for the handler
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    handler.setFormatter(formatter)

    return handler


# Create a separate logger instance outside of the Flask app context
app_logger = logging.getLogger(__name__)
app_logger.addHandler(create_log_handler())
app_logger.setLevel(logging.INFO)

# Redirect stdout to the logger's handler
sys.stdout = app_logger.handlers[0].stream

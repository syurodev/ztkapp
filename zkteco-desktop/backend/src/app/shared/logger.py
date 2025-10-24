import logging
import sys
from logging.handlers import RotatingFileHandler
import os


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Special colors for different log types
    CRON_COLOR = "\033[34m"  # Blue for [CRON]
    API_COLOR = "\033[95m"  # Light magenta for API
    DEVICE_COLOR = "\033[96m"  # Light cyan for device

    def format(self, record):
        # Get the original formatted message
        log_message = super().format(record)

        # Color the level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = (
                f"{self.COLORS[levelname]}{self.BOLD}{levelname}{self.RESET}"
            )
            log_message = log_message.replace(levelname, colored_levelname, 1)

        # Color special prefixes
        if "[CRON]" in log_message:
            log_message = log_message.replace(
                "[CRON]", f"{self.CRON_COLOR}[CRON]{self.RESET}"
            )

        if (
            "External API Request" in log_message
            or "External API Response" in log_message
        ):
            log_message = log_message.replace(
                "External API", f"{self.API_COLOR}External API{self.RESET}"
            )

        if (
            "Connected to device" in log_message
            or "Failed to connect to device" in log_message
        ):
            log_message = log_message.replace(
                "device", f"{self.DEVICE_COLOR}device{self.RESET}"
            )

        return log_message


def get_user_log_dir():
    """Get user-writable directory for log files"""
    if os.name == "nt":  # Windows
        # Use LOCALAPPDATA (e.g., C:\Users\username\AppData\Local\ZKTeco)
        appdata = os.getenv("LOCALAPPDATA")
        if appdata:
            log_dir = os.path.join(appdata, "ZKTeco")
        else:
            # Fallback to APPDATA
            appdata = os.getenv("APPDATA")
            log_dir = (
                os.path.join(appdata, "ZKTeco")
                if appdata
                else os.path.join(os.path.expanduser("~"), "ZKTeco")
            )
    else:  # Unix/Linux/macOS
        # Use ~/.local/share/ZKTeco or /tmp as fallback
        log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "ZKTeco")
        if not os.access(os.path.dirname(log_dir), os.W_OK):
            log_dir = "/tmp"

    # Create directory if it doesn't exist
    try:
        os.makedirs(log_dir, exist_ok=True)
    except (OSError, PermissionError):
        # Fallback to temp directory
        log_dir = os.path.join(os.path.expanduser("~"), "zkteco_logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            # Last resort - current directory
            log_dir = os.getcwd()

    return log_dir


def create_log_handler():
    """Create file handler for logging"""
    # Log file size from .env or default to 10MB
    log_file_size = int(os.getenv("LOG_FILE_SIZE", 10485760))

    # Set up logging with user-writable directory
    log_dir = get_user_log_dir()
    log_file_path = os.path.join(log_dir, "app.log")
    handler = RotatingFileHandler(log_file_path, maxBytes=log_file_size, backupCount=3)

    # Define the formatter and set it for the handler (no colors for file)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    handler.setFormatter(formatter)

    return handler


def create_console_handler():
    """Create console handler with colored output"""
    console_handler = logging.StreamHandler(sys.stdout)

    # Use colored formatter for console
    colored_formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(colored_formatter)

    return console_handler


# Create a separate logger instance outside of the Flask app context
app_logger = logging.getLogger(__name__)

# Only add handlers if they haven't been added yet (prevent duplicates on module reload)
if not app_logger.handlers:
    # Add file handler (no colors)
    app_logger.addHandler(create_log_handler())

    # Add console handler (with colors)
    app_logger.addHandler(create_console_handler())

app_logger.setLevel(logging.INFO)

# Prevent propagation to root logger (which might cause duplicates)
app_logger.propagate = False

"""Helper functions for device type checking and operations"""

from typing import Optional
from app.config.config_manager import config_manager


def is_pull_device(device_id: str) -> bool:
    """
    Check if device is pull type (requires TCP connection).

    Pull devices: Traditional ZKTeco devices that require active TCP connection
    Push devices: Modern devices (e.g., SenseFace 4) that push data via HTTP

    Args:
        device_id: The device ID to check

    Returns:
        bool: True if device is pull type, False if push type

    Note:
        - Returns True for unknown devices (backward compatibility)
        - Returns True if device_type field is missing (default to pull)
    """
    if not device_id:
        return True  # Default to pull for backward compatibility

    device = config_manager.get_device(device_id)
    if not device:
        return True  # Default to pull if device not found

    device_type = device.get('device_type', 'pull')
    return device_type == 'pull'


def get_device_type(device_id: str) -> Optional[str]:
    """
    Get the device type (pull or push).

    Args:
        device_id: The device ID to check

    Returns:
        str: 'pull' or 'push', or None if device not found
    """
    if not device_id:
        return None

    device = config_manager.get_device(device_id)
    if not device:
        return None

    return device.get('device_type', 'pull')


def require_pull_device(device_id: str) -> None:
    """
    Raise ValueError if device is not a pull device.

    Use this in functions that require TCP connection.

    Args:
        device_id: The device ID to check

    Raises:
        ValueError: If device is not a pull device

    Example:
        >>> require_pull_device(device_id)  # Raises if not pull device
        >>> # Continue with TCP operations...
    """
    if not is_pull_device(device_id):
        device_type = get_device_type(device_id)
        raise ValueError(
            f"This operation is only supported for pull devices. "
            f"Device type: {device_type}"
        )

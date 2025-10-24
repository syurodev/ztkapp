from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class Device:
    """Device model"""

    id: str
    name: str
    ip: str
    port: int = 4370
    password: int = 0
    timeout: int = 180
    retry_count: int = 3
    retry_delay: int = 2
    ping_interval: int = 30
    force_udp: bool = False
    is_active: bool = True
    is_primary: bool = False  # Only one device can be primary
    device_type: str = "pull"  # 'pull' or 'push'
    device_info: Dict[str, Any] = None
    serial_number: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = asdict(self)

        # Ensure device_info exists
        if not data.get("device_info"):
            data["device_info"] = {}

        # Normalize serial_number and device_name: always put them in device_info
        # This ensures consistent access from frontend regardless of device type

        # Priority for serial_number: device_info.serial_number > column serial_number
        if not data["device_info"].get("serial_number") and self.serial_number:
            data["device_info"]["serial_number"] = self.serial_number

        # Priority for device_name: device_info.device_name > device.name
        if not data["device_info"].get("device_name"):
            data["device_info"]["device_name"] = self.name

        # For push devices, add additional standardized metadata
        if self.device_type == "push":
            # Ensure push device metadata is present
            if "device_type" not in data["device_info"]:
                data["device_info"]["device_type"] = "push"

            # Override with column values to ensure consistency
            data["device_info"]["serial_number"] = (
                self.serial_number or "Pending Registration"
            )
            data["device_info"]["device_name"] = self.name

        return data

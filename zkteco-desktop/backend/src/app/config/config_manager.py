import uuid
from typing import Dict, Any, List, Optional
from app.models import Device
from app.repositories import device_repo, setting_repo


class SQLiteConfigManager:
    """SQLite-based configuration manager - SQLite only, no JSON dependencies"""

    def __init__(self):
        # Initialize database only - no JSON migration needed
        pass

    def get_config(self) -> Dict[str, Any]:
        """Get configuration (for API compatibility)"""
        base_domain = self.get_api_gateway_domain()
        return {
            "API_GATEWAY_DOMAIN": base_domain,
            "EXTERNAL_API_DOMAIN": self.get_external_api_url(),
            "EXTERNAL_API_KEY": self.get_external_api_key(),
            "RESOURCE_DOMAIN": self.get_resource_domain(),
            "active_device_id": self.get_active_device_id(),
            "devices": self.get_all_devices(),
        }

    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Save configuration (for API compatibility)"""
        if (
            "API_GATEWAY_DOMAIN" in config_data
            and config_data["API_GATEWAY_DOMAIN"] is not None
        ):
            api_gateway_domain = self._normalize_gateway_domain(
                config_data.get("API_GATEWAY_DOMAIN")
            )
            setting_repo.set(
                "API_GATEWAY_DOMAIN",
                api_gateway_domain,
                "Base domain for external API and resources",
            )

        if "EXTERNAL_API_KEY" in config_data:
            api_key = config_data["EXTERNAL_API_KEY"]
            setting_repo.set(
                "EXTERNAL_API_KEY", api_key or "", "External API authentication key"
            )

        if "RESOURCE_DOMAIN" in config_data:
            resource_domain = self._normalize_resource_domain(
                config_data.get("RESOURCE_DOMAIN")
            )
            setting_repo.set(
                "RESOURCE_DOMAIN",
                resource_domain,
                "Custom resource domain for static assets (fallback to /short when empty)",
            )

        if "active_device_id" in config_data:
            active_id = config_data["active_device_id"]
            if active_id:
                setting_repo.set(
                    "active_device_id", active_id, "Currently active device ID"
                )

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all devices as list of dictionaries"""
        devices = device_repo.get_all()
        return [device.to_dict() for device in devices]

    def get_active_device(self) -> Optional[Dict[str, Any]]:
        """Get active device as dictionary"""
        active_id = self.get_active_device_id()
        if active_id:
            device = device_repo.get_by_id(active_id)
            return device.to_dict() if device else None
        return None

    def get_active_device_id(self) -> Optional[str]:
        """Get active device ID"""
        return setting_repo.get_value("active_device_id")

    def add_device(self, device_data: Dict[str, Any]) -> str:
        """Add new device with serial_number uniqueness validation"""
        device_id = device_data.get("id") or str(uuid.uuid4())

        # Validate serial_number uniqueness if provided
        serial_number = device_data.get("serial_number")
        if serial_number:
            existing_devices = device_repo.get_all()
            for existing in existing_devices:
                if existing.serial_number == serial_number:
                    raise ValueError(
                        f"Device with serial number '{serial_number}' already exists"
                    )

        device = Device(
            id=device_id,
            name=device_data.get("name", f"Device {device_id}"),
            ip=device_data.get("ip"),
            port=device_data.get("port", 4370),
            password=device_data.get("password", 0),
            timeout=device_data.get("timeout", 30),
            retry_count=device_data.get("retry_count", 3),
            retry_delay=device_data.get("retry_delay", 2),
            ping_interval=device_data.get("ping_interval", 30),
            force_udp=device_data.get("force_udp", False),
            is_active=device_data.get("is_active", True),
            device_type=device_data.get("device_type", "pull"),  # Default to 'pull'
            device_info=device_data.get("device_info", {}),
            serial_number=serial_number,
        )

        created_device = device_repo.create(device)

        # Set as active if no active device or explicitly requested
        current_active = self.get_active_device_id()
        if not current_active or device_data.get("set_as_active", False):
            self.set_active_device(device_id)

        return device_id

    def update_device(self, device_id: str, device_data: Dict[str, Any]) -> bool:
        """Update existing device with serial_number uniqueness validation"""
        # Validate serial_number uniqueness if provided
        serial_number = device_data.get("serial_number")
        if serial_number:
            existing_devices = device_repo.get_all()
            for existing in existing_devices:
                if existing.serial_number == serial_number and existing.id != device_id:
                    raise ValueError(
                        f"Device with serial number '{serial_number}' already exists"
                    )

        return device_repo.update(device_id, device_data)

    def delete_device(self, device_id: str) -> bool:
        """Delete device"""
        from app.shared.logger import app_logger

        try:
            app_logger.info(f"ConfigManager: Starting delete_device for {device_id}")

            # Check if this is the active device
            active_id = self.get_active_device_id()
            app_logger.info(f"ConfigManager: Current active device: {active_id}")

            app_logger.info(f"ConfigManager: Calling device_repo.delete({device_id})")
            success = device_repo.delete(device_id)
            app_logger.info(f"ConfigManager: device_repo.delete returned: {success}")

            if success and active_id == device_id:
                app_logger.info(
                    f"ConfigManager: Deleted device was active, finding new active device"
                )
                # Set new active device if available
                all_devices = device_repo.get_all()
                app_logger.info(
                    f"ConfigManager: Found {len(all_devices)} remaining devices"
                )

                if all_devices:
                    new_active = all_devices[0].id
                    app_logger.info(
                        f"ConfigManager: Setting new active device: {new_active}"
                    )
                    self.set_active_device(new_active)
                else:
                    app_logger.info(
                        f"ConfigManager: No devices left, clearing active device"
                    )
                    setting_repo.set("active_device_id", "", "No active device")

            app_logger.info(
                f"ConfigManager: delete_device completed successfully for {device_id}"
            )
            return success

        except Exception as e:
            app_logger.error(
                f"ConfigManager: Error in delete_device({device_id}): {e}",
                exc_info=True,
            )
            raise

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID"""
        device = device_repo.get_by_id(device_id)
        return device.to_dict() if device else None

    def set_active_device(self, device_id: str) -> bool:
        """Set active device"""
        device = device_repo.get_by_id(device_id)
        if device:
            setting_repo.set(
                "active_device_id", device_id, "Currently active device ID"
            )
            return True
        return False

    def save_device_info(
        self, device_info: Dict[str, Any], device_id: str = None
    ) -> None:
        """Save device info"""
        if device_id:
            device_repo.update(device_id, {"device_info": device_info})

    def get_device_info(self, device_id: str = None) -> Dict[str, Any]:
        """Get device info"""
        if device_id:
            device = device_repo.get_by_id(device_id)
            return device.device_info if device else {}

        # Get active device info
        active_device = self.get_active_device()
        return active_device.get("device_info", {}) if active_device else {}

    def get_api_gateway_domain(self) -> str:
        """Get base API gateway domain shared by services"""
        domain = setting_repo.get_value("API_GATEWAY_DOMAIN") or ""
        return domain.rstrip("/") if domain else ""

    def get_external_api_url(self) -> str:
        """Get external API URL"""
        return self._build_external_api_domain(self.get_api_gateway_domain())

    def get_external_api_key(self) -> str:
        """Get external API key for authentication"""
        return setting_repo.get_value("EXTERNAL_API_KEY") or ""

    def get_resource_domain(self) -> str:
        """Get resource domain for avatar URLs"""
        stored = setting_repo.get_value("RESOURCE_DOMAIN")
        if stored and stored.strip():
            return stored.rstrip("/")
        return self._build_resource_domain(self.get_api_gateway_domain())

    def get_external_api_domain(self) -> str:
        """Alias for get_external_api_url for consistency"""
        return self.get_external_api_url()

    # Additional methods for enhanced functionality
    def get_devices_by_status(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """Get devices filtered by active status"""
        devices = device_repo.get_all()
        filtered = [device for device in devices if device.is_active == is_active]
        return [device.to_dict() for device in filtered]

    # Internal helpers
    @staticmethod
    def _normalize_gateway_domain(domain: Optional[str]) -> str:
        if not domain:
            return ""
        return domain.strip().rstrip("/")

    @staticmethod
    def _normalize_resource_domain(domain: Optional[str]) -> str:
        if not domain:
            return ""
        return domain.strip().rstrip("/")

    def _build_external_api_domain(self, base_domain: str) -> str:
        if not base_domain:
            return ""
        return f"{base_domain.rstrip('/')}/api/v1"

    def _build_resource_domain(self, base_domain: str) -> str:
        if not base_domain:
            return ""
        return f"{base_domain.rstrip('/')}/short"

    def get_device_count(self) -> int:
        """Get total device count"""
        return len(device_repo.get_all())

    def bulk_update_devices(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple devices"""
        updated_count = 0
        for update_data in updates:
            device_id = update_data.pop("id", None)
            if device_id and self.update_device(device_id, update_data):
                updated_count += 1
        return updated_count


# Create global instance using SQLite
config_manager = SQLiteConfigManager()

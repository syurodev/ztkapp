import uuid
from typing import Dict, Any, List, Optional
from zkteco.database.models import Device, device_repo, setting_repo

class SQLiteConfigManager:
    """SQLite-based configuration manager - SQLite only, no JSON dependencies"""
    
    def __init__(self):
        # Initialize database only - no JSON migration needed
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration (for API compatibility)"""
        return {
            'EXTERNAL_API_DOMAIN': self.get_external_api_url(),
            'active_device_id': self.get_active_device_id(),
            'devices': self.get_all_devices()
        }
    
    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Save configuration (for API compatibility)"""
        if 'EXTERNAL_API_DOMAIN' in config_data:
            domain = config_data['EXTERNAL_API_DOMAIN']
            if domain:
                domain = domain.rstrip('/')
            setting_repo.set('EXTERNAL_API_DOMAIN', domain, 'External API domain URL')
        
        if 'active_device_id' in config_data:
            active_id = config_data['active_device_id']
            if active_id:
                setting_repo.set('active_device_id', active_id, 'Currently active device ID')
    
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
        return setting_repo.get('active_device_id')
    
    def add_device(self, device_data: Dict[str, Any]) -> str:
        """Add new device"""
        device_id = device_data.get('id') or str(uuid.uuid4())
        
        device = Device(
            id=device_id,
            name=device_data.get('name', f'Device {device_id}'),
            ip=device_data.get('ip'),
            port=device_data.get('port', 4370),
            password=device_data.get('password', 0),
            timeout=device_data.get('timeout', 10),
            retry_count=device_data.get('retry_count', 3),
            retry_delay=device_data.get('retry_delay', 2),
            ping_interval=device_data.get('ping_interval', 30),
            force_udp=device_data.get('force_udp', False),
            is_active=device_data.get('is_active', True),
            device_info=device_data.get('device_info', {})
        )
        
        created_device = device_repo.create(device)
        
        # Set as active if no active device or explicitly requested
        current_active = self.get_active_device_id()
        if not current_active or device_data.get('set_as_active', False):
            self.set_active_device(device_id)
        
        return device_id
    
    def update_device(self, device_id: str, device_data: Dict[str, Any]) -> bool:
        """Update existing device"""
        return device_repo.update(device_id, device_data)
    
    def delete_device(self, device_id: str) -> bool:
        """Delete device"""
        # Check if this is the active device
        active_id = self.get_active_device_id()
        
        success = device_repo.delete(device_id)
        
        if success and active_id == device_id:
            # Set new active device if available
            all_devices = device_repo.get_all()
            if all_devices:
                self.set_active_device(all_devices[0].id)
            else:
                setting_repo.set('active_device_id', '', 'No active device')
        
        return success
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID"""
        device = device_repo.get_by_id(device_id)
        return device.to_dict() if device else None
    
    def set_active_device(self, device_id: str) -> bool:
        """Set active device"""
        device = device_repo.get_by_id(device_id)
        if device:
            setting_repo.set('active_device_id', device_id, 'Currently active device ID')
            return True
        return False
    
    def save_device_info(self, device_info: Dict[str, Any], device_id: str = None) -> None:
        """Save device info"""
        if device_id:
            device_repo.update(device_id, {'device_info': device_info})
    
    def get_device_info(self, device_id: str = None) -> Dict[str, Any]:
        """Get device info"""
        if device_id:
            device = device_repo.get_by_id(device_id)
            return device.device_info if device else {}
        
        # Get active device info
        active_device = self.get_active_device()
        return active_device.get('device_info', {}) if active_device else {}
    
    def get_external_api_url(self) -> str:
        """Get external API URL"""
        domain = setting_repo.get('EXTERNAL_API_DOMAIN') or ''
        return domain.rstrip('/') if domain else ''
    
    # Additional methods for enhanced functionality
    def get_devices_by_status(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """Get devices filtered by active status"""
        devices = device_repo.get_all()
        filtered = [device for device in devices if device.is_active == is_active]
        return [device.to_dict() for device in filtered]
    
    def get_device_count(self) -> int:
        """Get total device count"""
        return len(device_repo.get_all())
    
    def bulk_update_devices(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple devices"""
        updated_count = 0
        for update_data in updates:
            device_id = update_data.pop('id', None)
            if device_id and self.update_device(device_id, update_data):
                updated_count += 1
        return updated_count

# Create global instance using SQLite
config_manager = SQLiteConfigManager()
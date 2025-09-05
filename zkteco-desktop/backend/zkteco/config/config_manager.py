import json
import os
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.default_config = {
            "EXTERNAL_API_DOMAIN": "",
            "active_device_id": None,
            "devices": []
        }
        try:
            self.config = self.load_config()
        except Exception as e:
            print(f"Warning: Config loading failed: {e}")
            self.config = self.default_config.copy()

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with default to ensure all keys are present
                    result = self.default_config.copy()
                    result.update(config)
                    return result
            except (json.JSONDecodeError, IOError):
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self, config_data: Dict[str, Any]) -> None:
        # Remove trailing slashes from EXTERNAL_API_DOMAIN if present
        if 'EXTERNAL_API_DOMAIN' in config_data and config_data['EXTERNAL_API_DOMAIN']:
            config_data['EXTERNAL_API_DOMAIN'] = config_data['EXTERNAL_API_DOMAIN'].rstrip('/')
        
        self.config.update(config_data)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_config(self) -> Dict[str, Any]:
        return self.config
    
    def get_all_devices(self) -> list:
        return self.config.get('devices', [])
    
    def get_active_device(self) -> Dict[str, Any]:
        active_id = self.config.get('active_device_id')
        if active_id:
            for device in self.get_all_devices():
                if device.get('id') == active_id:
                    return device
        return None
    
    def add_device(self, device_data: Dict[str, Any]) -> str:
        import uuid
        device_id = device_data.get('id') or str(uuid.uuid4())
        
        device = {
            'id': device_id,
            'name': device_data.get('name', f'Device {device_id}'),
            'ip': device_data.get('ip'),
            'port': device_data.get('port', 4370),
            'password': device_data.get('password', 0),
            'timeout': device_data.get('timeout', 10),
            'retry_count': device_data.get('retry_count', 3),
            'retry_delay': device_data.get('retry_delay', 2),
            'ping_interval': device_data.get('ping_interval', 30),
            'force_udp': device_data.get('force_udp', False),
            'is_active': device_data.get('is_active', True),
            'device_info': device_data.get('device_info', {})
        }
        
        self.config['devices'].append(device)
        
        if not self.config.get('active_device_id') or device_data.get('set_as_active', False):
            self.config['active_device_id'] = device_id
            
        self.save_config(self.config)
        return device_id
    
    def update_device(self, device_id: str, device_data: Dict[str, Any]) -> bool:
        devices = self.config.get('devices', [])
        for device in devices:
            if device['id'] == device_id:
                device.update({
                    'name': device_data.get('name', device['name']),
                    'ip': device_data.get('ip', device['ip']),
                    'port': device_data.get('port', device['port']),
                    'password': device_data.get('password', device['password']),
                    'timeout': device_data.get('timeout', device['timeout']),
                    'retry_count': device_data.get('retry_count', device['retry_count']),
                    'retry_delay': device_data.get('retry_delay', device['retry_delay']),
                    'ping_interval': device_data.get('ping_interval', device['ping_interval']),
                    'force_udp': device_data.get('force_udp', device['force_udp']),
                    'is_active': device_data.get('is_active', device['is_active'])
                })
                if 'device_info' in device_data:
                    device['device_info'] = device_data['device_info']
                self.save_config(self.config)
                return True
        return False
    
    def delete_device(self, device_id: str) -> bool:
        devices = self.config.get('devices', [])
        for i, device in enumerate(devices):
            if device['id'] == device_id:
                devices.pop(i)
                if self.config.get('active_device_id') == device_id:
                    self.config['active_device_id'] = None
                    if devices:
                        self.config['active_device_id'] = devices[0]['id']
                self.save_config(self.config)
                return True
        return False
    
    def get_device(self, device_id: str) -> Dict[str, Any]:
        devices = self.config.get('devices', [])
        for device in devices:
            if device['id'] == device_id:
                return device
        return None
    
    def set_active_device(self, device_id: str) -> bool:
        device = self.get_device(device_id)
        if device:
            self.config['active_device_id'] = device_id
            self.save_config(self.config)
            return True
        return False
    
    def save_device_info(self, device_info: Dict[str, Any], device_id: str = None) -> None:
        if device_id:
            device = self.get_device(device_id)
            if device:
                device['device_info'] = device_info
                self.save_config(self.config)
        else:
            # Legacy support
            pass
    
    def get_device_info(self, device_id: str = None) -> Dict[str, Any]:
        if device_id:
            device = self.get_device(device_id)
            return device.get('device_info', {}) if device else {}
        else:
            return {}
    
    def get_external_api_url(self) -> str:
        domain = self.config.get('EXTERNAL_API_DOMAIN', '')
        
        if domain:
            return domain.rstrip('/')
        
        return self.config.get('EXTERNAL_API_URL', '')

config_manager = ConfigManager()
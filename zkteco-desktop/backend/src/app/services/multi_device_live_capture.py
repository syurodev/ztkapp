"""
Multi-Device Live Capture Configuration and Utilities

This module provides configuration management and utilities for multi-device
live capture functionality.
"""

import os
from typing import Dict, List, Any
from app.shared.logger import app_logger

class MultiDeviceConfig:
    """Configuration manager for multi-device live capture"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables and defaults"""
        config = {
            'max_concurrent_devices': int(os.getenv('MAX_CONCURRENT_DEVICES', '10')),
            'device_timeout': int(os.getenv('DEVICE_TIMEOUT', '30')),
            'reconnect_delay': int(os.getenv('RECONNECT_DELAY', '10')),
            'ping_interval': int(os.getenv('PING_INTERVAL', '30')),
            'enable_device_isolation': bool(os.getenv('ENABLE_DEVICE_ISOLATION', 'true').lower() == 'true'),
            'log_device_events': bool(os.getenv('LOG_DEVICE_EVENTS', 'true').lower() == 'true'),
            'auto_start_on_device_add': bool(os.getenv('AUTO_START_ON_DEVICE_ADD', 'false').lower() == 'true'),
            'graceful_shutdown_timeout': int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
        }
        
        app_logger.info(f"Multi-device configuration loaded: {config}")
        return config
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def update(self, key: str, value: Any):
        """Update configuration value"""
        self.config[key] = value
        app_logger.info(f"Updated config: {key} = {value}")

class DeviceHealthMonitor:
    """Monitor device health and connection status"""
    
    def __init__(self):
        self.device_stats = {}  # device_id -> stats
        
    def record_connection(self, device_id: str):
        """Record successful connection"""
        if device_id not in self.device_stats:
            self.device_stats[device_id] = {
                'connections': 0,
                'disconnections': 0,
                'errors': 0,
                'last_connected': None,
                'last_error': None
            }
        
        self.device_stats[device_id]['connections'] += 1
        self.device_stats[device_id]['last_connected'] = self._current_time()
        
    def record_disconnection(self, device_id: str):
        """Record disconnection"""
        if device_id in self.device_stats:
            self.device_stats[device_id]['disconnections'] += 1
            
    def record_error(self, device_id: str, error: str):
        """Record error"""
        if device_id not in self.device_stats:
            self.device_stats[device_id] = {
                'connections': 0,
                'disconnections': 0,
                'errors': 0,
                'last_connected': None,
                'last_error': None
            }
            
        self.device_stats[device_id]['errors'] += 1
        self.device_stats[device_id]['last_error'] = {
            'time': self._current_time(),
            'message': error
        }
    
    def get_device_stats(self, device_id: str) -> Dict[str, Any]:
        """Get statistics for a device"""
        return self.device_stats.get(device_id, {
            'connections': 0,
            'disconnections': 0,
            'errors': 0,
            'last_connected': None,
            'last_error': None
        })
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all devices"""
        return self.device_stats.copy()
    
    def is_device_healthy(self, device_id: str) -> bool:
        """Check if device is considered healthy"""
        if device_id not in self.device_stats:
            return True  # No data yet, assume healthy
            
        stats = self.device_stats[device_id]
        error_rate = stats['errors'] / max(stats['connections'], 1)
        
        # Consider unhealthy if error rate > 50%
        return error_rate < 0.5
    
    def _current_time(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class DeviceSafetyManager:
    """Manage safety features for multi-device operations"""
    
    def __init__(self, config: MultiDeviceConfig):
        self.config = config
        self.device_locks = {}  # device_id -> lock
        
    def validate_device_start(self, device_id: str, active_count: int) -> tuple[bool, str]:
        """Validate if device can be started safely
        
        Returns:
            tuple: (can_start: bool, reason: str)
        """
        # Check max concurrent devices
        max_concurrent = self.config.get('max_concurrent_devices', 10)
        if active_count >= max_concurrent:
            return False, f"Maximum concurrent devices ({max_concurrent}) reached"
        
        # Check if device already has active capture
        if device_id in self.device_locks:
            return False, f"Device {device_id} already has active capture"
            
        return True, "OK"
    
    def can_add_device(self, active_count: int) -> bool:
        """Check if new device can be added"""
        max_concurrent = self.config.get('max_concurrent_devices', 10)
        return active_count < max_concurrent
    
    def should_enable_isolation(self) -> bool:
        """Check if device isolation should be enabled"""
        return self.config.get('enable_device_isolation', True)

# Global instances
multi_device_config = MultiDeviceConfig()
device_health_monitor = DeviceHealthMonitor()
device_safety_manager = DeviceSafetyManager(multi_device_config)

def get_recommended_settings() -> Dict[str, Any]:
    """Get recommended settings for different scenarios"""
    return {
        'development': {
            'max_concurrent_devices': 3,
            'device_timeout': 10,
            'reconnect_delay': 5,
            'log_device_events': True,
            'enable_device_isolation': True
        },
        'production': {
            'max_concurrent_devices': 20,
            'device_timeout': 30,
            'reconnect_delay': 10,
            'log_device_events': False,
            'enable_device_isolation': True
        },
        'testing': {
            'max_concurrent_devices': 5,
            'device_timeout': 5,
            'reconnect_delay': 2,
            'log_device_events': True,
            'enable_device_isolation': False
        }
    }

def apply_settings(environment: str) -> bool:
    """Apply recommended settings for environment"""
    try:
        recommended = get_recommended_settings()
        if environment not in recommended:
            app_logger.error(f"Unknown environment: {environment}")
            return False
            
        settings = recommended[environment]
        for key, value in settings.items():
            multi_device_config.update(key, value)
            
        app_logger.info(f"Applied {environment} settings successfully")
        return True
        
    except Exception as e:
        app_logger.error(f"Error applying settings for {environment}: {e}")
        return False
import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List
from .models import Device, device_repo, setting_repo
from .db_manager import db_manager

class MigrationManager:
    """Handles migration from JSON-based storage to SQLite"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.backup_file = f"{config_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def migrate_from_json(self) -> bool:
        """
        Migrate existing JSON config to SQLite database
        Returns True if migration successful, False if no migration needed
        """
        if not os.path.exists(self.config_file):
            print("No existing config.json found. Starting with fresh database.")
            return False
        
        print(f"Starting migration from {self.config_file} to SQLite...")
        
        try:
            # Backup existing config
            self._backup_config()
            
            # Load existing JSON data
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Migrate devices
            devices_migrated = self._migrate_devices(config_data.get('devices', []))
            
            # Migrate app settings
            settings_migrated = self._migrate_settings(config_data)
            
            # Set active device
            active_device_id = config_data.get('active_device_id')
            if active_device_id:
                setting_repo.set('active_device_id', active_device_id, 'Currently active device ID')
            
            print(f"Migration completed successfully!")
            print(f"- Devices migrated: {devices_migrated}")
            print(f"- Settings migrated: {settings_migrated}")
            print(f"- Active device: {active_device_id or 'None'}")
            print(f"- Backup created: {self.backup_file}")
            
            return True
            
        except Exception as e:
            print(f"Migration failed: {e}")
            # Restore backup if migration fails
            if os.path.exists(self.backup_file):
                shutil.copy2(self.backup_file, self.config_file)
                print("Config restored from backup due to migration failure.")
            raise
    
    def _backup_config(self):
        """Create backup of existing config"""
        shutil.copy2(self.config_file, self.backup_file)
        print(f"Config backed up to: {self.backup_file}")
    
    def _migrate_devices(self, devices_data: List[Dict[str, Any]]) -> int:
        """Migrate devices from JSON to database"""
        migrated_count = 0
        
        for device_data in devices_data:
            try:
                # Create Device object from JSON data
                device = Device(
                    id=device_data.get('id'),
                    name=device_data.get('name', 'Unnamed Device'),
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
                
                # Check if device already exists
                existing = device_repo.get_by_id(device.id)
                if existing:
                    print(f"Device {device.name} already exists, skipping...")
                    continue
                
                # Create device in database
                device_repo.create(device)
                migrated_count += 1
                print(f"Migrated device: {device.name} ({device.ip})")
                
            except Exception as e:
                print(f"Failed to migrate device {device_data.get('name', 'Unknown')}: {e}")
                continue
        
        return migrated_count
    
    def _migrate_settings(self, config_data: Dict[str, Any]) -> int:
        """Migrate app settings from JSON to database"""
        migrated_count = 0
        
        # Migrate known settings
        settings_to_migrate = {
            'EXTERNAL_API_DOMAIN': 'External API domain URL'
        }
        
        for key, description in settings_to_migrate.items():
            if key in config_data:
                value = config_data[key]
                if value:  # Only migrate non-empty values
                    setting_repo.set(key, str(value), description)
                    migrated_count += 1
                    print(f"Migrated setting: {key} = {value}")
        
        return migrated_count
    
    def rollback_migration(self) -> bool:
        """Rollback migration by restoring from backup"""
        if not os.path.exists(self.backup_file):
            print("No backup file found for rollback.")
            return False
        
        try:
            # Remove current config if exists
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            
            # Restore from backup
            shutil.copy2(self.backup_file, self.config_file)
            
            # Remove SQLite database
            if os.path.exists(db_manager.db_path):
                os.remove(db_manager.db_path)
            
            print(f"Migration rolled back successfully. Restored from: {self.backup_file}")
            return True
            
        except Exception as e:
            print(f"Rollback failed: {e}")
            return False
    
    def cleanup_backup(self):
        """Remove backup file after successful migration"""
        if os.path.exists(self.backup_file):
            os.remove(self.backup_file)
            print(f"Backup file removed: {self.backup_file}")

def run_migration(config_file: str = "config.json") -> bool:
    """
    Run migration from JSON to SQLite
    Returns True if migration was performed, False if not needed
    """
    migration_manager = MigrationManager(config_file)
    return migration_manager.migrate_from_json()

if __name__ == "__main__":
    # Run migration when script is executed directly
    print("=== ZKTeco App Migration Tool ===")
    
    try:
        migrated = run_migration()
        if migrated:
            print("\n✅ Migration completed successfully!")
            print("You can now use the SQLite database for all operations.")
        else:
            print("\n✅ Database initialized. No migration needed.")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("Please check the error and try again.")
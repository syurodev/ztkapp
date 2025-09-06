#!/usr/bin/env python3
"""
Simple migration runner script
"""

import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    print("=== ZKTeco SQLite Migration ===")
    
    try:
        # Check if config.json exists
        config_file = "config.json"
        if not os.path.exists(config_file):
            print("❌ No config.json found. Nothing to migrate.")
            return
        
        # Read existing config
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        print(f"📁 Found config.json with {len(config_data.get('devices', []))} devices")
        
        # Initialize database first
        from zkteco.database.db_manager import db_manager
        print("✅ Database initialized")
        
        # Import models and repositories
        from zkteco.database.models import device_repo, setting_repo
        print("✅ Models imported")
        
        # Migrate devices
        devices_migrated = 0
        for device_data in config_data.get('devices', []):
            try:
                # Check if device already exists
                existing = device_repo.get_by_id(device_data.get('id'))
                if existing:
                    print(f"⚠️  Device {device_data.get('name')} already exists, skipping...")
                    continue
                
                # Import Device class for creation
                from zkteco.database.models import Device
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
                
                # Create device
                device_repo.create(device)
                devices_migrated += 1
                print(f"✅ Migrated device: {device.name} ({device.ip})")
                
            except Exception as e:
                print(f"❌ Failed to migrate device {device_data.get('name', 'Unknown')}: {e}")
        
        # Migrate settings
        settings_migrated = 0
        if 'EXTERNAL_API_DOMAIN' in config_data and config_data['EXTERNAL_API_DOMAIN']:
            setting_repo.set('EXTERNAL_API_DOMAIN', config_data['EXTERNAL_API_DOMAIN'], 'External API domain URL')
            settings_migrated += 1
            print(f"✅ Migrated EXTERNAL_API_DOMAIN: {config_data['EXTERNAL_API_DOMAIN']}")
        
        # Set active device
        if 'active_device_id' in config_data and config_data['active_device_id']:
            setting_repo.set('active_device_id', config_data['active_device_id'], 'Currently active device ID')
            print(f"✅ Set active device: {config_data['active_device_id']}")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"   - Devices migrated: {devices_migrated}")
        print(f"   - Settings migrated: {settings_migrated}")
        print(f"   - Active device: {config_data.get('active_device_id', 'None')}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
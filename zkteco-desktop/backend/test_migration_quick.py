#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

def test_quick():
    try:
        # Test import
        from zkteco.config.config_manager_sqlite import config_manager
        print("✅ SQLite config manager imported successfully")
        
        # Test config retrieval
        config = config_manager.get_config()
        print(f"✅ Active device ID: {config.get('active_device_id')}")
        
        # Test devices
        devices = config_manager.get_all_devices()
        print(f"✅ Total devices: {len(devices)}")
        
        if devices:
            print(f"   - First device: {devices[0].get('name')} ({devices[0].get('ip')})")
        
        # Test database connection
        from zkteco.database.db_manager import db_manager
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM devices")
            count = cursor.fetchone()[0]
            print(f"✅ Devices in database: {count}")
        
        print("\n🎉 Migration test PASSED! System is using SQLite successfully.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_quick()
    exit(0 if success else 1)
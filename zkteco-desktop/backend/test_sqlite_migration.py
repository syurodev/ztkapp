#!/usr/bin/env python3
"""
Test script for SQLite database migration and functionality
"""

import os
import sys
import json
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_database_initialization():
    """Test database initialization"""
    print("=== Testing Database Initialization ===")
    
    try:
        from zkteco.database.db_manager import db_manager
        print("✅ Database manager imported successfully")
        print(f"📁 Database path: {os.path.abspath(db_manager.db_path)}")
        
        # Test connection
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"📋 Tables created: {', '.join(tables)}")
            
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def test_models():
    """Test database models"""
    print("\n=== Testing Database Models ===")
    
    try:
        from zkteco.database.models import Device, device_repo, setting_repo
        import uuid
        
        # Test device creation
        test_device = Device(
            id=str(uuid.uuid4()),
            name="Test Device",
            ip="192.168.1.100",
            port=4370,
            device_info={"serial": "TEST123", "firmware": "1.0.0"}
        )
        
        created_device = device_repo.create(test_device)
        print(f"✅ Device created: {created_device.name} ({created_device.id})")
        
        # Test device retrieval
        retrieved_device = device_repo.get_by_id(created_device.id)
        if retrieved_device and retrieved_device.name == test_device.name:
            print("✅ Device retrieval successful")
        else:
            print("❌ Device retrieval failed")
            return False
        
        # Test settings
        setting_repo.set('test_setting', 'test_value', 'Test setting')
        retrieved_value = setting_repo.get('test_setting')
        if retrieved_value == 'test_value':
            print("✅ Settings functionality working")
        else:
            print("❌ Settings functionality failed")
            return False
        
        # Cleanup
        device_repo.delete(created_device.id)
        print("✅ Test cleanup completed")
        
        return True
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False

def create_test_config():
    """Create a test config.json for migration testing"""
    test_config = {
        "EXTERNAL_API_DOMAIN": "https://api.example.com",
        "active_device_id": "test-device-1",
        "devices": [
            {
                "id": "test-device-1",
                "name": "Main Gate",
                "ip": "192.168.1.201",
                "port": 4370,
                "password": 0,
                "timeout": 10,
                "retry_count": 3,
                "retry_delay": 2,
                "ping_interval": 30,
                "force_udp": False,
                "is_active": True,
                "device_info": {
                    "serial_number": "ABC123456",
                    "firmware_version": "1.2.3"
                }
            },
            {
                "id": "test-device-2", 
                "name": "Side Door",
                "ip": "192.168.1.202",
                "port": 4370,
                "password": 0,
                "timeout": 15,
                "retry_count": 5,
                "retry_delay": 3,
                "ping_interval": 60,
                "force_udp": True,
                "is_active": False,
                "device_info": {
                    "serial_number": "DEF789012",
                    "firmware_version": "1.1.8"
                }
            }
        ]
    }
    
    with open('test_config.json', 'w') as f:
        json.dump(test_config, f, indent=2)
    
    print("📝 Test config.json created")
    return test_config

def test_migration():
    """Test migration from JSON to SQLite"""
    print("\n=== Testing Migration ===")
    
    try:
        # Create test config
        test_config = create_test_config()
        
        # Run migration
        from zkteco.database.migration import run_migration
        migrated = run_migration('test_config.json')
        
        if migrated:
            print("✅ Migration completed")
        else:
            print("ℹ️  No migration needed (fresh database)")
        
        # Verify migration results
        from zkteco.database.models import device_repo, setting_repo
        
        devices = device_repo.get_all()
        print(f"📱 Devices in database: {len(devices)}")
        
        for device in devices:
            print(f"   - {device.name} ({device.ip})")
        
        # Check settings
        external_api = setting_repo.get('EXTERNAL_API_DOMAIN')
        active_device = setting_repo.get('active_device_id')
        
        print(f"🔗 External API: {external_api}")
        print(f"🎯 Active device: {active_device}")
        
        # Cleanup test file
        if os.path.exists('test_config.json'):
            os.remove('test_config.json')
            print("🧹 Test config file cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        return False

def test_config_manager():
    """Test SQLite-based config manager"""
    print("\n=== Testing Config Manager ===")
    
    try:
        from zkteco.config.config_manager_sqlite import config_manager
        
        # Test config retrieval
        config = config_manager.get_config()
        print(f"📊 Config keys: {list(config.keys())}")
        
        # Test device operations
        devices = config_manager.get_all_devices()
        print(f"📱 Devices via config manager: {len(devices)}")
        
        # Test active device
        active_device = config_manager.get_active_device()
        if active_device:
            print(f"🎯 Active device: {active_device['name']}")
        else:
            print("🎯 No active device set")
        
        return True
    except Exception as e:
        print(f"❌ Config manager test failed: {e}")
        return False

def test_user_sync_functionality():
    """Test user sync tracking functionality"""
    print("\n=== Testing User Sync Functionality ===")
    
    try:
        from zkteco.database.models import User, user_repo, device_repo
        import uuid
        
        # Create test device first
        test_device_id = str(uuid.uuid4())
        from zkteco.database.models import Device
        test_device = Device(
            id=test_device_id,
            name="Sync Test Device",
            ip="192.168.1.99"
        )
        device_repo.create(test_device)
        
        # Create test user
        test_user = User(
            user_id="TEST001",
            name="Test User",
            device_id=test_device_id,
            privilege=0
        )
        
        created_user = user_repo.create(test_user)
        print(f"✅ User created: {created_user.name} (ID: {created_user.id})")
        print(f"   Sync status: {created_user.is_synced}")
        
        # Test getting unsynced users
        unsynced = user_repo.get_unsynced_users()
        print(f"📝 Unsynced users: {len(unsynced)}")
        
        # Test marking as synced
        success = user_repo.mark_as_synced(created_user.id)
        if success:
            print("✅ User marked as synced")
            
            # Verify sync status
            updated_user = user_repo.get_by_id(created_user.id)
            if updated_user.is_synced:
                print("✅ Sync status verified")
            else:
                print("❌ Sync status not updated")
                return False
        
        # Test marking as unsynced
        user_repo.mark_as_unsynced(created_user.id)
        updated_user = user_repo.get_by_id(created_user.id)
        if not updated_user.is_synced:
            print("✅ User marked as unsynced")
        
        # Cleanup
        user_repo.delete(created_user.id)
        device_repo.delete(test_device_id)
        print("✅ Test cleanup completed")
        
        return True
    except Exception as e:
        print(f"❌ User sync test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 ZKTeco SQLite Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Database Initialization", test_database_initialization),
        ("Database Models", test_models),
        ("Migration", test_migration),
        ("Config Manager", test_config_manager),
        ("User Sync Functionality", test_user_sync_functionality)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! SQLite integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test script for multi-device live capture functionality

This script tests the multi-device live capture implementation
by simulating multiple ZKTeco devices.
"""

import os
import sys
import time
import threading
from typing import List

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from zkteco.services.live_capture_service import (
    multi_device_manager,
    start_multi_device_capture,
    stop_multi_device_capture,
    start_device_capture,
    stop_device_capture,
    get_capture_status
)
from zkteco.services.multi_device_live_capture import (
    multi_device_config,
    device_health_monitor,
    device_safety_manager,
    apply_settings
)
from zkteco.config.config_manager_sqlite import config_manager
from zkteco.logger import app_logger

def setup_test_environment():
    """Setup test environment with mock configuration"""
    print("Setting up test environment...")
    
    # Set environment variables for testing
    os.environ['USE_MOCK_DEVICE'] = 'true'
    os.environ['MAX_CONCURRENT_DEVICES'] = '5'
    os.environ['DEVICE_TIMEOUT'] = '10'
    os.environ['RECONNECT_DELAY'] = '2'
    
    # Apply testing settings
    apply_settings('testing')
    
    print("✓ Test environment configured")

def create_test_devices() -> List[str]:
    """Create test devices in the database"""
    print("Creating test devices...")
    
    test_devices = [
        {
            'id': 'test_device_1',
            'name': 'Test Device 1',
            'ip': '192.168.1.101',
            'port': 4370,
            'password': 0,
            'timeout': 10,
            'is_active': True,
            'serial_number': 'TEST001'
        },
        {
            'id': 'test_device_2', 
            'name': 'Test Device 2',
            'ip': '192.168.1.102',
            'port': 4370,
            'password': 0,
            'timeout': 10,
            'is_active': True,
            'serial_number': 'TEST002'
        },
        {
            'id': 'test_device_3',
            'name': 'Test Device 3',
            'ip': '192.168.1.103',
            'port': 4370,
            'password': 0,
            'timeout': 10,
            'is_active': True,
            'serial_number': 'TEST003'
        }
    ]
    
    device_ids = []
    for device_data in test_devices:
        try:
            # Remove device if exists (cleanup from previous test)
            try:
                config_manager.delete_device(device_data['id'])
            except:
                pass
                
            device_id = config_manager.add_device(device_data)
            device_ids.append(device_id)
            print(f"✓ Created device: {device_data['name']} (ID: {device_id})")
        except Exception as e:
            print(f"✗ Failed to create device {device_data['name']}: {e}")
    
    return device_ids

def test_single_device_capture():
    """Test single device live capture"""
    print("\n=== Testing Single Device Capture ===")
    
    device_ids = create_test_devices()
    if not device_ids:
        print("✗ No devices available for testing")
        return False
        
    device_id = device_ids[0]
    
    print(f"Starting capture for device: {device_id}")
    success = start_device_capture(device_id)
    
    if not success:
        print("✗ Failed to start single device capture")
        return False
        
    # Check status
    time.sleep(2)
    status = get_capture_status()
    print(f"Capture status: {status}")
    
    if status['active_captures'] == 1 and device_id in status['devices']:
        print("✓ Single device capture working correctly")
        result = True
    else:
        print("✗ Single device capture not working")
        result = False
        
    # Stop capture
    stop_device_capture(device_id)
    time.sleep(1)
    
    status = get_capture_status()
    if status['active_captures'] == 0:
        print("✓ Device capture stopped correctly")
    else:
        print("✗ Device capture not stopped properly")
        result = False
        
    return result

def test_multi_device_capture():
    """Test multi-device live capture"""
    print("\n=== Testing Multi-Device Capture ===")
    
    device_ids = create_test_devices()
    if len(device_ids) < 2:
        print("✗ Need at least 2 devices for multi-device test")
        return False
    
    print("Starting multi-device capture...")
    start_multi_device_capture()
    
    # Wait for threads to start
    time.sleep(3)
    
    status = get_capture_status()
    print(f"Multi-device capture status: {status}")
    
    expected_devices = len(device_ids)
    if status['active_captures'] == expected_devices:
        print(f"✓ Multi-device capture started correctly ({expected_devices} devices)")
        result = True
    else:
        print(f"✗ Expected {expected_devices} active captures, got {status['active_captures']}")
        result = False
    
    # Test individual device control
    print("\nTesting individual device stop/start...")
    test_device = device_ids[0]
    
    stop_device_capture(test_device)
    time.sleep(1)
    
    status = get_capture_status()
    if status['active_captures'] == expected_devices - 1:
        print(f"✓ Individual device stop working (devices: {status['active_captures']})")
    else:
        print(f"✗ Individual device stop failed (devices: {status['active_captures']})")
        result = False
    
    start_device_capture(test_device)
    time.sleep(2)
    
    status = get_capture_status()
    if status['active_captures'] == expected_devices:
        print(f"✓ Individual device start working (devices: {status['active_captures']})")
    else:
        print(f"✗ Individual device start failed (devices: {status['active_captures']})")
        result = False
    
    # Stop all
    print("\nStopping all captures...")
    stop_multi_device_capture()
    time.sleep(2)
    
    status = get_capture_status()
    if status['active_captures'] == 0:
        print("✓ All captures stopped correctly")
    else:
        print(f"✗ Some captures still active: {status['active_captures']}")
        result = False
        
    return result

def test_safety_limits():
    """Test safety limits and validation"""
    print("\n=== Testing Safety Limits ===")
    
    # Test max concurrent devices
    original_max = multi_device_config.get('max_concurrent_devices', 10)
    multi_device_config.update('max_concurrent_devices', 2)
    
    device_ids = create_test_devices()
    if len(device_ids) < 3:
        print("✗ Need at least 3 devices for safety test")
        return False
    
    print("Testing max concurrent device limit (set to 2)...")
    
    # Start 2 devices (should work)
    success1 = start_device_capture(device_ids[0])
    success2 = start_device_capture(device_ids[1])
    
    time.sleep(1)
    status = get_capture_status()
    
    if success1 and success2 and status['active_captures'] == 2:
        print("✓ First 2 devices started successfully")
        result = True
    else:
        print("✗ Failed to start first 2 devices")
        result = False
    
    # Try to start 3rd device (should fail)
    success3 = start_device_capture(device_ids[2])
    time.sleep(1)
    status = get_capture_status()
    
    if not success3 and status['active_captures'] == 2:
        print("✓ Safety limit working - 3rd device correctly rejected")
    else:
        print("✗ Safety limit not working - 3rd device was allowed")
        result = False
    
    # Cleanup
    stop_multi_device_capture()
    multi_device_config.update('max_concurrent_devices', original_max)
    
    return result

def test_health_monitoring():
    """Test device health monitoring"""
    print("\n=== Testing Health Monitoring ===")
    
    device_ids = create_test_devices()
    if not device_ids:
        return False
        
    device_id = device_ids[0]
    
    print("Testing health monitoring...")
    
    # Record some events
    device_health_monitor.record_connection(device_id)
    device_health_monitor.record_error(device_id, "Test error")
    device_health_monitor.record_disconnection(device_id)
    
    stats = device_health_monitor.get_device_stats(device_id)
    print(f"Device stats: {stats}")
    
    if (stats['connections'] >= 1 and 
        stats['errors'] >= 1 and 
        stats['disconnections'] >= 1):
        print("✓ Health monitoring recording events correctly")
        return True
    else:
        print("✗ Health monitoring not working")
        return False

def cleanup_test_devices(device_ids: List[str]):
    """Clean up test devices"""
    print("\nCleaning up test devices...")
    
    for device_id in device_ids:
        try:
            config_manager.delete_device(device_id)
            print(f"✓ Deleted device: {device_id}")
        except Exception as e:
            print(f"✗ Failed to delete device {device_id}: {e}")

def main():
    """Run all tests"""
    print("ZKTeco Multi-Device Live Capture Test Suite")
    print("=" * 50)
    
    setup_test_environment()
    
    test_results = []
    device_ids = []
    
    try:
        # Run tests
        test_results.append(("Single Device Capture", test_single_device_capture()))
        test_results.append(("Multi-Device Capture", test_multi_device_capture()))  
        test_results.append(("Safety Limits", test_safety_limits()))
        test_results.append(("Health Monitoring", test_health_monitoring()))
        
        # Store device IDs for cleanup (from last test)
        device_ids = create_test_devices()
        
    except Exception as e:
        print(f"Test execution error: {e}")
        
    finally:
        # Cleanup
        print("\nStopping all captures...")
        stop_multi_device_capture()
        time.sleep(1)
        
        if device_ids:
            cleanup_test_devices(device_ids)
    
    # Results summary
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    print("-" * 50)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
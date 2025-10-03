#!/usr/bin/env python3
"""
Simple test script to verify multi-device API endpoints are working
"""

import requests
import json
import time

# API Configuration
API_BASE_URL = "http://127.0.0.1:57575"

def test_api_connection():
    """Test basic API connection"""
    try:
        response = requests.get(f"{API_BASE_URL}/service/status", timeout=5)
        if response.status_code == 200:
            print("✓ API connection successful")
            return True
        else:
            print(f"✗ API returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to connect to API: {e}")
        return False

def test_get_devices():
    """Test getting all devices"""
    try:
        response = requests.get(f"{API_BASE_URL}/devices", timeout=5)
        if response.status_code == 200:
            data = response.json()
            devices = data.get('devices', [])
            print(f"✓ Retrieved {len(devices)} devices")

            for device in devices:
                print(f"  - {device.get('name')} ({device.get('ip')}:{device.get('port')})")

            return devices
        else:
            print(f"✗ Failed to get devices: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to get devices: {e}")
        return []

def test_capture_status():
    """Test getting capture status"""
    try:
        response = requests.get(f"{API_BASE_URL}/devices/capture/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✓ Capture status retrieved successfully")

            overall_status = data.get('overall_status', {})
            devices_status = data.get('devices', [])

            print(f"  Overall: {overall_status.get('active_captures', 0)} active captures")
            print(f"  Max concurrent: {overall_status.get('max_concurrent', 'N/A')}")

            for device in devices_status:
                status = "Capturing" if device.get('is_capturing') else "Inactive"
                health = "Healthy" if device.get('is_healthy') else "Unhealthy"
                print(f"  - {device.get('device_name')}: {status} ({health})")

            return True
        else:
            print(f"✗ Failed to get capture status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to get capture status: {e}")
        return False

def test_start_all_capture():
    """Test starting all device capture"""
    try:
        response = requests.post(f"{API_BASE_URL}/devices/capture/start-all", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("✓ Started all device capture successfully")
            print(f"  Message: {data.get('message', 'No message')}")
            return True
        else:
            print(f"✗ Failed to start all capture: {response.status_code}")
            if response.text:
                try:
                    error_data = response.json()
                    print(f"  Error: {error_data.get('error', 'Unknown error')}")
                except:
                    print(f"  Raw response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to start all capture: {e}")
        return False

def test_stop_all_capture():
    """Test stopping all device capture"""
    try:
        response = requests.post(f"{API_BASE_URL}/devices/capture/stop-all", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("✓ Stopped all device capture successfully")
            print(f"  Message: {data.get('message', 'No message')}")
            return True
        else:
            print(f"✗ Failed to stop all capture: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to stop all capture: {e}")
        return False

def test_individual_device_capture(device_id, device_name):
    """Test individual device capture start/stop"""
    print(f"\nTesting individual capture for {device_name} ({device_id})")

    # Start capture
    try:
        response = requests.post(f"{API_BASE_URL}/devices/{device_id}/capture/start", timeout=15)
        if response.status_code == 200:
            print(f"✓ Started capture for {device_name}")
        else:
            print(f"✗ Failed to start capture for {device_name}: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to start capture for {device_name}: {e}")
        return False

    # Wait a bit
    time.sleep(2)

    # Stop capture
    try:
        response = requests.post(f"{API_BASE_URL}/devices/{device_id}/capture/stop", timeout=15)
        if response.status_code == 200:
            print(f"✓ Stopped capture for {device_name}")
            return True
        else:
            print(f"✗ Failed to stop capture for {device_name}: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to stop capture for {device_name}: {e}")
        return False

def main():
    """Run all API endpoint tests"""
    print("Multi-Device Live Capture API Test")
    print("=" * 40)

    # Test basic connectivity
    if not test_api_connection():
        print("Cannot connect to API. Make sure the backend is running.")
        return 1

    print()

    # Get devices
    devices = test_get_devices()
    if not devices:
        print("No devices found or failed to retrieve devices.")
        print("Add some devices through the frontend first.")
        return 1

    print()

    # Test capture status
    if not test_capture_status():
        return 1

    print()

    # Test start all capture
    if test_start_all_capture():
        time.sleep(3)  # Wait for captures to start

        # Check status after start
        print("\nChecking status after start all:")
        test_capture_status()

        time.sleep(2)

        # Test stop all
        print()
        if test_stop_all_capture():
            time.sleep(2)

            # Check status after stop
            print("\nChecking status after stop all:")
            test_capture_status()

    # Test individual device control (if devices available)
    if devices and len(devices) > 0:
        device = devices[0]
        device_id = device.get('id')
        device_name = device.get('name', 'Unknown')

        if device_id:
            test_individual_device_capture(device_id, device_name)

    print("\n" + "=" * 40)
    print("API endpoint testing completed!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)

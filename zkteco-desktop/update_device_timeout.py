#!/usr/bin/env python3
"""Update timeout for existing devices in database"""
import sys
import os

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

from zkteco.database.models import device_repo

def update_all_device_timeouts(new_timeout=30):
    """Update timeout for all devices"""
    devices = device_repo.get_all()

    if not devices:
        print("No devices found in database")
        return

    print(f"Found {len(devices)} device(s)")

    for device in devices:
        print(f"\nDevice: {device.name} (ID: {device.id})")
        print(f"  Current timeout: {device.timeout}s")

        # Update timeout
        success = device_repo.update(device.id, {'timeout': new_timeout})

        if success:
            print(f"  OK Updated timeout to: {new_timeout}s")
        else:
            print(f"  ✗ Failed to update timeout")

    print("\nOK All devices updated successfully")

if __name__ == '__main__':
    update_all_device_timeouts(30)

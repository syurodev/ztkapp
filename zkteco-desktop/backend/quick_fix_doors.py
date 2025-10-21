#!/usr/bin/env python3
"""
Quick fix script to restore door-device relationships
Run this after migration fixes to restore data
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "src/app/database/zkteco_app.db"


def main():
    print("=" * 60)
    print("🔧 Door-Device Relationship Fix Script")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    # Backup first
    backup_path = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n📦 Creating backup: {backup_path}")

    import shutil

    shutil.copy2(DB_PATH, backup_path)
    print("✅ Backup created")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get devices
    cursor.execute(
        "SELECT id, name FROM devices WHERE deleted_at IS NULL ORDER BY created_at"
    )
    devices = cursor.fetchall()

    if not devices:
        print("\n❌ No devices found in database!")
        conn.close()
        return

    print(f"\n📱 Found {len(devices)} device(s):")
    for i, (dev_id, dev_name) in enumerate(devices, 1):
        print(f"  {i}. {dev_name}")
        print(f"     ID: {dev_id}")

    # Get doors
    cursor.execute("SELECT id, name, device_id FROM doors ORDER BY id")
    doors = cursor.fetchall()

    if not doors:
        print("\n❌ No doors found in database!")
        conn.close()
        return

    print(f"\n🚪 Found {len(doors)} door(s):")
    for door_id, door_name, device_id in doors:
        status = "✅" if device_id else "❌"
        print(f"  {status} {door_name} → {device_id or 'NOT ASSIGNED'}")

    # Count doors without device_id
    unassigned = [d for d in doors if not d[2]]

    if not unassigned:
        print("\n✅ All doors are already assigned to devices!")
        conn.close()
        return

    print(f"\n⚠️  {len(unassigned)} door(s) need device assignment")

    # Interactive assignment
    print("\n" + "=" * 60)
    print("Assignment Mode")
    print("=" * 60)

    for door_id, door_name, _ in unassigned:
        print(f"\n🚪 Door: '{door_name}' (ID: {door_id})")
        print("Available devices:")
        for i, (dev_id, dev_name) in enumerate(devices, 1):
            print(f"  {i}. {dev_name}")

        while True:
            choice = input(
                f"\nAssign to device (1-{len(devices)}) or 's' to skip: "
            ).strip()

            if choice.lower() == "s":
                print(f"⏭️  Skipped {door_name}")
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(devices):
                    device_id, device_name = devices[idx]

                    # Update database
                    cursor.execute(
                        "UPDATE doors SET device_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (device_id, door_id),
                    )

                    print(f"✅ Assigned '{door_name}' → '{device_name}'")
                    break
                else:
                    print("❌ Invalid choice, try again")
            except ValueError:
                print("❌ Invalid input, try again")

    # Commit changes
    conn.commit()

    # Verify
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)

    cursor.execute("""
        SELECT
            d.id,
            d.name as door_name,
            d.device_id,
            dev.name as device_name
        FROM doors d
        LEFT JOIN devices dev ON d.device_id = dev.id
        ORDER BY d.id
    """)

    results = cursor.fetchall()
    all_assigned = True

    for door_id, door_name, device_id, device_name in results:
        if device_id:
            print(f"✅ {door_name} → {device_name}")
        else:
            print(f"❌ {door_name} → NOT ASSIGNED")
            all_assigned = False

    conn.close()

    print("\n" + "=" * 60)
    if all_assigned:
        print("🎉 SUCCESS! All doors are now assigned to devices")
    else:
        print("⚠️  Some doors are still unassigned")
        print("   You can run this script again or assign manually via UI")
    print("=" * 60)
    print(f"\n💾 Backup saved at: {backup_path}")
    print("   Restore with: cp {backup_path} {DB_PATH}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

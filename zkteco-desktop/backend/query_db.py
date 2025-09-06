#!/usr/bin/env python3
"""
Simple database query script for ZKTeco SQLite database
"""

import sqlite3
import json
import sys
from datetime import datetime

def connect_db(db_path="zkteco_app.db"):
    """Connect to SQLite database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def show_devices():
    """Show all devices"""
    print("🔍 DEVICES")
    print("=" * 80)
    
    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, ip, port, is_active, device_info, created_at 
            FROM devices 
            ORDER BY created_at DESC
        """)
        
        for row in cursor.fetchall():
            device_info = json.loads(row['device_info']) if row['device_info'] else {}
            status = "🟢 Active" if row['is_active'] else "🔴 Inactive"
            
            print(f"ID: {row['id']}")
            print(f"Name: {row['name']}")
            print(f"Address: {row['ip']}:{row['port']}")
            print(f"Status: {status}")
            print(f"Serial: {device_info.get('serial_number', 'N/A')}")
            print(f"Created: {row['created_at']}")
            print("-" * 80)

def show_settings():
    """Show all app settings"""
    print("\n⚙️  APP SETTINGS")
    print("=" * 80)
    
    with connect_db() as conn:
        cursor = conn.execute("SELECT * FROM app_settings ORDER BY updated_at DESC")
        
        for row in cursor.fetchall():
            print(f"{row['key']}: {row['value']}")
            if row['description']:
                print(f"  Description: {row['description']}")
            print(f"  Updated: {row['updated_at']}")
            print("-" * 40)

def show_users():
    """Show all users"""
    print("\n👤 USERS")
    print("=" * 80)
    
    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT user_id, name, device_id, is_synced, synced_at, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        if not users:
            print("No users found.")
            return
            
        for row in users:
            sync_status = "✅ Synced" if row['is_synced'] else "⏳ Not synced"
            print(f"User ID: {row['user_id']}")
            print(f"Name: {row['name']}")
            print(f"Device: {row['device_id']}")
            print(f"Sync Status: {sync_status}")
            print(f"Created: {row['created_at']}")
            print("-" * 40)

def show_attendance_logs(limit=10):
    """Show recent attendance logs"""
    print(f"\n📋 RECENT ATTENDANCE LOGS (Last {limit})")
    print("=" * 80)
    
    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT user_id, device_id, timestamp, method, action, created_at 
            FROM attendance_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        logs = cursor.fetchall()
        if not logs:
            print("No attendance logs found.")
            return
            
        for row in logs:
            method_name = {1: "Fingerprint", 4: "Card"}.get(row['method'], "Unknown")
            action_name = {
                0: "Check In", 1: "Check Out", 
                2: "Overtime Start", 3: "Overtime End", 
                4: "Unspecified"
            }.get(row['action'], "Unknown")
            
            print(f"User: {row['user_id']}")
            print(f"Device: {row['device_id']}")
            print(f"Time: {row['timestamp']}")
            print(f"Method: {method_name}")
            print(f"Action: {action_name}")
            print("-" * 40)

def show_stats():
    """Show database statistics"""
    print("\n📊 DATABASE STATISTICS")
    print("=" * 80)
    
    with connect_db() as conn:
        # Count devices
        cursor = conn.execute("SELECT COUNT(*) as count FROM devices")
        device_count = cursor.fetchone()['count']
        
        # Count users
        cursor = conn.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        
        # Count attendance logs
        cursor = conn.execute("SELECT COUNT(*) as count FROM attendance_logs")
        log_count = cursor.fetchone()['count']
        
        # Count settings
        cursor = conn.execute("SELECT COUNT(*) as count FROM app_settings")
        setting_count = cursor.fetchone()['count']
        
        print(f"📱 Devices: {device_count}")
        print(f"👥 Users: {user_count}")
        print(f"📋 Attendance Logs: {log_count}")
        print(f"⚙️  Settings: {setting_count}")

def custom_query(sql):
    """Execute custom SQL query"""
    print(f"\n🔍 CUSTOM QUERY: {sql}")
    print("=" * 80)
    
    try:
        with connect_db() as conn:
            cursor = conn.execute(sql)
            results = cursor.fetchall()
            
            if not results:
                print("No results found.")
                return
                
            # Print column headers
            columns = [description[0] for description in cursor.description]
            print(" | ".join(columns))
            print("-" * (len(" | ".join(columns)) + 10))
            
            # Print data
            for row in results:
                print(" | ".join(str(row[col]) for col in columns))
                
    except Exception as e:
        print(f"❌ Query failed: {e}")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "devices":
            show_devices()
        elif command == "users":
            show_users()
        elif command == "settings":
            show_settings()
        elif command == "logs":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            show_attendance_logs(limit)
        elif command == "stats":
            show_stats()
        elif command == "query":
            if len(sys.argv) > 2:
                custom_query(" ".join(sys.argv[2:]))
            else:
                print("Usage: python query_db.py query 'SELECT * FROM devices'")
        else:
            print("Unknown command. Use: devices, users, settings, logs, stats, query")
    else:
        print("🚀 ZKTeco Database Query Tool")
        print("=" * 80)
        show_stats()
        show_devices()
        show_settings()
        show_users()
        show_attendance_logs(5)
        
        print("\n💡 Usage:")
        print("python query_db.py devices     # Show all devices")
        print("python query_db.py users       # Show all users") 
        print("python query_db.py settings    # Show all settings")
        print("python query_db.py logs [N]    # Show last N attendance logs")
        print("python query_db.py stats       # Show statistics")
        print("python query_db.py query 'SQL' # Execute custom SQL")

if __name__ == "__main__":
    main()
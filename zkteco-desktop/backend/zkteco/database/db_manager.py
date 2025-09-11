import sqlite3
import os
import threading
from contextlib import contextmanager
from typing import Optional, Any, Dict, List
from datetime import datetime

class DatabaseManager:
    """SQLite database manager for ZKTeco application"""
    
    def __init__(self, db_path: str = "zkteco_app.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys and row factory
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database operations"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            cursor.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_cursor() as cursor:
            # Devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    port INTEGER DEFAULT 4370,
                    password INTEGER DEFAULT 0,
                    timeout INTEGER DEFAULT 10,
                    retry_count INTEGER DEFAULT 3,
                    retry_delay INTEGER DEFAULT 2,
                    ping_interval INTEGER DEFAULT 30,
                    force_udp BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    device_info TEXT, -- JSON string for device info
                    serial_number TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Users table with sync tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    device_id TEXT,
                    serial_number TEXT,
                    privilege INTEGER DEFAULT 0,
                    group_id INTEGER DEFAULT 0,
                    card INTEGER DEFAULT 0,
                    password TEXT DEFAULT '',
                    is_synced BOOLEAN DEFAULT FALSE,
                    synced_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Attendance logs table with sync tracking and duplicate prevention
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    device_id TEXT,
                    serial_number TEXT,
                    timestamp DATETIME NOT NULL,
                    method INTEGER NOT NULL, -- 1: fingerprint, 4: card
                    action INTEGER NOT NULL, -- 0: checkin, 1: checkout, 2: overtime start, 3: overtime end, 4: unspecified
                    raw_data TEXT, -- JSON string for raw attendance data
                    is_synced BOOLEAN DEFAULT FALSE,
                    synced_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_attendance UNIQUE(user_id, device_id, timestamp, method, action)
                )
            ''')
            
            # App settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migrate existing tables to add new columns
            self._migrate_devices_table(cursor)
            self._migrate_users_table(cursor)
            self._migrate_attendance_logs_table(cursor)
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_device_id ON users(device_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_sync_status ON users(is_synced)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON attendance_logs(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_device_id ON attendance_logs(device_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance_logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_sync_status ON attendance_logs(is_synced)')
            
            print(f"Database initialized at: {os.path.abspath(self.db_path)}")
    
    def _migrate_devices_table(self, cursor):
        """Migrate existing devices table to add serial_number column"""
        # Check if column already exists
        cursor.execute("PRAGMA table_info(devices)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'serial_number' not in columns:
            try:
                print("Adding serial_number column to devices table...")
                # Add column without UNIQUE constraint first (SQLite limitation)
                cursor.execute('ALTER TABLE devices ADD COLUMN serial_number TEXT')
                print("serial_number column added successfully")
            except Exception as e:
                print(f"Warning: Could not add serial_number column: {e}")
                print("This may be normal if the column already exists in some form")
    
    def _migrate_users_table(self, cursor):
        """Migrate existing users table to add serial_number column"""
        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'serial_number' not in columns:
            try:
                print("Adding serial_number column to users table...")
                cursor.execute('ALTER TABLE users ADD COLUMN serial_number TEXT')
                print("serial_number column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add serial_number column to users table: {e}")
                print("This may be normal if the column already exists in some form")
    
    def _migrate_attendance_logs_table(self, cursor):
        """Migrate existing attendance_logs table to add sync tracking columns and unique constraint"""
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(attendance_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'serial_number' not in columns:
            try:
                print("Adding serial_number column to attendance_logs table...")
                cursor.execute('ALTER TABLE attendance_logs ADD COLUMN serial_number TEXT')
                print("serial_number column added to attendance_logs table successfully")
            except Exception as e:
                print(f"Warning: Could not add serial_number column to attendance_logs table: {e}")
        
        if 'is_synced' not in columns:
            print("Adding is_synced column to attendance_logs table...")
            cursor.execute('ALTER TABLE attendance_logs ADD COLUMN is_synced BOOLEAN DEFAULT FALSE')
            
        if 'synced_at' not in columns:
            print("Adding synced_at column to attendance_logs table...")
            cursor.execute('ALTER TABLE attendance_logs ADD COLUMN synced_at DATETIME NULL')
        
        # Check if unique constraint already exists
        cursor.execute("PRAGMA index_list(attendance_logs)")
        constraints = cursor.fetchall()
        
        unique_constraint_exists = False
        for constraint in constraints:
            if 'unique_attendance' in constraint[1]:
                unique_constraint_exists = True
                break
        
        if not unique_constraint_exists:
            try:
                print("Adding unique constraint to prevent duplicate attendance records...")
                # Note: SQLite doesn't support adding constraints to existing tables directly
                # We'll create a unique index instead, which provides the same functionality
                cursor.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS unique_attendance 
                    ON attendance_logs(user_id, device_id, timestamp, method, action)
                ''')
                print("Unique constraint added successfully")
            except Exception as e:
                # If constraint creation fails due to existing duplicates, log it
                print(f"Warning: Could not add unique constraint due to existing duplicates: {e}")
                print("Please clean up duplicate records manually if needed")
    
    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single query"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Fetch single row"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Fetch all rows"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def close_connection(self):
        """Close thread-local connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection

# Global database manager instance
db_manager = DatabaseManager()
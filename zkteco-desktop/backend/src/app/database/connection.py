import sqlite3
import os
import threading
import atexit
from contextlib import contextmanager
from typing import Optional, Any, Dict, List, Set
from datetime import datetime


class DatabaseManager:
    """SQLite database manager for ZKTeco application"""

    def __init__(self, db_path: str = "zkteco_app.db"):
        env_db_path = os.environ.get("ZKTECO_DB_PATH")
        resolved_path = env_db_path if env_db_path else db_path

        if not os.path.isabs(resolved_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            resolved_path = os.path.join(base_dir, resolved_path)

        db_directory = os.path.dirname(resolved_path)
        if db_directory:
            try:
                os.makedirs(db_directory, exist_ok=True)
            except OSError as exc:
                raise RuntimeError(
                    f"Unable to create database directory '{db_directory}': {exc}"
                ) from exc

        self.db_path = resolved_path
        self._local = threading.local()
        self._connections: Set[sqlite3.Connection] = (
            set()
        )  # Track all connections for cleanup
        self._lock = threading.Lock()

        # Register cleanup on exit
        atexit.register(self.close_all_connections)

        # Clean up stale WAL files before initializing database
        self._cleanup_stale_wal_files()

        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            # Enable performance-oriented pragmas. WAL improves concurrent access, while
            # NORMAL synchronous/cache/temp settings trade a little durability for speed.
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.row_factory = sqlite3.Row

            # Store connection in thread-local storage
            self._local.connection = conn

            # Track connection for cleanup
            with self._lock:
                self._connections.add(conn)

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
            cursor.execute("""
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
                    is_primary BOOLEAN DEFAULT FALSE, -- Only one device can be primary
                    device_type TEXT DEFAULT 'pull', -- 'pull' or 'push'
                    device_info TEXT, -- JSON string for device info
                    serial_number TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Users table with sync tracking
            cursor.execute("""
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
                    external_user_id INTEGER NULL,
                    avatar_url TEXT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Attendance logs table with sync tracking and duplicate prevention
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    device_id TEXT,
                    serial_number TEXT,
                    timestamp DATETIME NOT NULL,
                    method INTEGER NOT NULL, -- 1: fingerprint, 4: card
                    action INTEGER NOT NULL, -- 0: checkin, 1: checkout, 2: overtime start, 3: overtime end, 4: unspecified
                    raw_data TEXT, -- JSON string for raw attendance data
                    sync_status TEXT DEFAULT 'pending', -- pending, synced, skipped
                    is_synced BOOLEAN DEFAULT FALSE, -- kept for backward compatibility
                    synced_at DATETIME NULL,
                    error_code TEXT NULL,
                    error_message TEXT NULL,
                    original_status INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_attendance UNIQUE(user_id, device_id, timestamp, method, action)
                )
            """)

            # App settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrate existing tables to add new columns
            self._migrate_devices_table(cursor)
            self._migrate_users_table(cursor)
            self._migrate_attendance_logs_table(cursor)

            # Create indexes for better performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_device_id ON users(device_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_sync_status ON users(is_synced)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON attendance_logs(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_device_id ON attendance_logs(device_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance_logs(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_sync_status ON attendance_logs(is_synced)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_sync_status_new ON attendance_logs(sync_status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_date_action ON attendance_logs(DATE(timestamp), action)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_logs(user_id, DATE(timestamp))"
            )

            print(f"Database initialized at: {os.path.abspath(self.db_path)}")

    def _migrate_devices_table(self, cursor):
        """Migrate existing devices table to add serial_number, device_type and is_primary columns"""
        # Check if column already exists
        cursor.execute("PRAGMA table_info(devices)")
        columns = [column[1] for column in cursor.fetchall()]

        if "serial_number" not in columns:
            try:
                print("Adding serial_number column to devices table...")
                # Add column without UNIQUE constraint first (SQLite limitation)
                cursor.execute("ALTER TABLE devices ADD COLUMN serial_number TEXT")
                print("serial_number column added successfully")
            except Exception as e:
                print(f"Warning: Could not add serial_number column: {e}")
                print("This may be normal if the column already exists in some form")

        if "device_type" not in columns:
            try:
                print("Adding device_type column to devices table...")
                cursor.execute(
                    "ALTER TABLE devices ADD COLUMN device_type TEXT DEFAULT 'pull'"
                )
                print("device_type column added successfully")

                # Update existing devices to have 'pull' type
                cursor.execute(
                    "UPDATE devices SET device_type = 'pull' WHERE device_type IS NULL"
                )
                print("Existing devices set to 'pull' type")
            except Exception as e:
                print(f"Warning: Could not add device_type column: {e}")
                print("This may be normal if the column already exists in some form")

        if "is_primary" not in columns:
            try:
                print("Adding is_primary column to devices table...")
                cursor.execute(
                    "ALTER TABLE devices ADD COLUMN is_primary BOOLEAN DEFAULT FALSE"
                )
                print("is_primary column added successfully")

                # Set the first active device as primary if no primary device exists
                cursor.execute("SELECT COUNT(*) FROM devices WHERE is_primary = TRUE")
                primary_count = cursor.fetchone()[0]

                if primary_count == 0:
                    cursor.execute(
                        "UPDATE devices SET is_primary = TRUE WHERE id = (SELECT id FROM devices WHERE is_active = TRUE LIMIT 1)"
                    )
                    print("Set first active device as primary")
            except Exception as e:
                print(f"Warning: Could not add is_primary column: {e}")
                print("This may be normal if the column already exists in some form")

    def _migrate_users_table(self, cursor):
        """Migrate existing users table to add new columns"""
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if "serial_number" not in columns:
            try:
                print("Adding serial_number column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN serial_number TEXT")
                print("serial_number column added to users table successfully")
            except Exception as e:
                print(
                    f"Warning: Could not add serial_number column to users table: {e}"
                )
                print("This may be normal if the column already exists in some form")

        if "external_user_id" not in columns:
            try:
                print("Adding external_user_id column to users table...")
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN external_user_id INTEGER NULL"
                )
                print("external_user_id column added to users table successfully")
            except Exception as e:
                print(
                    f"Warning: Could not add external_user_id column to users table: {e}"
                )

        if "avatar_url" not in columns:
            try:
                print("Adding avatar_url column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT NULL")
                print("avatar_url column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add avatar_url column to users table: {e}")

        # Add new fields for employee information
        if "full_name" not in columns:
            try:
                print("Adding full_name column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT NULL")
                print("full_name column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add full_name column to users table: {e}")

        if "employee_code" not in columns:
            try:
                print("Adding employee_code column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN employee_code TEXT NULL")
                print("employee_code column added to users table successfully")
            except Exception as e:
                print(
                    f"Warning: Could not add employee_code column to users table: {e}"
                )

        if "position" not in columns:
            try:
                print("Adding position column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN position TEXT NULL")
                print("position column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add position column to users table: {e}")

        if "department" not in columns:
            try:
                print("Adding department column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN department TEXT NULL")
                print("department column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add department column to users table: {e}")

        if "notes" not in columns:
            try:
                print("Adding notes column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN notes TEXT NULL")
                print("notes column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add notes column to users table: {e}")

        if "employee_object" not in columns:
            try:
                print("Adding employee_object column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN employee_object TEXT NULL")
                print("employee_object column added to users table successfully")
            except Exception as e:
                print(
                    f"Warning: Could not add employee_object column to users table: {e}"
                )

        if "gender" not in columns:
            try:
                print("Adding gender column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT NULL")
                print("gender column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add gender column to users table: {e}")

        if "hire_date" not in columns:
            try:
                print("Adding hire_date column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN hire_date TEXT NULL")
                print("hire_date column added to users table successfully")
            except Exception as e:
                print(f"Warning: Could not add hire_date column to users table: {e}")

    def _migrate_attendance_logs_table(self, cursor):
        """Migrate existing attendance_logs table to add sync tracking columns and unique constraint"""
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(attendance_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        column_names = [column[1] for column in cursor.fetchall()]

        if "serial_number" not in columns:
            try:
                print("Adding serial_number column to attendance_logs table...")
                cursor.execute(
                    "ALTER TABLE attendance_logs ADD COLUMN serial_number TEXT"
                )
                print(
                    "serial_number column added to attendance_logs table successfully"
                )
            except Exception as e:
                print(
                    f"Warning: Could not add serial_number column to attendance_logs table: {e}"
                )

        # Handle migration from is_synced to sync_status
        if "sync_status" not in columns:
            if "is_synced" in columns:
                print("Migrating from is_synced to sync_status...")
                # Add new sync_status column
                cursor.execute(
                    'ALTER TABLE attendance_logs ADD COLUMN sync_status TEXT DEFAULT "pending"'
                )

                # Migrate existing data: is_synced=1 -> 'synced', is_synced=0 -> 'pending'
                cursor.execute("""
                    UPDATE attendance_logs
                    SET sync_status = CASE
                        WHEN is_synced = 1 THEN 'synced'
                        ELSE 'pending'
                    END
                """)
                print("Data migrated from is_synced to sync_status successfully")

                # Note: We keep is_synced column for backward compatibility during transition
                print("Note: is_synced column kept for backward compatibility")
            else:
                print("Adding sync_status column to attendance_logs table...")
                cursor.execute(
                    'ALTER TABLE attendance_logs ADD COLUMN sync_status TEXT DEFAULT "pending"'
                )

        if "is_synced" not in columns:
            print("Adding is_synced column to attendance_logs table...")
            cursor.execute(
                "ALTER TABLE attendance_logs ADD COLUMN is_synced BOOLEAN DEFAULT FALSE"
            )

        if "synced_at" not in columns:
            print("Adding synced_at column to attendance_logs table...")
            cursor.execute(
                "ALTER TABLE attendance_logs ADD COLUMN synced_at DATETIME NULL"
            )

        # Add error tracking columns for sync error handling
        if "error_code" not in columns:
            print("Adding error_code column to attendance_logs table...")
            cursor.execute(
                "ALTER TABLE attendance_logs ADD COLUMN error_code TEXT NULL"
            )

        if "error_message" not in columns:
            print("Adding error_message column to attendance_logs table...")
            cursor.execute(
                "ALTER TABLE attendance_logs ADD COLUMN error_message TEXT NULL"
            )

        # Add original_status column for tracking original STATUS from device
        if "original_status" not in columns:
            try:
                print("Adding original_status column to attendance_logs table...")
                cursor.execute(
                    "ALTER TABLE attendance_logs ADD COLUMN original_status INTEGER DEFAULT 0"
                )
                print(
                    "original_status column added to attendance_logs table successfully"
                )
            except Exception as e:
                print(
                    f"Warning: Could not add original_status column to attendance_logs table: {e}"
                )

        if "error_count" not in columns:
            try:
                print("Adding error_count column to attendance_logs table...")
                cursor.execute(
                    "ALTER TABLE attendance_logs ADD COLUMN error_count INTEGER DEFAULT 0"
                )
                cursor.execute(
                    "UPDATE attendance_logs SET error_count = 0 WHERE error_count IS NULL"
                )
                print("error_count column added to attendance_logs table successfully")
            except Exception as e:
                print(
                    f"Warning: Could not add error_count column to attendance_logs table: {e}"
                )

        # Check if unique constraint already exists
        cursor.execute("PRAGMA index_list(attendance_logs)")
        constraints = cursor.fetchall()

        unique_constraint_exists = False
        for constraint in constraints:
            if "unique_attendance" in constraint[1]:
                unique_constraint_exists = True
                break

        if not unique_constraint_exists:
            try:
                print(
                    "Adding unique constraint to prevent duplicate attendance records..."
                )
                # Note: SQLite doesn't support adding constraints to existing tables directly
                # We'll create a unique index instead, which provides the same functionality
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS unique_attendance
                    ON attendance_logs(user_id, device_id, timestamp, method, action)
                """)
                print("Unique constraint added successfully")
            except Exception as e:
                # If constraint creation fails due to existing duplicates, log it
                print(
                    f"Warning: Could not add unique constraint due to existing duplicates: {e}"
                )
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
        if hasattr(self._local, "connection") and self._local.connection is not None:
            try:
                conn = self._local.connection
                conn.close()

                # Remove from tracking set
                with self._lock:
                    self._connections.discard(conn)
            except Exception as e:
                print(f"Error closing thread-local connection: {e}")
            finally:
                self._local.connection = None

    def close_all_connections(self):
        """Close all tracked connections - called on shutdown"""
        print("DatabaseManager: Closing all connections...")
        closed_count = 0
        error_count = 0

        with self._lock:
            # Create a list copy to avoid modification during iteration
            connections_to_close = list(self._connections)
            # Clear the set
            self._connections.clear()

        for conn in connections_to_close:
            try:
                conn.close()
                closed_count += 1
            except Exception as e:
                error_count += 1
                print(f"Error closing connection: {e}")

        print(
            f"DatabaseManager: Closed {closed_count} connections, {error_count} errors"
        )

    def _checkpoint_wal(self):
        """Checkpoint WAL file to flush all data to main database"""
        try:
            # Get a connection to perform checkpoint
            conn = self.get_connection()
            cursor = conn.cursor()

            # PRAGMA wal_checkpoint(TRUNCATE) will:
            # 1. Move all WAL data into the main database
            # 2. Truncate the WAL file to zero bytes
            # 3. Reset the WAL file for reuse
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = cursor.fetchone()

            if result:
                # Result: (busy, log_frames, checkpointed_frames)
                print(f"WAL checkpoint completed: {result[2]} frames checkpointed")

            cursor.close()
        except Exception as e:
            print(f"Warning: Failed to checkpoint WAL: {e}")
            # Don't raise - this is a best-effort operation

    def _cleanup_stale_wal_files(self):
        """Clean up stale WAL and SHM files from previous crashes"""
        wal_file = f"{self.db_path}-wal"
        shm_file = f"{self.db_path}-shm"

        try:
            # Check if database file exists
            if not os.path.exists(self.db_path):
                print(f"Database file does not exist yet: {self.db_path}")
                return

            # Try to open database to check if WAL files are stale
            # If we can open it successfully, SQLite will handle recovery automatically
            try:
                test_conn = sqlite3.connect(
                    self.db_path,
                    timeout=5.0,
                    isolation_level=None,  # Autocommit mode
                )

                # Check WAL mode
                cursor = test_conn.cursor()
                cursor.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()

                if mode and mode[0].upper() == "WAL":
                    # Try to checkpoint to clean up WAL
                    try:
                        cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
                        print("Performed passive WAL checkpoint during startup")
                    except Exception as checkpoint_err:
                        print(f"Could not checkpoint WAL on startup: {checkpoint_err}")

                cursor.close()
                test_conn.close()

                print(
                    "Database opened successfully, WAL recovery (if needed) completed"
                )

            except sqlite3.Error as db_err:
                print(f"Database check failed: {db_err}")

                # If database is locked or corrupted, try to remove stale files
                # This is safe only if NO other process is using the database
                for file_path in [wal_file, shm_file]:
                    if os.path.exists(file_path):
                        try:
                            # Try to remove the file
                            os.remove(file_path)
                            print(f"Removed stale file: {file_path}")
                        except OSError as remove_err:
                            # File is locked by another process - this is OK
                            print(
                                f"Could not remove {file_path} (may be in use): {remove_err}"
                            )

        except Exception as e:
            print(f"Error during WAL cleanup: {e}")
            # Don't raise - allow database initialization to continue


# Global database manager instance
db_manager = DatabaseManager()

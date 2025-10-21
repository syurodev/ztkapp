"""
Migration: Add soft delete to devices table
Created: 2025-10-17
"""


def upgrade(connection):
    """Add deleted_at column to devices table for soft delete"""
    cursor = connection.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(devices)")
    columns = [col[1] for col in cursor.fetchall()]

    if "deleted_at" not in columns:
        cursor.execute("""
            ALTER TABLE devices ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL
        """)
        connection.commit()

        # Create index for faster queries on soft-deleted items
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_deleted_at
            ON devices(deleted_at)
        """)
        connection.commit()

        print("Migration 001: Added soft delete column to devices table")
    else:
        print("Migration 001: deleted_at column already exists, skipping")


def downgrade(connection):
    """Remove deleted_at column from devices table"""
    cursor = connection.cursor()

    # SQLite doesn't support DROP COLUMN directly before version 3.35.0
    # We need to recreate the table without deleted_at column

    # Drop the index first
    cursor.execute("DROP INDEX IF EXISTS idx_devices_deleted_at")
    connection.commit()

    # Create new table without deleted_at
    cursor.execute("""
        CREATE TABLE devices_new (
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
            device_type TEXT DEFAULT 'pull',
            device_info TEXT,
            serial_number TEXT UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()

    # Copy data
    cursor.execute("""
        INSERT INTO devices_new
        SELECT id, name, ip, port, password, timeout, retry_count, retry_delay,
               ping_interval, force_udp, is_active, device_type, device_info,
               serial_number, created_at, updated_at
        FROM devices
        WHERE deleted_at IS NULL
    """)
    connection.commit()

    # Drop old table and rename
    cursor.execute("DROP TABLE devices")
    cursor.execute("ALTER TABLE devices_new RENAME TO devices")
    connection.commit()

    print("Migration 001: Removed soft delete column from devices table")

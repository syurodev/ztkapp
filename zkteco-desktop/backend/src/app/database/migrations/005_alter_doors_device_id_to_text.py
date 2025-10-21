"""
Migration: Alter doors table to change device_id from INTEGER to TEXT
Created: 2025-10-17

SAFE PATTERN: Preserves all data when converting device_id type
"""


def upgrade(connection):
    """
    Change device_id from INTEGER to TEXT in doors table

    This migration safely converts device_id values to TEXT while preserving all data.
    """
    cursor = connection.cursor()

    # Check current schema
    cursor.execute("PRAGMA table_info(doors)")
    columns = {col[1]: col for col in cursor.fetchall()}

    if "device_id" not in columns:
        print("Migration 005: device_id column not found, skipping")
        return

    col_info = columns["device_id"]
    col_type = col_info[2]  # type

    if col_type == "TEXT":
        print("Migration 005: device_id already TEXT, skipping")
        return

    print(f"Migration 005: Converting device_id from {col_type} to TEXT...")

    # SQLite requires table recreation for type changes
    # Create new table with TEXT device_id
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id TEXT,  -- Changed to TEXT
            location TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
        )
    """)
    connection.commit()

    # Copy data with CAST to preserve device_id values
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT
            id,
            name,
            CASE
                WHEN device_id IS NOT NULL THEN CAST(device_id AS TEXT)
                ELSE NULL
            END as device_id,
            location,
            description,
            status,
            created_at,
            updated_at
        FROM doors
    """)
    connection.commit()

    # Verify data copied correctly
    cursor.execute("SELECT COUNT(*) FROM doors")
    old_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM doors_new")
    new_count = cursor.fetchone()[0]

    if old_count != new_count:
        raise Exception(f"Data loss detected! Old: {old_count}, New: {new_count}")

    # Drop old table and rename
    cursor.execute("DROP TABLE doors")
    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)")
    connection.commit()

    print("Migration 005: Successfully changed device_id to TEXT")
    print(f"Migration 005: Migrated {new_count} door record(s)")


def downgrade(connection):
    """
    Revert device_id from TEXT to INTEGER

    Warning: Only TEXT values that can be converted to INTEGER will be kept.
    UUIDs and non-numeric strings will become NULL or cause rows to be skipped.
    """
    cursor = connection.cursor()

    print("Migration 005 downgrade: Converting device_id from TEXT back to INTEGER...")

    # Check for non-numeric device_ids
    cursor.execute("""
        SELECT COUNT(*) FROM doors
        WHERE device_id IS NOT NULL
        AND device_id != ''
        AND (CAST(device_id AS INTEGER) = 0 AND device_id != '0')
    """)
    non_numeric_count = cursor.fetchone()[0]

    if non_numeric_count > 0:
        print(
            f"Warning: {non_numeric_count} door(s) have non-numeric device_id (will be set to NULL)"
        )

    # Create new table with INTEGER device_id
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id INTEGER,  -- Back to INTEGER
            location TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
        )
    """)
    connection.commit()

    # Copy data, converting TEXT to INTEGER where possible
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT
            id,
            name,
            CASE
                WHEN device_id IS NULL OR device_id = '' THEN NULL
                WHEN CAST(device_id AS INTEGER) = 0 AND device_id != '0' THEN NULL
                ELSE CAST(device_id AS INTEGER)
            END as device_id,
            location,
            description,
            status,
            created_at,
            updated_at
        FROM doors
    """)
    connection.commit()

    cursor.execute("DROP TABLE doors")
    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)")
    connection.commit()

    print("Migration 005 downgrade: Reverted device_id to INTEGER")

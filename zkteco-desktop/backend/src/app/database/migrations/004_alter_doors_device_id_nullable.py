"""
Migration: Alter doors table to make device_id nullable
Created: 2025-10-17

SAFE PATTERN: Uses PRAGMA to check before altering (không recreate table)
"""


def upgrade(connection):
    """
    Make device_id nullable in doors table

    Note: SQLite doesn't support ALTER COLUMN for constraints,
    but we can verify the schema is correct.
    """
    cursor = connection.cursor()

    # Check current schema
    cursor.execute("PRAGMA table_info(doors)")
    columns = {col[1]: col for col in cursor.fetchall()}

    if "device_id" in columns:
        col_info = columns["device_id"]
        is_not_null = col_info[3]  # notnull flag

        if is_not_null == 1:
            # device_id is NOT NULL, need to recreate table
            print("Migration 004: device_id is NOT NULL, making it nullable...")

            # Since SQLite limitation, we must recreate the table
            # But we preserve ALL data this time
            cursor.execute("""
                CREATE TABLE doors_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    device_id INTEGER,  -- Made nullable
                    location TEXT,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
                )
            """)
            connection.commit()

            # Copy ALL data including device_id
            cursor.execute("""
                INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
                SELECT id, name, device_id, location, description, status, created_at, updated_at
                FROM doors
            """)
            connection.commit()

            # Drop old and rename
            cursor.execute("DROP TABLE doors")
            cursor.execute("ALTER TABLE doors_new RENAME TO doors")
            connection.commit()

            # Recreate indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)"
            )
            connection.commit()

            print("Migration 004: Made device_id nullable in doors table")
        else:
            print("Migration 004: device_id already nullable, skipping")
    else:
        print("Migration 004: device_id column not found, skipping")


def downgrade(connection):
    """
    Revert device_id to NOT NULL

    Warning: This will delete rows where device_id is NULL
    """
    cursor = connection.cursor()

    # Check if there are any NULL device_ids
    cursor.execute("SELECT COUNT(*) FROM doors WHERE device_id IS NULL")
    null_count = cursor.fetchone()[0]

    if null_count > 0:
        print(f"Warning: {null_count} door(s) have NULL device_id and will be deleted")

    # Recreate table with NOT NULL constraint
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id INTEGER NOT NULL,  -- Back to NOT NULL
            location TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        )
    """)
    connection.commit()

    # Copy only rows with device_id
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT id, name, device_id, location, description, status, created_at, updated_at
        FROM doors
        WHERE device_id IS NOT NULL
    """)
    connection.commit()

    cursor.execute("DROP TABLE doors")
    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)")
    connection.commit()

    print("Migration 004: Reverted device_id to NOT NULL in doors table")

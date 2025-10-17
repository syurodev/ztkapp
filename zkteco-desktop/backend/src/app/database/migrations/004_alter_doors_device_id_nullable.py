"""
Migration: Alter doors table to make device_id nullable
Created: 2025-10-17
"""


def upgrade(connection):
    """Make device_id nullable in doors table"""
    cursor = connection.cursor()

    # SQLite doesn't support ALTER COLUMN directly
    # We need to recreate the table

    # 1. Create temporary table with new schema
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id INTEGER,
            location TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
        )
    """)
    connection.commit()

    # 2. Copy data from old table to new table
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT id, name, device_id, location, description, status, created_at, updated_at
        FROM doors
    """)
    connection.commit()

    # 3. Drop old table
    cursor.execute("DROP TABLE doors")
    connection.commit()

    # 4. Rename new table to original name
    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # 5. Recreate indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)
    """)
    connection.commit()

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)
    """)
    connection.commit()

    print("Migration 004: Made device_id nullable in doors table")


def downgrade(connection):
    """Revert device_id to NOT NULL"""
    cursor = connection.cursor()

    # Create table with NOT NULL constraint
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id INTEGER NOT NULL,
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
    connection.commit()

    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)")
    connection.commit()

    print("Migration 004: Reverted device_id to NOT NULL in doors table")

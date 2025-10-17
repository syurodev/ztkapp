"""
Migration: Alter doors table to change device_id to TEXT
Created: 2025-10-17
"""


def upgrade(connection):
    """Change device_id to TEXT in doors table"""
    cursor = connection.cursor()

    # 1. Create a new table with the correct schema
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

    # 2. Copy data from the old table to the new one.
    # Since we can't map old integer device_id to new TEXT ids, we set them to NULL.
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT id, name, NULL, location, description, status, created_at, updated_at
        FROM doors
    """)
    connection.commit()

    # 3. Drop the old table
    cursor.execute("DROP TABLE doors")
    connection.commit()

    # 4. Rename the new table to the original name
    cursor.execute("ALTER TABLE doors_new RENAME TO doors")
    connection.commit()

    # 5. Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)")
    connection.commit()

    print("Migration 005: Changed doors.device_id to TEXT")


def downgrade(connection):
    """Revert device_id to INTEGER"""
    cursor = connection.cursor()

    # Create a new table with the old schema
    cursor.execute("""
        CREATE TABLE doors_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id INTEGER, -- Reverted to INTEGER
            location TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
        )
    """)
    connection.commit()

    # Copy data back, device_id will be NULL
    cursor.execute("""
        INSERT INTO doors_new (id, name, device_id, location, description, status, created_at, updated_at)
        SELECT id, name, NULL, location, description, status, created_at, updated_at
        FROM doors
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

    print("Migration 005: Reverted doors.device_id to INTEGER")

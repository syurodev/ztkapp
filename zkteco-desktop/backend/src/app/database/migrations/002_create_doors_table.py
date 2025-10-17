"""
Migration: Create doors table
Created: 2025-10-17
"""


def upgrade(connection):
    """Create doors table"""
    cursor = connection.cursor()

    # Create the table first
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doors (
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

    # Then create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doors_device_id ON doors(device_id)
    """)
    connection.commit()

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doors_status ON doors(status)
    """)
    connection.commit()

    print("Migration 002: Created doors table")


def downgrade(connection):
    """Drop doors table"""
    cursor = connection.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_doors_status")
    cursor.execute("DROP INDEX IF EXISTS idx_doors_device_id")
    cursor.execute("DROP TABLE IF EXISTS doors")
    connection.commit()
    print("Migration 002: Dropped doors table")

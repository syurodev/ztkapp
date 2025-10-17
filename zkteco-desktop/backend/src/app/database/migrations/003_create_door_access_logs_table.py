"""
Migration: Create door_access_logs table
Created: 2025-10-17
"""


def upgrade(connection):
    """Create door_access_logs table"""
    cursor = connection.cursor()

    # Create the table first
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS door_access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            door_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (door_id) REFERENCES doors(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    connection.commit()

    # Then create indexes for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_door_id ON door_access_logs(door_id)
    """)
    connection.commit()

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_user_id ON door_access_logs(user_id)
    """)
    connection.commit()

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_timestamp ON door_access_logs(timestamp)
    """)
    connection.commit()

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_action ON door_access_logs(action)
    """)
    connection.commit()

    print("Migration 003: Created door_access_logs table")


def downgrade(connection):
    """Drop door_access_logs table"""
    cursor = connection.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_door_access_logs_action")
    cursor.execute("DROP INDEX IF EXISTS idx_door_access_logs_timestamp")
    cursor.execute("DROP INDEX IF EXISTS idx_door_access_logs_user_id")
    cursor.execute("DROP INDEX IF EXISTS idx_door_access_logs_door_id")
    cursor.execute("DROP TABLE IF EXISTS door_access_logs")
    connection.commit()
    print("Migration 003: Dropped door_access_logs table")

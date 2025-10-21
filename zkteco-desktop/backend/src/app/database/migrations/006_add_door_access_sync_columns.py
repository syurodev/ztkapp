"""
Migration: Add sync columns to door_access_logs table
Created: 2025-10-19

SAFE PATTERN: Uses PRAGMA to check before adding columns (như connection.py)
"""


def upgrade(connection):
    """
    Add is_synced and synced_at columns to door_access_logs table

    This is the SAFE way - checks before adding, doesn't recreate table.
    """
    cursor = connection.cursor()

    # Check which columns already exist
    cursor.execute("PRAGMA table_info(door_access_logs)")
    columns = [col[1] for col in cursor.fetchall()]

    changes_made = False

    # Add is_synced column if not exists
    if "is_synced" not in columns:
        try:
            print("Migration 006: Adding is_synced column...")
            cursor.execute("""
                ALTER TABLE door_access_logs
                ADD COLUMN is_synced BOOLEAN DEFAULT 0
            """)
            connection.commit()
            print("Migration 006: ✓ is_synced column added")
            changes_made = True
        except Exception as e:
            print(f"Migration 006: Warning - Could not add is_synced column: {e}")
    else:
        print("Migration 006: is_synced column already exists, skipping")

    # Add synced_at column if not exists
    if "synced_at" not in columns:
        try:
            print("Migration 006: Adding synced_at column...")
            cursor.execute("""
                ALTER TABLE door_access_logs
                ADD COLUMN synced_at DATETIME NULL
            """)
            connection.commit()
            print("Migration 006: ✓ synced_at column added")
            changes_made = True
        except Exception as e:
            print(f"Migration 006: Warning - Could not add synced_at column: {e}")
    else:
        print("Migration 006: synced_at column already exists, skipping")

    # Add index for faster lookups on is_synced
    if changes_made or "is_synced" in columns:
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_door_access_logs_is_synced
                ON door_access_logs(is_synced)
            """)
            connection.commit()
            print("Migration 006: ✓ Index on is_synced created")
        except Exception as e:
            print(f"Migration 006: Warning - Could not create index: {e}")

    if changes_made:
        print("Migration 006: Successfully added sync columns to door_access_logs")
    else:
        print("Migration 006: All sync columns already present, no changes needed")


def downgrade(connection):
    """
    Remove sync columns from door_access_logs table

    SQLite doesn't support DROP COLUMN directly (before 3.35.0),
    so we need to recreate the table.
    """
    cursor = connection.cursor()

    # Check if columns exist before attempting removal
    cursor.execute("PRAGMA table_info(door_access_logs)")
    columns = [col[1] for col in cursor.fetchall()]

    if "is_synced" not in columns and "synced_at" not in columns:
        print("Migration 006 downgrade: Sync columns not present, nothing to remove")
        return

    print("Migration 006 downgrade: Removing sync columns...")

    # Drop index first
    cursor.execute("DROP INDEX IF EXISTS idx_door_access_logs_is_synced")
    connection.commit()

    # Recreate table without sync columns
    cursor.execute("""
        CREATE TABLE door_access_logs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            door_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (door_id) REFERENCES doors(id) ON DELETE CASCADE
        )
    """)
    connection.commit()

    # Copy data without sync columns
    cursor.execute("""
        INSERT INTO door_access_logs_new
            (id, door_id, user_id, user_name, action, status, timestamp, notes)
        SELECT
            id, door_id, user_id, user_name, action, status, timestamp, notes
        FROM door_access_logs
    """)
    connection.commit()

    # Verify data
    cursor.execute("SELECT COUNT(*) FROM door_access_logs")
    old_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM door_access_logs_new")
    new_count = cursor.fetchone()[0]

    if old_count != new_count:
        raise Exception(
            f"Data loss detected during downgrade! Old: {old_count}, New: {new_count}"
        )

    # Drop old table and rename
    cursor.execute("DROP TABLE door_access_logs")
    cursor.execute("ALTER TABLE door_access_logs_new RENAME TO door_access_logs")
    connection.commit()

    # Recreate original indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_door_id
        ON door_access_logs(door_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_user_id
        ON door_access_logs(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_timestamp
        ON door_access_logs(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_door_access_logs_action
        ON door_access_logs(action)
    """)
    connection.commit()

    print("Migration 006 downgrade: Successfully removed sync columns")
    print(f"Migration 006 downgrade: Preserved {new_count} log record(s)")

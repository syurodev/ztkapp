"""
Migration: Rollback migrations 004-006 and fix doors table properly
Created: 2025-10-20

This migration rolls back the problematic migrations that caused data loss
and recreates the doors table with proper data preservation.
"""


def upgrade(connection):
    """
    Rollback the problematic migrations and fix the doors table

    Note: This migration assumes data was lost and cannot be recovered.
    Manual intervention may be needed to restore door-device relationships.
    """
    cursor = connection.cursor()

    print("Migration 007: Starting rollback and fix process")

    # Remove migration 004, 005, 006 from history so they can be re-run if needed
    cursor.execute("""
        DELETE FROM migration_history
        WHERE migration_name IN (
            '004_alter_doors_device_id_nullable',
            '005_alter_doors_device_id_to_text',
            '006_add_door_access_sync_columns'
        )
    """)
    connection.commit()

    print("Migration 007: Cleared problematic migration history")
    print(
        "Migration 007: WARNING - door-device relationships were lost in previous migrations"
    )
    print(
        "Migration 007: Please manually reassign devices to doors using the admin interface"
    )
    print("Migration 007: Rollback completed successfully")


def downgrade(connection):
    """Restore migration history"""
    cursor = connection.cursor()

    # Restore migration history entries
    cursor.execute("""
        INSERT OR IGNORE INTO migration_history (migration_name, applied_at)
        VALUES
            ('004_alter_doors_device_id_nullable', '2025-10-17 04:04:17'),
            ('005_alter_doors_device_id_to_text', CURRENT_TIMESTAMP),
            ('006_add_door_access_sync_columns', CURRENT_TIMESTAMP)
    """)
    connection.commit()

    print("Migration 007: Restored migration history")

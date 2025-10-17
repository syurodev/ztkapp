"""
Run database migrations
"""

import os
import sys
import importlib.util

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.database.connection import db_manager


def run_migrations():
    """Run all pending migrations"""
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")

    if not os.path.exists(migrations_dir):
        print(f"Migrations directory not found: {migrations_dir}")
        return

    # Get all migration files
    migration_files = sorted(
        [
            f
            for f in os.listdir(migrations_dir)
            if f.endswith(".py") and not f.startswith("__")
        ]
    )

    if not migration_files:
        print("No migration files found")
        return

    print(f"Found {len(migration_files)} migration file(s)")

    # Create migrations tracking table if it doesn't exist
    with db_manager.get_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Run each migration
    for migration_file in migration_files:
        migration_name = migration_file[:-3]  # Remove .py extension

        # Check if migration already applied
        existing = db_manager.fetch_one(
            "SELECT * FROM migration_history WHERE migration_name = ?",
            (migration_name,),
        )

        if existing:
            print(f"Migration {migration_name} already applied, skipping...")
            continue

        # Load and run migration
        migration_path = os.path.join(migrations_dir, migration_file)

        try:
            print(f"Running migration: {migration_name}")

            # Import migration module
            spec = importlib.util.spec_from_file_location(
                migration_name, migration_path
            )
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # Run upgrade function
            if hasattr(migration_module, "upgrade"):
                conn = db_manager.get_connection()
                migration_module.upgrade(conn)

                # Record migration as applied
                with db_manager.get_cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO migration_history (migration_name) VALUES (?)",
                        (migration_name,),
                    )

                print(f"Migration {migration_name} completed successfully")
            else:
                print(f"Warning: Migration {migration_name} has no upgrade function")

        except Exception as e:
            print(f"Error running migration {migration_name}: {e}")
            import traceback

            traceback.print_exc()
            # Continue with other migrations instead of stopping
            continue

    print("\nAll migrations completed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Running database migrations...")
    print("=" * 60)
    run_migrations()

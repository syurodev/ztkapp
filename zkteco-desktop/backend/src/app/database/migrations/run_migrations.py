import os
import sqlite3
import importlib.util

# Add the project root to the Python path to allow for absolute imports
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.database.connection import db_manager


def run_migrations():
    """Run all pending database migrations"""
    print("Starting database migration process...")

    # 1. Get database connection
    connection = db_manager.get_connection()
    cursor = connection.cursor()

    # 2. Create migrations table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    print("Migrations table ensured.")

    # 3. Get list of applied migrations
    cursor.execute("SELECT name FROM migrations")
    applied_migrations = {row[0] for row in cursor.fetchall()}
    print(f"Found {len(applied_migrations)} applied migrations: {applied_migrations}")

    # 4. Find all migration files
    migrations_dir = os.path.dirname(__file__)
    all_migration_files = sorted(
        [
            f
            for f in os.listdir(migrations_dir)
            if f.endswith(".py") and f.startswith("0") and f != "__init__.py"
        ]
    )
    print(f"Found {len(all_migration_files)} migration files in directory.")

    # 5. Run pending migrations
    pending_migrations = [f for f in all_migration_files if f not in applied_migrations]
    print(f"Pending migrations to run: {pending_migrations}")

    for migration_file in pending_migrations:
        try:
            print(f"--- Running migration: {migration_file} ---")

            # Dynamically import the migration module
            module_name = migration_file[:-3]
            file_path = os.path.join(migrations_dir, migration_file)
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # Run the upgrade function
            if hasattr(migration_module, "upgrade"):
                migration_module.upgrade(connection)
                print(f"Upgrade function in {migration_file} executed.")
            else:
                print(f"Warning: No upgrade function found in {migration_file}")
                continue

            # Record the migration as applied
            cursor.execute(
                "INSERT INTO migrations (name) VALUES (?)", (migration_file,)
            )
            connection.commit()
            print(f"--- Successfully applied migration: {migration_file} ---")

        except Exception as e:
            print(f"!!! ERROR applying migration {migration_file}: {e} !!!")
            connection.rollback()
            # It's often better to stop on error to avoid cascading failures
            raise

    print("Database migration process completed.")


if __name__ == "__main__":
    run_migrations()

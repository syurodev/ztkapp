from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.user import User
from app.database.connection import db_manager

class UserRepository:
    """User database operations with sync tracking"""

    def create(self, user: User) -> User:
        """Create new user"""
        query = '''
            INSERT INTO users (
                user_id, name, device_id, serial_number, privilege, group_id, card, password, is_synced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        cursor = db_manager.execute_query(query, (
            user.user_id, user.name, user.device_id, user.serial_number, user.privilege,
            user.group_id, user.card, user.password, user.is_synced
        ))

        # Get the created user with auto-generated ID
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by auto-generated ID"""
        row = db_manager.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._row_to_user(row) if row else None

    def get_by_user_id(self, user_id: str, device_id: str = None) -> Optional[User]:
        """Get user by user_id and optionally device_id"""
        if device_id:
            row = db_manager.fetch_one(
                "SELECT * FROM users WHERE user_id = ? AND device_id = ?",
                (user_id, device_id)
            )
        else:
            row = db_manager.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self._row_to_user(row) if row else None

    def get_all(self, device_id: str = None) -> List[User]:
        """Get all users, optionally filtered by device"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM users WHERE device_id = ? ORDER BY created_at DESC",
                (device_id,)
            )
        else:
            rows = db_manager.fetch_all("SELECT * FROM users ORDER BY created_at DESC")
        return [self._row_to_user(row) for row in rows]

    def get_unsynced_users(self, device_id: str = None) -> List[User]:
        """Get users that haven't been synced"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM users WHERE is_synced = FALSE AND device_id = ?",
                (device_id,)
            )
        else:
            rows = db_manager.fetch_all("SELECT * FROM users WHERE is_synced = FALSE")
        return [self._row_to_user(row) for row in rows]

    def mark_as_synced(self, user_id: int) -> bool:
        """Mark user as synced"""
        query = "UPDATE users SET is_synced = TRUE, synced_at = ? WHERE id = ?"
        cursor = db_manager.execute_query(query, (datetime.now(), user_id))
        return cursor.rowcount > 0

    def mark_as_unsynced(self, user_id: int) -> bool:
        """Mark user as not synced (for re-sync scenarios)"""
        query = "UPDATE users SET is_synced = FALSE, synced_at = NULL WHERE id = ?"
        cursor = db_manager.execute_query(query, (user_id,))
        return cursor.rowcount > 0

    def update(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update user"""
        updates['updated_at'] = datetime.now()

        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        query = f"UPDATE users SET {set_clause} WHERE id = ?"

        cursor = db_manager.execute_query(query, (*updates.values(), user_id))
        return cursor.rowcount > 0

    def delete(self, user_id: int) -> bool:
        """Delete user"""
        cursor = db_manager.execute_query("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0

    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        # Helper function to safely get column value
        def get_column(column_name, default=None):
            try:
                return row[column_name] if column_name in row.keys() else default
            except (KeyError, IndexError):
                return default

        return User(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            device_id=row['device_id'],
            serial_number=get_column('serial_number'),
            privilege=row['privilege'],
            group_id=row['group_id'],
            card=row['card'],
            password=row['password'],
            is_synced=bool(row['is_synced']),
            synced_at=row['synced_at'],
            external_user_id=get_column('external_user_id'),
            avatar_url=get_column('avatar_url'),
            # New fields
            full_name=get_column('full_name'),
            employee_code=get_column('employee_code'),
            employee_object=get_column('employee_object'),
            position=get_column('position'),
            department=get_column('department'),
            notes=get_column('notes'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

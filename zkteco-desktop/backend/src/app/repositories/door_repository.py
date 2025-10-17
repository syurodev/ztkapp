"""
Door repository for database operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.door import Door
from app.database.connection import db_manager
from app.shared.logger import app_logger


class DoorRepository:
    """Door database operations"""

    def create(self, door: Door) -> Door:
        """Create new door"""
        query = """
            INSERT INTO doors (
                name, device_id, location, description, status
            ) VALUES (?, ?, ?, ?, ?)
        """

        cursor = db_manager.execute_query(
            query,
            (
                door.name,
                door.device_id,
                door.location,
                door.description,
                door.status,
            ),
        )

        door.id = cursor.lastrowid
        return self.get_by_id(door.id)

    def get_by_id(self, door_id: int) -> Optional[Door]:
        """Get door by ID"""
        row = db_manager.fetch_one("SELECT * FROM doors WHERE id = ?", (door_id,))
        return self._row_to_door(row) if row else None

    def get_all(self) -> List[Door]:
        """Get all doors"""
        rows = db_manager.fetch_all("SELECT * FROM doors ORDER BY created_at DESC")
        return [self._row_to_door(row) for row in rows]

    def get_by_device_id(self, device_id: int) -> List[Door]:
        """Get all doors for a specific device"""
        rows = db_manager.fetch_all(
            "SELECT * FROM doors WHERE device_id = ? ORDER BY created_at DESC",
            (device_id,),
        )
        return [self._row_to_door(row) for row in rows]

    def update(self, door_id: int, updates: Dict[str, Any]) -> bool:
        """Update door"""
        updates["updated_at"] = datetime.now()

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        query = f"UPDATE doors SET {set_clause} WHERE id = ?"

        cursor = db_manager.execute_query(query, (*updates.values(), door_id))
        return cursor.rowcount > 0

    def delete(self, door_id: int) -> bool:
        """Delete door"""
        try:
            app_logger.info(f"DoorRepository: Starting delete for door_id: {door_id}")

            # Check if door exists first
            existing = db_manager.fetch_one(
                "SELECT id, name FROM doors WHERE id = ?", (door_id,)
            )
            if existing:
                app_logger.info(
                    f"DoorRepository: Found door to delete: {existing[1]} ({existing[0]})"
                )
            else:
                app_logger.warning(
                    f"DoorRepository: Door not found for deletion: {door_id}"
                )
                return False

            app_logger.info(
                f"DoorRepository: Executing DELETE query for door_id: {door_id}"
            )

            # Execute DELETE and get rowcount within context
            with db_manager.get_cursor() as cursor:
                cursor.execute("DELETE FROM doors WHERE id = ?", (door_id,))
                rowcount = cursor.rowcount
                success = rowcount > 0
                app_logger.info(
                    f"DoorRepository: DELETE query affected {rowcount} rows, success: {success}"
                )

            return success

        except Exception as e:
            app_logger.error(
                f"DoorRepository: Error deleting door {door_id}: {e}",
                exc_info=True,
            )
            raise

    def _row_to_door(self, row) -> Door:
        """Convert database row to Door object"""
        return Door(
            id=row["id"],
            name=row["name"],
            device_id=row["device_id"],
            location=row["location"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

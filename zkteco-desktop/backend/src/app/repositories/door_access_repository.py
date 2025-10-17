"""
Door Access Log repository for database operations
"""

from typing import List, Optional
from datetime import datetime
from app.models.door_access_log import DoorAccessLog
from app.database.connection import db_manager
from app.shared.logger import app_logger


class DoorAccessRepository:
    """Door Access Log database operations"""

    def create(self, log: DoorAccessLog) -> DoorAccessLog:
        """Create new door access log entry"""
        query = """
            INSERT INTO door_access_logs (
                door_id, user_id, user_name, action, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """

        cursor = db_manager.execute_query(
            query,
            (
                log.door_id,
                log.user_id,
                log.user_name,
                log.action,
                log.status,
                log.notes,
            ),
        )

        log.id = cursor.lastrowid
        return self.get_by_id(log.id)

    def get_by_id(self, log_id: int) -> Optional[DoorAccessLog]:
        """Get access log by ID"""
        row = db_manager.fetch_one(
            "SELECT * FROM door_access_logs WHERE id = ?", (log_id,)
        )
        return self._row_to_log(row) if row else None

    def get_by_door_id(
        self, door_id: int, limit: int = 100, offset: int = 0
    ) -> List[DoorAccessLog]:
        """Get access logs for a specific door"""
        rows = db_manager.fetch_all(
            """
            SELECT * FROM door_access_logs
            WHERE door_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (door_id, limit, offset),
        )
        return [self._row_to_log(row) for row in rows]

    def get_by_user_id(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[DoorAccessLog]:
        """Get access logs for a specific user"""
        rows = db_manager.fetch_all(
            """
            SELECT * FROM door_access_logs
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        return [self._row_to_log(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[DoorAccessLog]:
        """Get all access logs with pagination"""
        rows = db_manager.fetch_all(
            """
            SELECT * FROM door_access_logs
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [self._row_to_log(row) for row in rows]

    def get_by_date_range(
        self, start_date: datetime, end_date: datetime, door_id: Optional[int] = None
    ) -> List[DoorAccessLog]:
        """Get access logs within a date range"""
        if door_id:
            rows = db_manager.fetch_all(
                """
                SELECT * FROM door_access_logs
                WHERE door_id = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
                """,
                (door_id, start_date, end_date),
            )
        else:
            rows = db_manager.fetch_all(
                """
                SELECT * FROM door_access_logs
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
                """,
                (start_date, end_date),
            )
        return [self._row_to_log(row) for row in rows]

    def count_by_door_id(self, door_id: int) -> int:
        """Count access logs for a specific door"""
        row = db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM door_access_logs WHERE door_id = ?",
            (door_id,),
        )
        return row["count"] if row else 0

    def delete_old_logs(self, days: int = 90) -> int:
        """Delete access logs older than specified days"""
        try:
            app_logger.info(
                f"DoorAccessRepository: Deleting logs older than {days} days"
            )

            with db_manager.get_cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM door_access_logs
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                    """,
                    (days,),
                )
                rowcount = cursor.rowcount
                app_logger.info(f"DoorAccessRepository: Deleted {rowcount} old logs")
                return rowcount

        except Exception as e:
            app_logger.error(
                f"DoorAccessRepository: Error deleting old logs: {e}",
                exc_info=True,
            )
            raise

    def _row_to_log(self, row) -> DoorAccessLog:
        """Convert database row to DoorAccessLog object"""
        return DoorAccessLog(
            id=row["id"],
            door_id=row["door_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            action=row["action"],
            status=row["status"],
            timestamp=row["timestamp"],
            notes=row["notes"],
        )

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

    def get_unsynced_logs_by_date(self, target_date: str) -> List[DoorAccessLog]:
        """Get unsynced door access logs for a specific date"""
        rows = db_manager.fetch_all(
            """
            SELECT * FROM door_access_logs
            WHERE DATE(timestamp) = ? AND is_synced = 0
            ORDER BY user_id, door_id, timestamp
            """,
            (target_date,),
        )
        return [self._row_to_log(row) for row in rows]

    def get_aggregated_door_access(self, target_date: str) -> List[dict]:
        """
        Get aggregated door access data for a specific date.
        Groups by user_id and door_id, collecting all timestamps.

        Returns:
            List of dicts with structure:
            {
                'user_id': int,
                'door_id': int,
                'external_user_id': int (from users table),
                'timestamps': List[str],  # HH:MM:SS format
                'log_ids': List[int]  # For marking as synced later
            }
        """
        query = """
            SELECT
                dal.id,
                dal.user_id,
                dal.door_id,
                TIME(dal.timestamp) as time_str,
                u.external_user_id
            FROM door_access_logs dal
            LEFT JOIN users u ON CAST(dal.user_id AS TEXT) = u.user_id
            WHERE DATE(dal.timestamp) = ?
              AND dal.is_synced = 0
            ORDER BY dal.user_id, dal.door_id, dal.timestamp
        """

        rows = db_manager.fetch_all(query, (target_date,))

        if not rows:
            return []

        # Group by (user_id, door_id)
        from collections import defaultdict

        grouped = defaultdict(
            lambda: {
                "user_id": None,
                "door_id": None,
                "external_user_id": None,
                "timestamps": [],
                "log_ids": [],
            }
        )

        for row in rows:
            key = (row["user_id"], row["door_id"])

            if grouped[key]["user_id"] is None:
                grouped[key]["user_id"] = row["user_id"]
                grouped[key]["door_id"] = row["door_id"]
                grouped[key]["external_user_id"] = row["external_user_id"]

            grouped[key]["timestamps"].append(row["time_str"])
            grouped[key]["log_ids"].append(row["id"])

        return list(grouped.values())

    def mark_logs_as_synced(self, log_ids: List[int]) -> int:
        """
        Mark door access logs as synced.

        Args:
            log_ids: List of log IDs to mark as synced

        Returns:
            Number of rows updated
        """
        if not log_ids:
            return 0

        try:
            placeholders = ",".join(["?"] * len(log_ids))
            query = f"""
                UPDATE door_access_logs
                SET is_synced = 1, synced_at = ?
                WHERE id IN ({placeholders})
            """

            from datetime import datetime

            cursor = db_manager.execute_query(query, (datetime.now(), *log_ids))

            rowcount = cursor.rowcount
            app_logger.info(f"DoorAccessRepository: Marked {rowcount} logs as synced")
            return rowcount

        except Exception as e:
            app_logger.error(
                f"DoorAccessRepository: Error marking logs as synced: {e}",
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
            is_synced=bool(row["is_synced"] if "is_synced" in row.keys() else 0),
            synced_at=row["synced_at"] if "synced_at" in row.keys() else None,
        )

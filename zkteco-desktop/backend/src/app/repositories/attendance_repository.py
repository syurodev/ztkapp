import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
from app.models.attendance import AttendanceLog, SyncStatus
from app.database.connection import db_manager


class AttendanceRepository:
    """Attendance log database operations"""

    def create(self, log: AttendanceLog) -> AttendanceLog:
        """Create attendance log"""
        raw_data_json = json.dumps(log.raw_data) if log.raw_data else None

        query = """
            INSERT INTO attendance_logs (
                user_id, device_id, serial_number, timestamp, method, action,
                raw_data, sync_status, is_pushed, is_synced, synced_at, original_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = db_manager.execute_query(
            query,
            (
                log.user_id,
                log.device_id,
                log.serial_number,
                log.timestamp,
                log.method,
                log.action,
                raw_data_json,
                log.sync_status,
                int(log.is_pushed),
                log.is_synced,
                log.synced_at,
                log.original_status,
            ),
        )

        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, log_id: int) -> Optional[AttendanceLog]:
        """Get attendance log by ID"""
        row = db_manager.fetch_one(
            "SELECT * FROM attendance_logs WHERE id = ?", (log_id,)
        )
        return self._row_to_log(row) if row else None

    def get_all(
        self,
        device_id: str = None,
        limit: int = 1000,
        offset: int = 0,
        start_date=None,
        end_date=None,
    ) -> List[AttendanceLog]:
        """Get attendance logs with pagination and optional date filtering"""
        conditions = []
        params = []

        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)

        if start_date and end_date:
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.extend([start_date, end_date])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM attendance_logs WHERE {where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = db_manager.fetch_all(query, tuple(params))
        return [self._row_to_log(row) for row in rows]

    def get_total_count(
        self, device_id: str = None, start_date=None, end_date=None
    ) -> int:
        """Get total count of attendance logs with optional date filtering"""
        conditions = []
        params = []

        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)

        if start_date and end_date:
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.extend([start_date, end_date])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT COUNT(*) as count FROM attendance_logs WHERE {where_clause}"

        result = db_manager.fetch_one(query, tuple(params) if params else None)
        return result["count"] if result else 0

    def get_by_date(
        self, target_date, device_id: str = None, limit: int = 100, offset: int = 0
    ) -> List[AttendanceLog]:
        """Get attendance logs filtered by date with pagination"""
        from datetime import datetime

        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        if device_id:
            query = """
                SELECT * FROM attendance_logs
                WHERE device_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
            """
            rows = db_manager.fetch_all(
                query, (device_id, start_datetime, end_datetime, limit, offset)
            )
        else:
            query = """
                SELECT * FROM attendance_logs
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
            """
            rows = db_manager.fetch_all(
                query, (start_datetime, end_datetime, limit, offset)
            )

        return [self._row_to_log(row) for row in rows]

    def get_count_by_date(self, target_date, device_id: str = None) -> int:
        """Get total count of attendance logs for a specific date"""
        from datetime import datetime

        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        if device_id:
            query = """
                SELECT COUNT(*) as count FROM attendance_logs
                WHERE device_id = ? AND timestamp >= ? AND timestamp <= ?
            """
            result = db_manager.fetch_one(
                query, (device_id, start_datetime, end_datetime)
            )
        else:
            query = """
                SELECT COUNT(*) as count FROM attendance_logs
                WHERE timestamp >= ? AND timestamp <= ?
            """
            result = db_manager.fetch_one(query, (start_datetime, end_datetime))

        return result["count"] if result else 0

    def get_by_user(self, user_id: str, limit: int = 100) -> List[AttendanceLog]:
        """Get attendance logs for specific user"""
        rows = db_manager.fetch_all(
            "SELECT * FROM attendance_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )
        return [self._row_to_log(row) for row in rows]

    def get_latest_for_user_today(
        self, user_id: str, device_id: str, day_start: datetime, before_time: datetime
    ) -> Optional[AttendanceLog]:
        """
        Get latest attendance record for user today before specified time.

        Used for smart action detection in push devices.

        Args:
            user_id: User ID
            device_id: Device ID
            day_start: Start of day (00:00:00)
            before_time: Current attendance timestamp

        Returns:
            Latest AttendanceLog or None if no record found
        """
        query = """
            SELECT * FROM attendance_logs
            WHERE user_id = ?
              AND device_id = ?
              AND timestamp >= ?
              AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        row = db_manager.fetch_one(query, (user_id, device_id, day_start, before_time))
        return self._row_to_log(row) if row else None

    def get_unsynced_logs(
        self, device_id: str = None, limit: int = 1000
    ) -> List[AttendanceLog]:
        """Get attendance logs that haven't been synced (pending status)"""
        if device_id:
            rows = db_manager.fetch_all(
                """
                SELECT * FROM attendance_logs
                WHERE sync_status = ? AND device_id = ?
                  AND COALESCE(error_count, 0) < 5
                ORDER BY timestamp DESC LIMIT ?
                """,
                (SyncStatus.PENDING, device_id, limit),
            )
        else:
            rows = db_manager.fetch_all(
                """
                SELECT * FROM attendance_logs
                WHERE sync_status = ?
                  AND COALESCE(error_count, 0) < 5
                ORDER BY timestamp DESC LIMIT ?
                """,
                (SyncStatus.PENDING, limit),
            )
        return [self._row_to_log(row) for row in rows]

    def get_logs_by_sync_status(
        self, sync_status: str, device_id: str = None, limit: int = 1000
    ) -> List[AttendanceLog]:
        """Get attendance logs by sync status"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? AND device_id = ? ORDER BY timestamp DESC LIMIT ?",
                (sync_status, device_id, limit),
            )
        else:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? ORDER BY timestamp DESC LIMIT ?",
                (sync_status, limit),
            )
        return [self._row_to_log(row) for row in rows]

    def mark_as_synced(self, log_id: int) -> bool:
        """Mark attendance log as synced"""
        query = """
            UPDATE attendance_logs
            SET sync_status = ?, is_synced = TRUE, synced_at = ?,
                error_count = 0, error_code = NULL, error_message = NULL
            WHERE id = ?
        """
        cursor = db_manager.execute_query(
            query, (SyncStatus.SYNCED, datetime.now(), log_id)
        )
        return cursor.rowcount > 0

    def mark_as_unsynced(self, log_id: int) -> bool:
        """Mark attendance log as not synced (for re-sync scenarios)"""
        query = """
            UPDATE attendance_logs
            SET sync_status = ?, is_synced = FALSE, synced_at = NULL,
                error_count = 0, error_code = NULL, error_message = NULL
            WHERE id = ?
        """
        cursor = db_manager.execute_query(query, (SyncStatus.PENDING, log_id))
        return cursor.rowcount > 0

    def update_sync_status(self, log_id: int, sync_status: str) -> bool:
        """Update sync status of attendance log"""
        synced_at = datetime.now() if sync_status == SyncStatus.SYNCED else None
        is_synced = sync_status == SyncStatus.SYNCED
        if sync_status in (SyncStatus.PENDING, SyncStatus.SYNCED):
            query = """
                UPDATE attendance_logs
                SET sync_status = ?, is_synced = ?, synced_at = ?,
                    error_count = 0, error_code = NULL, error_message = NULL
                WHERE id = ?
            """
            params = (sync_status, is_synced, synced_at, log_id)
        else:
            query = """
                UPDATE attendance_logs
                SET sync_status = ?, is_synced = ?, synced_at = ?
                WHERE id = ?
            """
            params = (sync_status, is_synced, synced_at, log_id)
        cursor = db_manager.execute_query(query, params)
        return cursor.rowcount > 0

    def update_sync_error(
        self, log_id: int, error_code: str, error_message: str, increment: bool = True
    ) -> bool:
        """Update attendance log with error information"""
        if increment:
            query = """
                UPDATE attendance_logs
                SET sync_status = ?, error_code = ?, error_message = ?, synced_at = ?,
                    error_count = COALESCE(error_count, 0) + 1
                WHERE id = ?
            """
            params = (
                SyncStatus.ERROR,
                error_code,
                error_message,
                datetime.now(),
                log_id,
            )
        else:
            query = """
                UPDATE attendance_logs
                SET sync_status = ?, error_code = ?, error_message = ?, synced_at = ?
                WHERE id = ?
            """
            params = (
                SyncStatus.ERROR,
                error_code,
                error_message,
                datetime.now(),
                log_id,
            )

        cursor = db_manager.execute_query(query, params)
        return cursor.rowcount > 0

    def get_error_records(
        self, device_id: str = None, limit: int = 1000
    ) -> List[AttendanceLog]:
        """Get attendance logs with error status"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? AND device_id = ? ORDER BY timestamp DESC LIMIT ?",
                (SyncStatus.ERROR, device_id, limit),
            )
        else:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? ORDER BY timestamp DESC LIMIT ?",
                (SyncStatus.ERROR, limit),
            )
        return [self._row_to_log(row) for row in rows]

    def mark_records_as_skipped(self, log_ids: List[int]) -> int:
        """Mark multiple attendance logs as skipped"""
        if not log_ids:
            return 0

        placeholders = ",".join(["?" for _ in log_ids])
        query = (
            f"UPDATE attendance_logs SET sync_status = ? WHERE id IN ({placeholders})"
        )
        cursor = db_manager.execute_query(query, (SyncStatus.SKIPPED, *log_ids))
        return cursor.rowcount

    def mark_as_pushed(self, log_ids: List[int]) -> int:
        """Mark attendance logs as successfully pushed to external API."""
        if not log_ids:
            return 0

        placeholders = ",".join("?" for _ in log_ids)
        query = f"UPDATE attendance_logs SET is_pushed = 1 WHERE id IN ({placeholders})"
        cursor = db_manager.execute_query(query, tuple(log_ids))
        return cursor.rowcount

    def get_unpushed_logs(self, limit: int = 500) -> List[AttendanceLog]:
        """Fetch attendance logs that have not been pushed yet."""
        query = """
            SELECT * FROM attendance_logs
            WHERE COALESCE(is_pushed, 0) = 0
            ORDER BY timestamp ASC
            LIMIT ?
        """
        rows = db_manager.fetch_all(query, (limit,))
        return [self._row_to_log(row) for row in rows]

    def get_sync_stats(self, device_id: str = None) -> Dict[str, int]:
        """Get sync statistics"""
        base_query = "SELECT sync_status, COUNT(*) as count FROM attendance_logs"
        if device_id:
            query = f"{base_query} WHERE device_id = ? GROUP BY sync_status"
            rows = db_manager.fetch_all(query, (device_id,))
        else:
            query = f"{base_query} GROUP BY sync_status"
            rows = db_manager.fetch_all(query)

        stats = {"pending": 0, "synced": 0, "skipped": 0, "error": 0, "total": 0}
        for row in rows:
            sync_status = row["sync_status"] or "pending"  # Handle null values
            if sync_status in stats:
                stats[sync_status] = row["count"]

        stats["total"] = sum(
            stats[key] for key in ["pending", "synced", "skipped", "error"]
        )
        return stats

    def get_pending_sync_dates(
        self,
        device_id: str = None,
        include_error: bool = False,
    ) -> List[str]:
        """Get all dates that have pending (optionally error) attendance records"""
        statuses = [SyncStatus.PENDING]
        if include_error:
            statuses.append(SyncStatus.ERROR)

        placeholders = ", ".join("?" for _ in statuses)

        if device_id:
            query = f"""
                SELECT DISTINCT DATE(timestamp) as sync_date
                FROM attendance_logs
                WHERE sync_status IN ({placeholders}) AND device_id = ?
                ORDER BY sync_date
            """
            params = (*statuses, device_id)
            rows = db_manager.fetch_all(query, params)
        else:
            query = f"""
                SELECT DISTINCT DATE(timestamp) as sync_date
                FROM attendance_logs
                WHERE sync_status IN ({placeholders})
                ORDER BY sync_date
            """
            rows = db_manager.fetch_all(query, tuple(statuses))

        return [row["sync_date"] for row in rows]

    def has_synced_record_for_date_action(
        self, user_id: str, target_date: str, action: int, device_id: str = None
    ) -> bool:
        """Check if user has any synced record for specific date and action type"""
        if device_id:
            query = """
                SELECT COUNT(*) as count
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ? AND device_id = ?
            """
            result = db_manager.fetch_one(
                query, (user_id, target_date, action, SyncStatus.SYNCED, device_id)
            )
        else:
            query = """
                SELECT COUNT(*) as count
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ?
            """
            result = db_manager.fetch_one(
                query, (user_id, target_date, action, SyncStatus.SYNCED)
            )

        return result["count"] > 0 if result else False

    def get_other_records_for_date_action(
        self,
        user_id: str,
        target_date: str,
        action: int,
        exclude_log_id: int,
        device_id: str = None,
    ) -> List[int]:
        """Get IDs of other records for same user, date, and action (excluding specific log)"""
        if device_id:
            query = """
                SELECT id
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND id != ? AND device_id = ? AND sync_status = ?
            """
            rows = db_manager.fetch_all(
                query,
                (
                    user_id,
                    target_date,
                    action,
                    exclude_log_id,
                    device_id,
                    SyncStatus.PENDING,
                ),
            )
        else:
            query = """
                SELECT id
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND id != ? AND sync_status = ?
            """
            rows = db_manager.fetch_all(
                query,
                (user_id, target_date, action, exclude_log_id, SyncStatus.PENDING),
            )

        return [row["id"] for row in rows]

    def find_duplicate(
        self,
        user_id: str,
        device_id: str,
        timestamp: datetime,
        method: int,
        action: int,
    ) -> Optional[AttendanceLog]:
        """Find existing attendance record with same unique key"""
        query = """
            SELECT * FROM attendance_logs
            WHERE user_id = ? AND device_id = ? AND timestamp = ? AND method = ? AND action = ?
        """
        row = db_manager.fetch_one(
            query, (user_id, device_id, timestamp, method, action)
        )
        return self._row_to_log(row) if row else None

    def create_safe(self, log: AttendanceLog) -> tuple[AttendanceLog, bool]:
        """Create attendance log safely, avoiding duplicates

        Returns:
            tuple: (AttendanceLog, is_new) where is_new indicates if record was actually created
        """
        # Check for existing duplicate
        existing = self.find_duplicate(
            log.user_id, log.device_id, log.timestamp, log.method, log.action
        )

        if existing:
            # Duplicate found, return existing record
            return existing, False

        try:
            # Create new record
            return self.create(log), True
        except Exception as e:
            # Handle unique constraint violation (race condition)
            if "UNIQUE constraint failed" in str(e) or "unique_attendance" in str(e):
                # Another thread created the record, fetch and return it
                existing = self.find_duplicate(
                    log.user_id, log.device_id, log.timestamp, log.method, log.action
                )
                if existing:
                    return existing, False
            # Re-raise other exceptions
            raise

    def bulk_insert_ignore(self, logs: List[AttendanceLog]) -> tuple[int, int]:
        """Insert a batch of attendance logs using INSERT OR IGNORE semantics.

        Args:
            logs: AttendanceLog items to persist.

        Returns:
            Tuple of (inserted_count, skipped_count).
        """
        if not logs:
            return 0, 0

        conn = db_manager.get_connection()
        before_changes = conn.total_changes

        rows = []
        for log in logs:
            timestamp = log.timestamp
            if isinstance(timestamp, datetime):
                timestamp_value = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_value = timestamp

            synced_at = log.synced_at
            if isinstance(synced_at, datetime):
                synced_at_value = synced_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                synced_at_value = synced_at

            raw_data_json = json.dumps(log.raw_data) if log.raw_data else None

            rows.append(
                (
                    log.user_id,
                    log.device_id,
                    log.serial_number,
                    timestamp_value,
                    log.method,
                    log.action,
                    raw_data_json,
                    log.sync_status,
                    int(getattr(log, "is_pushed", False)),
                    int(log.is_synced),
                    synced_at_value,
                )
            )

        try:
            conn.executemany(
                """
                INSERT OR IGNORE INTO attendance_logs (
                    user_id, device_id, serial_number, timestamp, method, action,
                    raw_data, sync_status, is_pushed, is_synced, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        inserted_count = conn.total_changes - before_changes
        skipped_count = len(logs) - inserted_count
        return inserted_count, skipped_count

    def _row_to_log(self, row) -> AttendanceLog:
        """Convert database row to AttendanceLog object"""
        raw_data = json.loads(row["raw_data"]) if row["raw_data"] else None

        # Handle serial_number safely for SQLite Row object
        try:
            serial_number = (
                row["serial_number"] if "serial_number" in row.keys() else None
            )
        except (KeyError, IndexError):
            serial_number = None

        # Handle sync_status safely for SQLite Row object
        try:
            sync_status = (
                row["sync_status"]
                if "sync_status" in row.keys() and row["sync_status"]
                else SyncStatus.PENDING
            )
        except (KeyError, IndexError):
            sync_status = SyncStatus.PENDING

        # Handle is_synced safely for SQLite Row object
        try:
            is_synced = bool(row["is_synced"]) if "is_synced" in row.keys() else False
        except (KeyError, IndexError):
            is_synced = False

        # Handle is_pushed safely for SQLite Row object
        try:
            is_pushed = bool(row["is_pushed"]) if "is_pushed" in row.keys() else False
        except (KeyError, IndexError):
            is_pushed = False

        # Handle synced_at safely for SQLite Row object
        try:
            synced_at = row["synced_at"] if "synced_at" in row.keys() else None
        except (KeyError, IndexError):
            synced_at = None

        # Handle error_code safely for SQLite Row object
        try:
            error_code = row["error_code"] if "error_code" in row.keys() else None
        except (KeyError, IndexError):
            error_code = None

        # Handle error_message safely for SQLite Row object
        try:
            error_message = (
                row["error_message"] if "error_message" in row.keys() else None
            )
        except (KeyError, IndexError):
            error_message = None

        # Handle original_status safely for SQLite Row object (backward compatible)
        try:
            original_status = (
                row["original_status"] if "original_status" in row.keys() else 0
            )
        except (KeyError, IndexError):
            original_status = 0

        try:
            error_count = row["error_count"] if "error_count" in row.keys() else 0
        except (KeyError, IndexError):
            error_count = 0

        return AttendanceLog(
            id=row["id"],
            user_id=row["user_id"],
            device_id=row["device_id"],
            serial_number=serial_number,
            timestamp=row["timestamp"],
            method=row["method"],
            action=row["action"],
            raw_data=raw_data,
            sync_status=sync_status,
            is_pushed=is_pushed,
            is_synced=is_synced,
            synced_at=synced_at,
            error_code=error_code,
            error_message=error_message,
            created_at=row["created_at"],
            original_status=original_status,  # Safe default to 0 for backward compatibility
            error_count=error_count,
        )

    def get_smart_filtered_by_date(
        self, target_date, device_id: str = None
    ) -> List[AttendanceLog]:
        """Get attendance logs for a date with smart filtering

        Logic:
        - Group by user_id
        - For checkin: prefer synced record, else use first
        - For checkout: prefer synced record, else use last

        Args:
            target_date: date object for the target date
            device_id: optional device filter

        Returns:
            List of filtered AttendanceLog objects
        """
        # Get all logs for the target date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        # Query database
        if device_id:
            query = """
                SELECT * FROM attendance_logs
                WHERE device_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """
            rows = db_manager.fetch_all(
                query, (device_id, start_datetime, end_datetime)
            )
        else:
            query = """
                SELECT * FROM attendance_logs
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """
            rows = db_manager.fetch_all(query, (start_datetime, end_datetime))

        # Convert rows to AttendanceLog objects
        logs = [self._row_to_log(row) for row in rows]

        # Group by user_id
        from collections import defaultdict

        user_groups = defaultdict(list)
        for log in logs:
            user_groups[log.user_id].append(log)

        # Apply smart filtering
        filtered_logs = []
        for user_id, user_logs in user_groups.items():
            # Separate by action type
            checkins = [
                log for log in user_logs if log.action == 0
            ]  # action=0 is checkin
            checkouts = [
                log for log in user_logs if log.action == 1
            ]  # action=1 is checkout

            # For checkin: prefer synced, else use first
            if checkins:
                synced_checkins = [log for log in checkins if log.is_synced]
                if synced_checkins:
                    # Use first synced checkin
                    filtered_logs.append(synced_checkins[0])
                else:
                    # Use first checkin
                    filtered_logs.append(checkins[0])

            # For checkout: prefer synced, else use last
            if checkouts:
                synced_checkouts = [log for log in checkouts if log.is_synced]
                if synced_checkouts:
                    # Use last synced checkout
                    filtered_logs.append(synced_checkouts[-1])
                else:
                    # Use last checkout
                    filtered_logs.append(checkouts[-1])

        # Sort by timestamp descending
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)

        return filtered_logs

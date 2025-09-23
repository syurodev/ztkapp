import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from .db_manager import db_manager

@dataclass
class Device:
    """Device model"""
    id: str
    name: str
    ip: str
    port: int = 4370
    password: int = 0
    timeout: int = 10
    retry_count: int = 3
    retry_delay: int = 2
    ping_interval: int = 30
    force_udp: bool = False
    is_active: bool = True
    device_info: Dict[str, Any] = None
    serial_number: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = asdict(self)
        if self.device_info:
            data['device_info'] = self.device_info
        return data

@dataclass
class User:
    """User model with sync tracking"""
    user_id: str
    name: str
    device_id: Optional[str] = None
    serial_number: Optional[str] = None
    privilege: int = 0
    group_id: int = 0
    card: int = 0
    password: str = ''
    is_synced: bool = False
    synced_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return asdict(self)

class SyncStatus:
    """Sync status constants for attendance logs"""
    PENDING = 'pending'
    SYNCED = 'synced'
    SKIPPED = 'skipped'

@dataclass
class AttendanceLog:
    """Attendance log model with sync tracking"""
    user_id: str
    timestamp: datetime
    method: int  # 1: fingerprint, 4: card
    action: int  # 0: checkin, 1: checkout, 2: overtime start, 3: overtime end, 4: unspecified
    device_id: Optional[str] = None
    serial_number: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    sync_status: str = SyncStatus.PENDING
    is_synced: bool = False  # kept for backward compatibility
    synced_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = asdict(self)
        # Format timestamp as string for JSON serialization
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        return data

@dataclass
class AppSetting:
    """App setting model"""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

class DeviceRepository:
    """Device database operations"""

    def create(self, device: Device) -> Device:
        """Create new device"""
        device_info_json = json.dumps(device.device_info) if device.device_info else None

        query = '''
            INSERT INTO devices (
                id, name, ip, port, password, timeout, retry_count,
                retry_delay, ping_interval, force_udp, is_active, device_info, serial_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        db_manager.execute_query(query, (
            device.id, device.name, device.ip, device.port, device.password,
            device.timeout, device.retry_count, device.retry_delay, device.ping_interval,
            device.force_udp, device.is_active, device_info_json, device.serial_number
        ))

        return self.get_by_id(device.id)

    def get_by_id(self, device_id: str) -> Optional[Device]:
        """Get device by ID"""
        row = db_manager.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        return self._row_to_device(row) if row else None

    def get_all(self) -> List[Device]:
        """Get all devices"""
        rows = db_manager.fetch_all("SELECT * FROM devices ORDER BY created_at DESC")
        return [self._row_to_device(row) for row in rows]

    def update(self, device_id: str, updates: Dict[str, Any]) -> bool:
        """Update device"""
        if 'device_info' in updates and updates['device_info']:
            updates['device_info'] = json.dumps(updates['device_info'])

        updates['updated_at'] = datetime.now()

        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        query = f"UPDATE devices SET {set_clause} WHERE id = ?"

        cursor = db_manager.execute_query(query, (*updates.values(), device_id))
        return cursor.rowcount > 0

    def delete(self, device_id: str) -> bool:
        """Delete device"""
        from zkteco.logger import app_logger

        try:
            app_logger.info(f"DeviceRepository: Starting delete for device_id: {device_id}")

            # Check if device exists first
            existing = db_manager.fetch_one("SELECT id, name FROM devices WHERE id = ?", (device_id,))
            if existing:
                app_logger.info(f"DeviceRepository: Found device to delete: {existing[1]} ({existing[0]})")
            else:
                app_logger.warning(f"DeviceRepository: Device not found for deletion: {device_id}")
                return False

            app_logger.info(f"DeviceRepository: Executing DELETE query for device_id: {device_id}")

            # Execute DELETE and get rowcount within context
            with db_manager.get_cursor() as cursor:
                cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
                rowcount = cursor.rowcount
                success = rowcount > 0
                app_logger.info(f"DeviceRepository: DELETE query affected {rowcount} rows, success: {success}")

            return success

        except Exception as e:
            app_logger.error(f"DeviceRepository: Error deleting device {device_id}: {e}", exc_info=True)
            raise

    def _row_to_device(self, row) -> Device:
        """Convert database row to Device object"""
        device_info = json.loads(row['device_info']) if row['device_info'] else {}
        
        # Handle serial_number safely for SQLite Row object
        try:
            serial_number = row['serial_number'] if 'serial_number' in row.keys() else None
        except (KeyError, IndexError):
            serial_number = None
            
        return Device(
            id=row['id'],
            name=row['name'],
            ip=row['ip'],
            port=row['port'],
            password=row['password'],
            timeout=row['timeout'],
            retry_count=row['retry_count'],
            retry_delay=row['retry_delay'],
            ping_interval=row['ping_interval'],
            force_udp=bool(row['force_udp']),
            is_active=bool(row['is_active']),
            device_info=device_info,
            serial_number=serial_number,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class UserRepository:
    """User database operations with sync tracking"""

    def create(self, user: User) -> User:
        """Create new user"""
        query = '''
            INSERT INTO users (
                user_id, name, device_id, serial_number, privilege, group_id, card, password
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''

        cursor = db_manager.execute_query(query, (
            user.user_id, user.name, user.device_id, user.serial_number, user.privilege,
            user.group_id, user.card, user.password
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
        # Handle serial_number safely for SQLite Row object
        try:
            serial_number = row['serial_number'] if 'serial_number' in row.keys() else None
        except (KeyError, IndexError):
            serial_number = None
            
        return User(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            device_id=row['device_id'],
            serial_number=serial_number,
            privilege=row['privilege'],
            group_id=row['group_id'],
            card=row['card'],
            password=row['password'],
            is_synced=bool(row['is_synced']),
            synced_at=row['synced_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class AttendanceRepository:
    """Attendance log database operations"""

    def create(self, log: AttendanceLog) -> AttendanceLog:
        """Create attendance log"""
        raw_data_json = json.dumps(log.raw_data) if log.raw_data else None

        query = '''
            INSERT INTO attendance_logs (
                user_id, device_id, serial_number, timestamp, method, action, raw_data, sync_status, is_synced, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        cursor = db_manager.execute_query(query, (
            log.user_id, log.device_id, log.serial_number, log.timestamp, log.method, log.action,
            raw_data_json, log.sync_status, log.is_synced, log.synced_at
        ))

        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, log_id: int) -> Optional[AttendanceLog]:
        """Get attendance log by ID"""
        row = db_manager.fetch_one("SELECT * FROM attendance_logs WHERE id = ?", (log_id,))
        return self._row_to_log(row) if row else None

    def get_all(self, device_id: str = None, limit: int = 1000, offset: int = 0) -> List[AttendanceLog]:
        """Get attendance logs with pagination"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE device_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (device_id, limit, offset)
            )
        else:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        return [self._row_to_log(row) for row in rows]

    def get_total_count(self, device_id: str = None) -> int:
        """Get total count of attendance logs"""
        if device_id:
            result = db_manager.fetch_one(
                "SELECT COUNT(*) as count FROM attendance_logs WHERE device_id = ?",
                (device_id,)
            )
        else:
            result = db_manager.fetch_one("SELECT COUNT(*) as count FROM attendance_logs")
        return result['count'] if result else 0

    def get_by_user(self, user_id: str, limit: int = 100) -> List[AttendanceLog]:
        """Get attendance logs for specific user"""
        rows = db_manager.fetch_all(
            "SELECT * FROM attendance_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        return [self._row_to_log(row) for row in rows]

    def get_unsynced_logs(self, device_id: str = None, limit: int = 1000) -> List[AttendanceLog]:
        """Get attendance logs that haven't been synced (pending status)"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? AND device_id = ? ORDER BY timestamp DESC LIMIT ?",
                (SyncStatus.PENDING, device_id, limit)
            )
        else:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? ORDER BY timestamp DESC LIMIT ?",
                (SyncStatus.PENDING, limit)
            )
        return [self._row_to_log(row) for row in rows]

    def get_logs_by_sync_status(self, sync_status: str, device_id: str = None, limit: int = 1000) -> List[AttendanceLog]:
        """Get attendance logs by sync status"""
        if device_id:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? AND device_id = ? ORDER BY timestamp DESC LIMIT ?",
                (sync_status, device_id, limit)
            )
        else:
            rows = db_manager.fetch_all(
                "SELECT * FROM attendance_logs WHERE sync_status = ? ORDER BY timestamp DESC LIMIT ?",
                (sync_status, limit)
            )
        return [self._row_to_log(row) for row in rows]
    
    def mark_as_synced(self, log_id: int) -> bool:
        """Mark attendance log as synced"""
        query = "UPDATE attendance_logs SET sync_status = ?, is_synced = TRUE, synced_at = ? WHERE id = ?"
        cursor = db_manager.execute_query(query, (SyncStatus.SYNCED, datetime.now(), log_id))
        return cursor.rowcount > 0

    def mark_as_unsynced(self, log_id: int) -> bool:
        """Mark attendance log as not synced (for re-sync scenarios)"""
        query = "UPDATE attendance_logs SET sync_status = ?, is_synced = FALSE, synced_at = NULL WHERE id = ?"
        cursor = db_manager.execute_query(query, (SyncStatus.PENDING, log_id))
        return cursor.rowcount > 0

    def update_sync_status(self, log_id: int, sync_status: str) -> bool:
        """Update sync status of attendance log"""
        synced_at = datetime.now() if sync_status == SyncStatus.SYNCED else None
        is_synced = sync_status == SyncStatus.SYNCED

        query = "UPDATE attendance_logs SET sync_status = ?, is_synced = ?, synced_at = ? WHERE id = ?"
        cursor = db_manager.execute_query(query, (sync_status, is_synced, synced_at, log_id))
        return cursor.rowcount > 0

    def mark_records_as_skipped(self, log_ids: List[int]) -> int:
        """Mark multiple attendance logs as skipped"""
        if not log_ids:
            return 0

        placeholders = ','.join(['?' for _ in log_ids])
        query = f"UPDATE attendance_logs SET sync_status = ? WHERE id IN ({placeholders})"
        cursor = db_manager.execute_query(query, (SyncStatus.SKIPPED, *log_ids))
        return cursor.rowcount
    
    def get_sync_stats(self, device_id: str = None) -> Dict[str, int]:
        """Get sync statistics"""
        base_query = "SELECT sync_status, COUNT(*) as count FROM attendance_logs"
        if device_id:
            query = f"{base_query} WHERE device_id = ? GROUP BY sync_status"
            rows = db_manager.fetch_all(query, (device_id,))
        else:
            query = f"{base_query} GROUP BY sync_status"
            rows = db_manager.fetch_all(query)

        stats = {"pending": 0, "synced": 0, "skipped": 0, "total": 0}
        for row in rows:
            sync_status = row['sync_status'] or 'pending'  # Handle null values
            if sync_status in stats:
                stats[sync_status] = row['count']

        stats["total"] = sum(stats[key] for key in ['pending', 'synced', 'skipped'])
        return stats

    def get_pending_sync_dates(self, device_id: str = None) -> List[str]:
        """Get all dates that have pending attendance records"""
        if device_id:
            query = """
                SELECT DISTINCT DATE(timestamp) as sync_date
                FROM attendance_logs
                WHERE sync_status = ? AND device_id = ?
                ORDER BY sync_date
            """
            rows = db_manager.fetch_all(query, (SyncStatus.PENDING, device_id))
        else:
            query = """
                SELECT DISTINCT DATE(timestamp) as sync_date
                FROM attendance_logs
                WHERE sync_status = ?
                ORDER BY sync_date
            """
            rows = db_manager.fetch_all(query, (SyncStatus.PENDING,))

        return [row['sync_date'] for row in rows]

    def has_synced_record_for_date_action(self, user_id: str, target_date: str, action: int, device_id: str = None) -> bool:
        """Check if user has any synced record for specific date and action type"""
        if device_id:
            query = """
                SELECT COUNT(*) as count
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ? AND device_id = ?
            """
            result = db_manager.fetch_one(query, (user_id, target_date, action, SyncStatus.SYNCED, device_id))
        else:
            query = """
                SELECT COUNT(*) as count
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ?
            """
            result = db_manager.fetch_one(query, (user_id, target_date, action, SyncStatus.SYNCED))

        return result['count'] > 0 if result else False

    def get_other_records_for_date_action(self, user_id: str, target_date: str, action: int, exclude_log_id: int, device_id: str = None) -> List[int]:
        """Get IDs of other records for same user, date, and action (excluding specific log)"""
        if device_id:
            query = """
                SELECT id
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND id != ? AND device_id = ? AND sync_status = ?
            """
            rows = db_manager.fetch_all(query, (user_id, target_date, action, exclude_log_id, device_id, SyncStatus.PENDING))
        else:
            query = """
                SELECT id
                FROM attendance_logs
                WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND id != ? AND sync_status = ?
            """
            rows = db_manager.fetch_all(query, (user_id, target_date, action, exclude_log_id, SyncStatus.PENDING))

        return [row['id'] for row in rows]

    def find_duplicate(self, user_id: str, device_id: str, timestamp: datetime, method: int, action: int) -> Optional[AttendanceLog]:
        """Find existing attendance record with same unique key"""
        query = """
            SELECT * FROM attendance_logs 
            WHERE user_id = ? AND device_id = ? AND timestamp = ? AND method = ? AND action = ?
        """
        row = db_manager.fetch_one(query, (user_id, device_id, timestamp, method, action))
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

    def _row_to_log(self, row) -> AttendanceLog:
        """Convert database row to AttendanceLog object"""
        raw_data = json.loads(row['raw_data']) if row['raw_data'] else None

        # Handle serial_number safely for SQLite Row object
        try:
            serial_number = row['serial_number'] if 'serial_number' in row.keys() else None
        except (KeyError, IndexError):
            serial_number = None

        # Handle sync_status safely for SQLite Row object
        try:
            sync_status = row['sync_status'] if 'sync_status' in row.keys() and row['sync_status'] else SyncStatus.PENDING
        except (KeyError, IndexError):
            sync_status = SyncStatus.PENDING

        # Handle is_synced safely for SQLite Row object
        try:
            is_synced = bool(row['is_synced']) if 'is_synced' in row.keys() else False
        except (KeyError, IndexError):
            is_synced = False

        # Handle synced_at safely for SQLite Row object
        try:
            synced_at = row['synced_at'] if 'synced_at' in row.keys() else None
        except (KeyError, IndexError):
            synced_at = None

        return AttendanceLog(
            id=row['id'],
            user_id=row['user_id'],
            device_id=row['device_id'],
            serial_number=serial_number,
            timestamp=row['timestamp'],
            method=row['method'],
            action=row['action'],
            raw_data=raw_data,
            sync_status=sync_status,
            is_synced=is_synced,
            synced_at=synced_at,
            created_at=row['created_at']
        )

class SettingRepository:
    """App settings database operations"""

    def get(self, key: str) -> Optional[str]:
        """Get setting value"""
        row = db_manager.fetch_one("SELECT value FROM app_settings WHERE key = ?", (key,))
        return row['value'] if row else None

    def set(self, key: str, value: str, description: str = None) -> bool:
        """Set setting value"""
        query = '''
            INSERT OR REPLACE INTO app_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        '''
        cursor = db_manager.execute_query(query, (key, value, description, datetime.now()))
        return cursor.rowcount > 0

    def get_all(self) -> Dict[str, str]:
        """Get all settings as dictionary"""
        rows = db_manager.fetch_all("SELECT key, value FROM app_settings")
        return {row['key']: row['value'] for row in rows}

# Repository instances
device_repo = DeviceRepository()
user_repo = UserRepository()
attendance_repo = AttendanceRepository()
setting_repo = SettingRepository()

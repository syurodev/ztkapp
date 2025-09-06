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

@dataclass
class AttendanceLog:
    """Attendance log model"""
    user_id: str
    timestamp: datetime
    method: int  # 1: fingerprint, 4: card
    action: int  # 0: checkin, 1: checkout, 2: overtime start, 3: overtime end, 4: unspecified
    device_id: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
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
                retry_delay, ping_interval, force_udp, is_active, device_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        db_manager.execute_query(query, (
            device.id, device.name, device.ip, device.port, device.password,
            device.timeout, device.retry_count, device.retry_delay, device.ping_interval,
            device.force_udp, device.is_active, device_info_json
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
        cursor = db_manager.execute_query("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount > 0
    
    def _row_to_device(self, row) -> Device:
        """Convert database row to Device object"""
        device_info = json.loads(row['device_info']) if row['device_info'] else {}
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
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class UserRepository:
    """User database operations with sync tracking"""
    
    def create(self, user: User) -> User:
        """Create new user"""
        query = '''
            INSERT INTO users (
                user_id, name, device_id, privilege, group_id, card, password
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        
        cursor = db_manager.execute_query(query, (
            user.user_id, user.name, user.device_id, user.privilege,
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
        return User(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            device_id=row['device_id'],
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
                user_id, device_id, timestamp, method, action, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?)
        '''
        
        cursor = db_manager.execute_query(query, (
            log.user_id, log.device_id, log.timestamp, log.method, log.action, raw_data_json
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
    
    def get_by_user(self, user_id: str, limit: int = 100) -> List[AttendanceLog]:
        """Get attendance logs for specific user"""
        rows = db_manager.fetch_all(
            "SELECT * FROM attendance_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        return [self._row_to_log(row) for row in rows]
    
    def _row_to_log(self, row) -> AttendanceLog:
        """Convert database row to AttendanceLog object"""
        raw_data = json.loads(row['raw_data']) if row['raw_data'] else None
        return AttendanceLog(
            id=row['id'],
            user_id=row['user_id'],
            device_id=row['device_id'],
            timestamp=row['timestamp'],
            method=row['method'],
            action=row['action'],
            raw_data=raw_data,
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
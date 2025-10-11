from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime

class SyncStatus:
    """Sync status constants for attendance logs"""
    PENDING = 'pending'
    SYNCED = 'synced'
    SKIPPED = 'skipped'
    ERROR = 'error'

@dataclass
class AttendanceLog:
    """Attendance log model with sync tracking"""
    user_id: str
    timestamp: datetime
    method: int  # VERIFY code: 0=password, 1=fingerprint, 2=face, 3=card, 4=combined
    action: int  # Smart status: 0=checkin, 1=checkout, 2=break start, 3=break end, 4=overtime start, 5=overtime end
    device_id: Optional[str] = None
    serial_number: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    sync_status: str = SyncStatus.PENDING
    is_synced: bool = False  # kept for backward compatibility
    synced_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    original_status: int = 0  # Original STATUS from device (255=undefined for push, same as action for pull)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = asdict(self)
        # Format timestamp as string for JSON serialization
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        return data

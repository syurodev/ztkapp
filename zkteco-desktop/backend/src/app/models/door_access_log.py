"""
Door Access Log model
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DoorAccessLog:
    """Door Access Log model for tracking door access events"""

    id: Optional[int] = None
    door_id: int = 0
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str = ""  # unlock, lock, access_granted, access_denied
    status: str = ""  # success, failed, error
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None
    is_synced: bool = False
    synced_at: Optional[datetime] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""

        def serialize_datetime(dt):
            """Serialize datetime to ISO format string"""
            if dt is None:
                return None
            if isinstance(dt, str):
                return dt
            if isinstance(dt, datetime):
                return dt.isoformat()
            return str(dt)

        return {
            "id": self.id,
            "door_id": self.door_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action": self.action,
            "status": self.status,
            "timestamp": serialize_datetime(self.timestamp),
            "notes": self.notes,
            "is_synced": self.is_synced,
            "synced_at": serialize_datetime(self.synced_at),
        }

    @staticmethod
    def from_dict(data: dict) -> "DoorAccessLog":
        """Create DoorAccessLog instance from dictionary"""
        return DoorAccessLog(
            id=data.get("id"),
            door_id=data.get("door_id", 0),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            action=data.get("action", ""),
            status=data.get("status", ""),
            timestamp=data.get("timestamp"),
            notes=data.get("notes"),
            is_synced=data.get("is_synced", False),
            synced_at=data.get("synced_at"),
        )

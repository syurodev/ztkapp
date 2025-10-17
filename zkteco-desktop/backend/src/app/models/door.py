"""
Door model
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Door:
    """Door model representing a physical door controlled by a device"""

    id: Optional[int] = None
    name: str = ""
    device_id: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"  # active, inactive, error
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
            "name": self.name,
            "device_id": self.device_id,
            "location": self.location,
            "description": self.description,
            "status": self.status,
            "created_at": serialize_datetime(self.created_at),
            "updated_at": serialize_datetime(self.updated_at),
        }

    @staticmethod
    def from_dict(data: dict) -> "Door":
        """Create Door instance from dictionary"""
        return Door(
            id=data.get("id"),
            name=data.get("name", ""),
            device_id=data.get("device_id"),
            location=data.get("location"),
            description=data.get("description"),
            status=data.get("status", "active"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

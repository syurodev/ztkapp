from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

@dataclass
class User:
    """User model with sync tracking"""
    user_id: str
    name: str  # Name from device (fallback)
    device_id: Optional[str] = None
    serial_number: Optional[str] = None
    privilege: int = 0
    group_id: int = 0
    card: int = 0
    password: str = ''
    is_synced: bool = False
    synced_at: Optional[datetime] = None
    external_user_id: Optional[int] = None  # bigint from external API
    avatar_url: Optional[str] = None
    # New fields from external API
    full_name: Optional[str] = None  # Họ tên đầy đủ từ API external
    employee_code: Optional[str] = None  # Mã nhân viên
    position: Optional[str] = None  # Chức vụ
    department: Optional[str] = None  # Phòng ban
    notes: Optional[str] = None  # Ghi chú
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return asdict(self)

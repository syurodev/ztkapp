from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class AppSetting:
    """App setting model"""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

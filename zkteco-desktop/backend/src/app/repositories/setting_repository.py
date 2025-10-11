from typing import Dict, Optional
from datetime import datetime
from app.database.connection import db_manager

class Setting:
    """Setting model"""
    def __init__(self, key: str, value: str, description: str = None):
        self.key = key
        self.value = value
        self.description = description

class SettingRepository:
    """App settings database operations"""

    def get(self, key: str) -> Optional[Setting]:
        """Get setting"""
        row = db_manager.fetch_one("SELECT * FROM app_settings WHERE key = ?", (key,))
        if row:
            return Setting(
                key=row['key'],
                value=row['value'],
                description=row['description'] if 'description' in row.keys() else None
            )
        return None

    def get_value(self, key: str) -> Optional[str]:
        """Get setting value only"""
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

    def initialize_defaults(self):
        """Initialize default settings if they don't exist"""
        defaults = {
            'cleanup_retention_days': {
                'value': '365',
                'description': 'Number of days to retain attendance records before cleanup (default: 365 = 1 year)'
            },
            'cleanup_enabled': {
                'value': 'true',
                'description': 'Enable/disable automatic monthly cleanup of old attendance records'
            }
        }

        for key, config in defaults.items():
            existing = self.get(key)
            if not existing:
                self.set(key, config['value'], config['description'])

# Global instance
setting_repo = SettingRepository()

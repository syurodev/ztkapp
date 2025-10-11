from app.repositories.device_repository import DeviceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.setting_repository import SettingRepository

# Repository instances
device_repo = DeviceRepository()
user_repo = UserRepository()
attendance_repo = AttendanceRepository()
setting_repo = SettingRepository()

__all__ = [
    'DeviceRepository',
    'UserRepository',
    'AttendanceRepository',
    'SettingRepository',
    'device_repo',
    'user_repo',
    'attendance_repo',
    'setting_repo',
]

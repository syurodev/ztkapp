from app.repositories.device_repository import DeviceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.door_repository import DoorRepository
from app.repositories.door_access_repository import DoorAccessRepository

# Repository instances
device_repo = DeviceRepository()
user_repo = UserRepository()
attendance_repo = AttendanceRepository()
setting_repo = SettingRepository()
door_repo = DoorRepository()
door_access_repo = DoorAccessRepository()


__all__ = [
    "DeviceRepository",
    "UserRepository",
    "AttendanceRepository",
    "SettingRepository",
    "DoorRepository",
    "DoorAccessRepository",
    "device_repo",
    "user_repo",
    "attendance_repo",
    "setting_repo",
    "door_repo",
    "door_access_repo",
]

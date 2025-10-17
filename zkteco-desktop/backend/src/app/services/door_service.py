"""
Door Service for handling door control operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from app.shared.logger import app_logger
from app.device.connection_manager import connection_manager
from app.repositories.door_repository import DoorRepository
from app.repositories.door_access_repository import DoorAccessRepository
from app.models.door import Door
from app.models.door_access_log import DoorAccessLog
from app.services.device_service import get_zk_service


class DoorService:
    """Service for door control and management"""

    def __init__(self):
        self.door_repo = DoorRepository()
        self.access_repo = DoorAccessRepository()

    def sync_logs_from_attendance(self, door_id: int) -> int:
        """Sync attendance logs as door access logs"""
        app_logger.info(f"Syncing attendance logs to door {door_id}")

        # 1. Get door information to ensure it exists
        door = self.door_repo.get_by_id(door_id)
        if not door:
            raise ValueError(f"Door {door_id} not found")

        # 2. Fetch attendance logs from the device
        # Get the service instance dynamically
        zk_service = get_zk_service(door.device_id)
        attendance_result = zk_service.get_attendance()
        if isinstance(attendance_result, dict) and "records" in attendance_result:
            attendance_logs = attendance_result["records"]
        else:
            # Handle case where the result might just be the list
            attendance_logs = attendance_result

        if not attendance_logs:
            app_logger.info("No new attendance logs to sync.")
            return 0

        # 3. Create a set of existing log timestamps for the given door to avoid duplicates
        existing_logs = self.access_repo.get_by_door_id(
            door_id, limit=10000
        )  # A large limit to get recent logs
        existing_timestamps = {log.timestamp for log in existing_logs}

        # 4. Iterate and create new access logs
        new_logs_count = 0
        for att_log in attendance_logs:
            # Check if a log with the same user and timestamp already exists for this door
            if att_log.timestamp in existing_timestamps:
                continue

            log_entry = DoorAccessLog(
                door_id=door_id,
                user_id=att_log.user_id,
                user_name=None,  # User name can be fetched and mapped later if needed
                action="unlock",
                status="success",
                timestamp=att_log.timestamp,
                notes=f"Synced from attendance log (Punch: {att_log.punch}, Status: {att_log.status})",
            )
            self.access_repo.create(log_entry)
            new_logs_count += 1

        app_logger.info(
            f"Synced {new_logs_count} new attendance logs to door {door_id}"
        )
        return new_logs_count

    def _check_pull_device(self, device_id: str) -> None:
        """Check if device is pull type, raise ValueError if not"""
        from app.utils.device_helpers import require_pull_device

        require_pull_device(device_id)

    def unlock_door(
        self,
        door_id: int,
        duration: int = 3,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Unlock a door for specified duration

        Args:
            door_id: ID of the door to unlock
            duration: Unlock duration in seconds (default 3)
            user_id: Optional user ID who triggered the unlock
            user_name: Optional user name who triggered the unlock

        Returns:
            Dictionary with status and message
        """
        app_logger.info(f"Unlocking door {door_id} for {duration} seconds")

        # Get door information
        door = self.door_repo.get_by_id(door_id)
        if not door:
            raise ValueError(f"Door {door_id} not found")

        # Check if door has device assigned
        if not door.device_id:
            raise ValueError(
                f"Door {door_id} has no device assigned. Please assign a device first."
            )

        # Check device type - only pull devices support door control
        self._check_pull_device(str(door.device_id))

        zk_instance = None
        success = False
        error_message = None

        try:
            # Get connection to the device
            app_logger.info(f"Getting connection for device {door.device_id}...")
            zk_instance = connection_manager.ensure_device_connection(
                str(door.device_id)
            )

            if not zk_instance.is_connect:
                raise Exception("Device not connected")

            # Send unlock command
            app_logger.info(f"Sending unlock command (duration: {duration}s)...")
            result = zk_instance.unlock(time=duration)

            if result:
                success = True
                app_logger.info(f"Door {door_id} unlocked successfully")
            else:
                error_message = "Unlock command failed"
                app_logger.warning(f"Door unlock failed for door {door_id}")

        except Exception as e:
            success = False
            error_message = str(e)
            app_logger.error(f"Error unlocking door {door_id}: {e}", exc_info=True)

        # Log the access attempt
        log_entry = DoorAccessLog(
            door_id=door_id,
            user_id=user_id,
            user_name=user_name,
            action="unlock",
            status="success" if success else "failed",
            notes=error_message if error_message else f"Unlocked for {duration}s",
        )
        self.access_repo.create(log_entry)

        if not success:
            raise Exception(f"Failed to unlock door: {error_message}")

        return {
            "success": True,
            "message": f"Door unlocked for {duration} seconds",
            "door_id": door_id,
            "duration": duration,
        }

    def get_door_state(self, door_id: int) -> Dict[str, Any]:
        """
        Get current state of a door

        Args:
            door_id: ID of the door

        Returns:
            Dictionary with door state information
        """
        app_logger.info(f"Getting state for door {door_id}")

        door = self.door_repo.get_by_id(door_id)
        if not door:
            raise ValueError(f"Door {door_id} not found")

        # Get device connection status only if device is assigned
        is_connected = False
        if door.device_id:
            try:
                zk_instance = connection_manager.ensure_device_connection(
                    str(door.device_id)
                )
                is_connected = zk_instance.is_connect if zk_instance else False
            except:
                is_connected = False

        return {
            "door_id": door_id,
            "name": door.name,
            "status": door.status,
            "device_connected": is_connected,
            "device_id": door.device_id,
            "location": door.location,
        }

    def create_door(self, door_data: Dict[str, Any]) -> Door:
        """Create a new door"""
        app_logger.info(f"Creating new door: {door_data.get('name')}")

        door = Door(
            name=door_data.get("name", ""),
            device_id=door_data.get("device_id"),
            location=door_data.get("location"),
            description=door_data.get("description"),
            status=door_data.get("status", "active"),
        )

        return self.door_repo.create(door)

    def update_door(self, door_id: int, updates: Dict[str, Any]) -> bool:
        """Update door information"""
        app_logger.info(f"Updating door {door_id}")
        return self.door_repo.update(door_id, updates)

    def delete_door(self, door_id: int) -> bool:
        """Delete a door"""
        app_logger.info(f"Deleting door {door_id}")
        return self.door_repo.delete(door_id)

    def get_door(self, door_id: int) -> Optional[Door]:
        """Get door by ID"""
        return self.door_repo.get_by_id(door_id)

    def get_all_doors(self) -> List[Door]:
        """Get all doors"""
        return self.door_repo.get_all()

    def get_doors_by_device(self, device_id: int) -> List[Door]:
        """Get all doors for a specific device"""
        return self.door_repo.get_by_device_id(device_id)

    def get_access_logs(
        self,
        door_id: Optional[int] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DoorAccessLog]:
        """
        Get door access logs

        Args:
            door_id: Filter by door ID (optional)
            user_id: Filter by user ID (optional)
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of door access logs
        """
        if door_id:
            return self.access_repo.get_by_door_id(door_id, limit, offset)
        elif user_id:
            return self.access_repo.get_by_user_id(user_id, limit, offset)
        else:
            return self.access_repo.get_all(limit, offset)


# Create singleton instance
door_service = DoorService()

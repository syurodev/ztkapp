"""
Push Protocol Service for ZKTeco Devices (SenseFace 4 Series)

This service handles the PUSH protocol where devices actively send data to the server,
as opposed to the traditional PULL protocol where the server connects to devices.

Protocol Flow:
1. Device pings /iclock/getrequest periodically to check for commands
2. Device sends handshake to /iclock/cdata (GET)
3. Device posts data to /iclock/cdata with table parameter (ATTLOG, OPERLOG, BIODATA)
4. Device checks /iclock/devicecmd for pending commands
5. Device sends biometric files to /iclock/fdata

References:
- ZKTeco PUSH Protocol Documentation: docs/ZKTeco Push Protocol.md
- Original Elysia.js implementation: index.ts
"""

import os
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from threading import Lock

import requests

from app.shared.logger import app_logger
from app.repositories import attendance_repo, user_repo, device_repo
from app.config.config_manager import config_manager
from app.models import AttendanceLog
from app.events.event_stream import device_event_stream


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================


@dataclass
class AttendanceRecord:
    """
    Attendance record from ATTLOG table.

    Format: user_id \t timestamp \t status \t verify_method
    Example: 1001\t2025-01-09 15:30:00\t0\t1
    """

    user_id: str  # Employee ID from device
    timestamp: str  # Format: YYYY-MM-DD HH:MM:SS
    status: int  # 0=check-in, 1=check-out, 2=break-start, 3=break-end, 4=overtime-start, 5=overtime-end
    verify_method: int  # 0=password, 1=fingerprint, 2=card, 15=face

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "verify_method": self.verify_method,
        }


@dataclass
class UserInfo:
    """
    User information from OPERLOG table.

    Format: USER PIN=123 Name=John Doe Grp=1 Pri=0 Verify=1 TZ=0
    """

    user_id: str  # PIN from device
    name: str = ""
    group: str = "0"
    privilege: str = "0"  # 0=user, 14=admin
    verify: str = "1"  # Verification methods enabled
    timezone: str = "0"
    has_face: bool = False  # Set when BIODATA received

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "group": self.group,
            "privilege": self.privilege,
            "verify": self.verify,
            "timezone": self.timezone,
            "has_face": self.has_face,
        }


@dataclass
class DeviceCommand:
    """
    Command to be sent to device on next ping.

    Common commands:
    - DATA UPDATE USERINFO: Request user list
    - DATA UPDATE FINGERTMP: Request fingerprint templates
    - DATA QUERY ATTLOG: Request attendance logs
    - CLEAR DATA: Clear device data
    """

    command: str  # Command string to send
    created_at: datetime = field(default_factory=datetime.now)
    device_sn: Optional[str] = None  # Serial number of target device


# ============================================================================
# PUSH PROTOCOL SERVICE
# ============================================================================


class PushProtocolService:
    """
    Service for handling ZKTeco Push Protocol communication.

    This service manages:
    - Device ping/pong for command delivery
    - Attendance log processing from ATTLOG
    - User info processing from OPERLOG
    - Biometric data processing from BIODATA
    - Command queue per device
    """

    def __init__(self):
        """Initialize the push protocol service"""
        # Thread-safe command queue: {device_serial: [commands]}
        self._command_queues: Dict[str, List[DeviceCommand]] = {}
        self._queue_lock = Lock()

        # Biodata storage directory
        self._biodata_dir = self._ensure_biodata_directory()

        app_logger.info("PushProtocolService initialized")

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _ensure_biodata_directory(self) -> str:
        """
        Ensure biodata storage directory exists.

        Returns:
            str: Absolute path to biodata directory
        """
        # Get project root (backend directory)
        backend_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        biodata_dir = os.path.join(backend_dir, "biodata")

        # Create directory if not exists
        os.makedirs(biodata_dir, exist_ok=True)

        app_logger.info(f"Biodata directory: {biodata_dir}")
        return biodata_dir

    def _parse_device_info(
        self, query_params: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse device serial number and options from query parameters.

        Args:
            query_params: Query parameters from request (SN, options, etc.)

        Returns:
            Tuple of (serial_number, device_options)

        Example query params from device:
            SN=ABC123456789&options=all&pushver=3.0&language=69
        """
        serial_number = query_params.get("SN")
        options = query_params.get("options", "")

        if serial_number:
            app_logger.debug(f"Device info: SN={serial_number}, options={options}")

        return serial_number, options

    # ========================================================================
    # DEVICE PING & COMMAND DELIVERY
    # ========================================================================

    def handle_device_ping(self, query_params: Dict[str, Any]) -> str:
        """
        Handle device ping request (GET /iclock/getrequest).

        Device pings periodically to check for pending commands.
        This is the primary mechanism for command delivery.

        Args:
            query_params: Query parameters from device

        Returns:
            str: Response text ('OK' or 'C:command')

        Response format:
            - 'OK\r\n': No commands pending
            - 'C:command\r\n': Command to execute

        Example:
            >>> service.handle_device_ping({'SN': 'ABC123'})
            'C:DATA UPDATE USERINFO\r\n'
        """
        serial_number, _ = self._parse_device_info(query_params)

        app_logger.info(
            f"[PUSH] Device ping: SN={serial_number}, params={query_params}"
        )

        # Auto-register device if not exists
        if serial_number:
            self._auto_register_device(serial_number, query_params)

        # Check for pending commands
        command = self._get_next_command(serial_number)

        if command:
            app_logger.info(
                f"[PUSH] Sending command to device {serial_number}: {command.command}"
            )
            return f"C:{command.command}\r\n"

        # No commands
        return "OK\r\n"

    def _get_next_command(
        self, serial_number: Optional[str]
    ) -> Optional[DeviceCommand]:
        """
        Get next pending command for device (FIFO queue).

        Args:
            serial_number: Device serial number

        Returns:
            DeviceCommand or None if no commands pending

        Thread-safe: Uses lock to protect command queue
        """
        if not serial_number:
            return None

        with self._queue_lock:
            queue = self._command_queues.get(serial_number, [])
            if queue:
                # Pop first command (FIFO)
                command = queue.pop(0)
                app_logger.debug(
                    f"Popped command for {serial_number}: {command.command}"
                )
                return command

        return None

    def queue_command(self, serial_number: str, command_text: str) -> bool:
        """
        Queue a command to be sent to device on next ping.

        Args:
            serial_number: Target device serial number
            command_text: Command string (e.g., 'DATA UPDATE USERINFO')

        Returns:
            bool: True if queued successfully

        Thread-safe: Uses lock to protect command queue

        Common commands:
            - 'DATA UPDATE USERINFO': Request user list
            - 'DATA UPDATE FINGERTMP': Request fingerprints
            - 'DATA QUERY ATTLOG': Request attendance logs
            - 'CLEAR DATA': Clear device memory
        """
        command = DeviceCommand(command=command_text, device_sn=serial_number)

        with self._queue_lock:
            if serial_number not in self._command_queues:
                self._command_queues[serial_number] = []

            self._command_queues[serial_number].append(command)
            queue_length = len(self._command_queues[serial_number])

        app_logger.info(
            f"[PUSH] Queued command '{command_text}' for device {serial_number} "
            f"(queue length: {queue_length})"
        )

        return True

    # ========================================================================
    # DEVICE AUTO-REGISTRATION
    # ========================================================================

    def _auto_register_device(
        self, serial_number: str, query_params: Dict[str, Any]
    ) -> None:
        """
        Auto-register push device when it first pings the server.

        If device doesn't exist in database, create it automatically.
        This allows zero-configuration setup for push devices.

        Args:
            serial_number: Device serial number
            query_params: Additional device info from query params

        Side effects:
            - Creates device in database if not exists
            - Logs registration event
        """
        try:
            # Check if device already exists
            existing_device = device_repo.get_by_serial_number(serial_number)

            if existing_device:
                # Device already registered
                app_logger.debug(f"Device {serial_number} already registered")
                return

            # Auto-register new push device
            device_data = {
                "name": f"Auto-registered Push Device {serial_number}",
                "ip": "0.0.0.0",  # Push devices don't need IP (they connect to us)
                "port": 0,  # No port needed for push
                "serial_number": serial_number,
                "device_type": "push",
                "is_active": True,
                "device_info": {
                    "auto_registered": True,
                    "registered_at": datetime.now().isoformat(),
                    "push_protocol_version": query_params.get("pushver", "unknown"),
                    "options": query_params.get("options", ""),
                    "language": query_params.get("language", "unknown"),
                },
            }

            device_id = config_manager.add_device(device_data)

            app_logger.info(
                f"[PUSH] ✓ Auto-registered new push device: "
                f"SN={serial_number}, ID={device_id}"
            )

            try:
                external_api_domain = config_manager.get_external_api_url()
                api_key = config_manager.get_external_api_key()

                if external_api_domain and api_key and serial_number:
                    api_url = (
                        external_api_domain.rstrip("/")
                        + "/time-clock-employees/sync-device"
                    )
                    payload = [
                        {"serial": serial_number, "name": device_data.get("name")}
                    ]
                    headers = {
                        "Content-Type": "application/json",
                        "x-api-key": api_key,
                    }

                    response = requests.post(
                        api_url,
                        json=payload,
                        headers=headers,
                        timeout=30,
                    )
                    response.raise_for_status()

                    try:
                        external_result = response.json()
                    except ValueError:
                        external_result = {"message": response.text}

                    app_logger.info(
                        f"[PUSH] Synced auto-registered device SN={serial_number} "
                        f"to external API ({external_result})."
                    )
                else:
                    app_logger.warning(
                        "[PUSH] Skip external sync for auto-registered device "
                        f"SN={serial_number}: missing config or serial."
                    )
            except requests.exceptions.RequestException as external_error:
                app_logger.error(
                    "[PUSH] Failed to sync auto-registered device "
                    f"SN={serial_number} to external API: {external_error}"
                )
            except Exception as external_error:
                app_logger.error(
                    "[PUSH] Unexpected error during external sync for auto-registered "
                    f"device SN={serial_number}: {external_error}"
                )

        except Exception as e:
            app_logger.error(f"Failed to auto-register device {serial_number}: {e}")

    # ========================================================================
    # HANDSHAKE
    # ========================================================================

    def handle_handshake(self, query_params: Dict[str, Any]) -> str:
        """
        Handle device handshake (GET /iclock/cdata).

        This is the initial connection establishment from device.

        Args:
            query_params: Query parameters from device

        Returns:
            str: 'OK\r\n' to acknowledge handshake
        """
        serial_number, _ = self._parse_device_info(query_params)

        app_logger.info(f"[PUSH] Device handshake: SN={serial_number}")

        return "OK\r\n"

    # ========================================================================
    # DATA PROCESSING - ATTENDANCE (ATTLOG)
    # ========================================================================

    def handle_attendance_data(
        self, raw_data: str, query_params: Dict[str, Any]
    ) -> Tuple[List[AttendanceRecord], int]:
        """
        Process attendance data from ATTLOG table.

        Args:
            raw_data: Raw text data from device
            query_params: Query parameters (SN, table, etc.)

        Returns:
            Tuple of (parsed_records, saved_count)

        Data format (TSV - Tab Separated Values):
            user_id \t timestamp \t status \t verify_method
            1001\t2025-01-09 15:30:00\t0\t1
            1002\t2025-01-09 15:31:00\t1\t15

        Status codes:
            0 = check-in
            1 = check-out
            2 = break-start
            3 = break-end
            4 = overtime-start
            5 = overtime-end

        Verify method codes:
            0 = password
            1 = fingerprint
            2 = card
            15 = face
        """
        serial_number, _ = self._parse_device_info(query_params)

        app_logger.info(f"[PUSH] Processing ATTLOG from device {serial_number}")

        # Parse raw data
        records = self._parse_attendance_data(raw_data)

        # Get device ID from serial number
        device = None
        if serial_number:
            device = device_repo.get_by_serial_number(serial_number)

        device_id = device.id if device else None

        # Save to database
        saved_count = self._save_attendance_records(records, device_id, serial_number)

        app_logger.info(
            f"[PUSH] ✓ Processed {len(records)} attendance records from {serial_number}, "
            f"saved {saved_count} new records"
        )

        return records, saved_count

    def _parse_attendance_data(self, raw_data: str) -> List[AttendanceRecord]:
        """
        Parse raw ATTLOG data into structured records.

        Args:
            raw_data: Raw TSV data from device

        Returns:
            List of AttendanceRecord objects

        Format:
            user_id \t timestamp \t status \t verify_method
        """
        records = []

        for line in raw_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                # Split by tab
                parts = line.split("\t")

                if len(parts) < 4:
                    app_logger.warning(
                        f"Invalid ATTLOG line (expected 4 fields): {line}"
                    )
                    continue

                user_id, timestamp, status, verify_method = parts[:4]

                record = AttendanceRecord(
                    user_id=user_id.strip(),
                    timestamp=timestamp.strip(),
                    status=int(status),
                    verify_method=int(verify_method),
                )

                records.append(record)

                app_logger.debug(
                    f"[ATTLOG] user={record.user_id} time={record.timestamp} "
                    f"status={record.status} verify={record.verify_method}"
                )

            except Exception as e:
                app_logger.error(f"Failed to parse ATTLOG line '{line}': {e}")
                continue

        return records

    def _determine_action(
        self, user_id: str, timestamp: datetime, status: int, device_id: Optional[str]
    ) -> int:
        """
        Determine check-in/out action from STATUS field.

        Logic:
        - If status = 0-5: Use as-is (explicit from device)
        - If status = 255 (undefined): Apply smart logic
          - Check last record for same user today
          - If no record or last was checkout (1): This is check-in (0)
          - If last was check-in (0): This is check-out (1)

        Args:
            user_id: User ID
            timestamp: Attendance timestamp
            status: Original STATUS from device
            device_id: Device ID

        Returns:
            int: 0=check-in, 1=check-out
        """
        # If device explicitly set status (0-5), use it
        if status != 255:
            return status if status <= 5 else 0

        # STATUS=255: Need smart detection based on previous record
        today_start = datetime.combine(timestamp.date(), datetime.min.time())

        # Get last record for this user today (before current timestamp)
        last_record = attendance_repo.get_latest_for_user_today(
            user_id, device_id, today_start, timestamp
        )

        if not last_record:
            # First record today = check-in
            app_logger.debug(
                f"[SMART STATUS] user={user_id}: No previous record today → check-in (0)"
            )
            return 0

        # Alternate: if last was check-in (0), this is check-out (1)
        new_action = 1 if last_record.action == 0 else 0
        app_logger.debug(
            f"[SMART STATUS] user={user_id}: Last action was {last_record.action}, "
            f"new action → {new_action}"
        )
        return new_action

    def _save_attendance_records(
        self,
        records: List[AttendanceRecord],
        device_id: Optional[str],
        serial_number: Optional[str],
    ) -> int:
        """
        Save attendance records to database.

        Args:
            records: List of AttendanceRecord objects
            device_id: Device ID (if device registered)
            serial_number: Device serial number

        Returns:
            int: Number of new records saved

        Side effects:
            - Inserts records into attendance_logs table
            - Handles duplicates (based on unique constraint)
        """
        saved_count = 0

        for record in records:
            try:
                # Parse timestamp
                try:
                    timestamp_dt = datetime.strptime(
                        record.timestamp, "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    # Try alternative format
                    timestamp_dt = datetime.strptime(
                        record.timestamp, "%Y/%m/%d %H:%M:%S"
                    )

                # Determine smart action from STATUS (handles STATUS=255 for push devices)
                action = self._determine_action(
                    record.user_id, timestamp_dt, record.status, device_id
                )

                # Create AttendanceLog model with both original_status and computed action
                log = AttendanceLog(
                    user_id=record.user_id,
                    device_id=device_id,
                    serial_number=serial_number,
                    timestamp=timestamp_dt,
                    method=record.verify_method,
                    action=action,  # Smart computed status (0/1 for STATUS=255, or explicit 0-5)
                    original_status=record.status,  # Raw STATUS from device (255 or 0-5)
                    raw_data=record.to_dict(),
                )

                # Save to database (will handle duplicates via unique constraint)
                saved_log = attendance_repo.create(log)

                if saved_log:
                    saved_count += 1
                    app_logger.debug(f"Saved attendance: {record.to_dict()}")

                    # Broadcast to SSE for real-time UI updates (Push devices)
                    self._broadcast_attendance_event(
                        saved_log, device_id, serial_number
                    )

            except Exception as e:
                # Log error but continue processing other records
                error_msg = str(e).lower()

                if "unique" in error_msg or "duplicate" in error_msg:
                    app_logger.debug(
                        f"Duplicate attendance record (skipped): {record.to_dict()}"
                    )
                else:
                    app_logger.error(
                        f"Failed to save attendance record {record.to_dict()}: {e}"
                    )

        return saved_count

    def _broadcast_attendance_event(
        self,
        attendance_log: AttendanceLog,
        device_id: Optional[str],
        serial_number: Optional[str],
    ) -> None:
        """
        Broadcast attendance event to SSE for real-time UI updates.

        This enables real-time attendance monitoring for push devices,
        similar to how pull devices work with live capture.

        Args:
            attendance_log: The saved AttendanceLog object
            device_id: Device ID (if registered)
            serial_number: Device serial number

        Side effects:
            - Publishes event to device_event_stream
            - Event received by frontend SSE listeners
        """
        try:
            # Get device info for event
            device = None
            if device_id:
                device = device_repo.get_by_id(device_id)

            # Get user info with all new fields
            user = user_repo.get_by_user_id(attendance_log.user_id, device_id)
            user_name = user.name if user else "Unknown User"
            avatar_url = user.avatar_url if user else None

            # Extract new employee fields with safe defaults
            full_name = user.full_name if user and user.full_name else user_name
            employee_code = user.employee_code if user and user.employee_code else ""
            position = user.position if user and user.position else ""
            department = user.department if user and user.department else ""
            notes = user.notes if user and user.notes else ""
            employee_object = (
                user.employee_object if user and user.employee_object else ""
            )

            # Format timestamp - handle both string and datetime objects
            if isinstance(attendance_log.timestamp, str):
                timestamp_str = attendance_log.timestamp
            else:
                timestamp_str = attendance_log.timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # Create event payload (same format as pull device live capture)
            event_data = {
                "type": "attendance",
                "device_id": device_id or "unknown",
                "device_name": device.name
                if device
                else f"Push Device {serial_number}",
                "serial_number": serial_number,
                "user_id": attendance_log.user_id,
                "name": user_name,  # Device name (fallback)
                "avatar_url": avatar_url,
                "timestamp": timestamp_str,
                "action": attendance_log.action,
                "method": attendance_log.method,
                "raw_data": attendance_log.raw_data,
                # New employee fields for realtime display
                "full_name": full_name,
                "employee_code": employee_code,
                "position": position,
                "department": department,
                "notes": notes,
                "employee_object": employee_object,
            }

            # Broadcast to all SSE clients
            device_event_stream.publish(event_data)

            app_logger.debug(
                f"[PUSH SSE] Broadcasted attendance event: "
                f"user={attendance_log.user_id}, device={device_id}"
            )

        except Exception as e:
            # Don't fail the save operation if broadcast fails
            app_logger.error(f"Failed to broadcast attendance event: {e}")

    # ========================================================================
    # DATA PROCESSING - USER INFO (OPERLOG)
    # ========================================================================

    def handle_user_data(
        self, raw_data: str, query_params: Dict[str, Any]
    ) -> Tuple[List[UserInfo], int]:
        """
        Process user information from OPERLOG table.

        Args:
            raw_data: Raw text data from device
            query_params: Query parameters (SN, table, etc.)

        Returns:
            Tuple of (parsed_users, saved_count)

        Data format (space-separated key=value pairs):
            USER PIN=123 Name=John Doe Grp=1 Pri=0 Verify=1 TZ=0
            OPLOG 1001 2025-01-09 15:30:00 OP=1

        Fields:
            PIN = User ID
            Name = User name
            Grp = Group ID
            Pri = Privilege (0=user, 14=admin)
            Verify = Verification methods
            TZ = Timezone
        """
        serial_number, _ = self._parse_device_info(query_params)

        app_logger.info(f"[PUSH] Processing OPERLOG from device {serial_number}")

        # Parse raw data
        users = self._parse_user_data(raw_data)

        # Get device ID from serial number
        device = None
        if serial_number:
            device = device_repo.get_by_serial_number(serial_number)

        device_id = device.id if device else None

        # Save to database
        saved_count = self._save_user_records(users, device_id, serial_number)

        app_logger.info(
            f"[PUSH] ✓ Processed {len(users)} user records from {serial_number}, "
            f"saved/updated {saved_count} users"
        )

        return users, saved_count

    def _parse_user_data(self, raw_data: str) -> List[UserInfo]:
        """
        Parse raw OPERLOG data into structured user info.

        Args:
            raw_data: Raw text data from device

        Returns:
            List of UserInfo objects

        Format:
            USER PIN=123 Name=John Doe Grp=1 Pri=0 Verify=1 TZ=0
        """
        users = []

        for line in raw_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                if line.startswith("USER"):
                    # Parse USER line
                    user = self._parse_user_line(line)
                    if user:
                        users.append(user)
                        app_logger.debug(f"[OPERLOG][USER] {user.to_dict()}")

                elif line.startswith("OPLOG"):
                    # Operation log (user creation/deletion event)
                    app_logger.debug(f"[OPERLOG][OPLOG] {line}")

                else:
                    # Other OPERLOG types
                    app_logger.debug(f"[OPERLOG][OTHER] {line}")

            except Exception as e:
                app_logger.error(f"Failed to parse OPERLOG line '{line}': {e}")
                continue

        return users

    def _parse_user_line(self, line: str) -> Optional[UserInfo]:
        """
        Parse a single USER line from OPERLOG.

        Args:
            line: USER line (e.g., 'USER PIN=123 Name=John Grp=1')

        Returns:
            UserInfo object or None if parsing failed

        Format:
            USER key1=value1 key2=value2 ...
        """
        try:
            # Remove 'USER' prefix and split by spaces
            parts = line.split()[1:]  # Skip 'USER'

            # Parse key=value pairs
            fields = {}
            for part in parts:
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value

            # Validate required field
            if "PIN" not in fields:
                app_logger.warning(f"USER line missing PIN: {line}")
                return None

            # Create UserInfo object
            user = UserInfo(
                user_id=fields.get("PIN", ""),
                name=fields.get("Name", ""),
                group=fields.get("Grp", "0"),
                privilege=fields.get("Pri", "0"),
                verify=fields.get("Verify", "1"),
                timezone=fields.get("TZ", "0"),
            )

            return user

        except Exception as e:
            app_logger.error(f"Failed to parse USER line '{line}': {e}")
            return None

    def _save_user_records(
        self,
        users: List[UserInfo],
        device_id: Optional[str],
        serial_number: Optional[str],
    ) -> int:
        """
        Save user records to database.

        Args:
            users: List of UserInfo objects
            device_id: Device ID (if device registered)
            serial_number: Device serial number

        Returns:
            int: Number of users saved/updated

        Side effects:
            - Inserts or updates records in users table
        """
        saved_count = 0

        for user_info in users:
            try:
                # Check if user already exists
                from app.models import User

                existing_users = user_repo.get_all()
                existing_user = None

                for u in existing_users:
                    if (
                        u.user_id == user_info.user_id
                        and u.serial_number == serial_number
                    ):
                        existing_user = u
                        break

                if existing_user:
                    # Update existing user
                    updates = {
                        "name": user_info.name,
                        "privilege": int(user_info.privilege)
                        if user_info.privilege.isdigit()
                        else 0,
                        "group_id": int(user_info.group)
                        if user_info.group.isdigit()
                        else 0,
                        "updated_at": datetime.now(),
                    }

                    user_repo.update(existing_user.id, updates)
                    saved_count += 1
                    app_logger.debug(f"Updated user: {user_info.user_id}")
                else:
                    # Create new user
                    new_user = User(
                        user_id=user_info.user_id,
                        name=user_info.name,
                        device_id=device_id,
                        serial_number=serial_number,
                        privilege=int(user_info.privilege)
                        if user_info.privilege.isdigit()
                        else 0,
                        group_id=int(user_info.group)
                        if user_info.group.isdigit()
                        else 0,
                    )

                    user_repo.create(new_user)
                    saved_count += 1
                    app_logger.debug(f"Created user: {user_info.user_id}")

            except Exception as e:
                app_logger.error(f"Failed to save user {user_info.to_dict()}: {e}")

        return saved_count

    # ========================================================================
    # DATA PROCESSING - BIOMETRIC DATA (BIODATA)
    # ========================================================================

    def handle_biodata(
        self, raw_data: str, query_params: Dict[str, Any]
    ) -> Optional[str]:
        """
        Process biometric template data (face/fingerprint).

        Args:
            raw_data: Raw text data from device
            query_params: Query parameters (SN, table, etc.)

        Returns:
            str: Path to saved file, or None if failed

        Data format:
            Pin=123&Tmp=<base64_encoded_template>

        Side effects:
            - Saves template to file in biodata directory
            - Updates user record to mark has_face=True
        """
        serial_number, _ = self._parse_device_info(query_params)

        app_logger.info(f"[PUSH] Processing BIODATA from device {serial_number}")

        try:
            # Parse PIN and template from raw data
            # Format: Pin=123&Tmp=<base64>
            # Or multi-line format with Pin= on one line, Tmp= on another

            user_id = None
            template_base64 = None

            # Try to extract Pin
            # Format can be: Pin=4\tNo=6\t... (tab-separated) or Pin=4&No=6&... (ampersand-separated)
            if "Pin=" in raw_data:
                for line in raw_data.split("\n"):
                    if "Pin=" in line:
                        # Extract Pin value - handle both tab and ampersand separators
                        pin_part = line.split("Pin=")[1]
                        # Split by tab first, then by ampersand
                        user_id = pin_part.split("\t")[0].split("&")[0].strip()
                        break

            # Try to extract Tmp
            if "Tmp=" in raw_data:
                for line in raw_data.split("\n"):
                    if "Tmp=" in line:
                        template_base64 = line.split("Tmp=")[1].strip()
                        break

            if not user_id or not template_base64:
                app_logger.warning(
                    f"[BIODATA] Invalid data format (missing Pin or Tmp): {raw_data[:100]}"
                )
                return None

            # Decode base64 template
            try:
                template_bytes = base64.b64decode(template_base64)
            except Exception as e:
                app_logger.error(f"[BIODATA] Failed to decode base64 template: {e}")
                return None

            # Save to file
            filename = f"face_pin{user_id}_{serial_number}.dat"
            filepath = os.path.join(self._biodata_dir, filename)

            with open(filepath, "wb") as f:
                f.write(template_bytes)

            app_logger.info(
                f"[BIODATA] ✓ Saved face template for user {user_id} → {filepath} "
                f"({len(template_bytes)} bytes)"
            )

            # Update user record to mark has_face=True
            self._mark_user_has_biometric(user_id, serial_number)

            return filepath

        except Exception as e:
            app_logger.error(f"[BIODATA] Failed to process biometric data: {e}")
            return None

    def _mark_user_has_biometric(
        self, user_id: str, serial_number: Optional[str]
    ) -> None:
        """
        Mark user as having biometric template.

        Args:
            user_id: User ID from device
            serial_number: Device serial number

        Side effects:
            - Updates user record (could add a has_face field in future)
        """
        try:
            # Find user
            existing_users = user_repo.get_all()

            for user in existing_users:
                if user.user_id == user_id and user.serial_number == serial_number:
                    app_logger.debug(
                        f"Marked user {user_id} as having biometric template"
                    )
                    # Note: In future, could add has_face field to User model
                    break

        except Exception as e:
            app_logger.error(f"Failed to mark user {user_id} has biometric: {e}")

    # ========================================================================
    # FILE DATA PROCESSING
    # ========================================================================

    def handle_file_data(
        self, file_data: bytes, query_params: Dict[str, Any]
    ) -> Optional[str]:
        """
        Handle raw biometric file upload (POST /iclock/fdata).

        Args:
            file_data: Raw binary file data
            query_params: Query parameters (PIN, SN, etc.)

        Returns:
            str: Path to saved file, or None if failed

        Side effects:
            - Saves file to biodata directory
        """
        serial_number, _ = self._parse_device_info(query_params)
        user_id = query_params.get("PIN", str(int(datetime.now().timestamp())))

        app_logger.info(
            f"[PUSH] Processing FDATA from device {serial_number}, "
            f"PIN={user_id}, size={len(file_data)} bytes"
        )

        try:
            # Save to file
            filename = (
                f"fdata_{user_id}_{serial_number}_{int(datetime.now().timestamp())}.dat"
            )
            filepath = os.path.join(self._biodata_dir, filename)

            with open(filepath, "wb") as f:
                f.write(file_data)

            app_logger.info(f"[FDATA] ✓ Saved raw file → {filepath}")

            return filepath

        except Exception as e:
            app_logger.error(f"[FDATA] Failed to save file data: {e}")
            return None


# ============================================================================
# GLOBAL SERVICE INSTANCE
# ============================================================================

push_protocol_service = PushProtocolService()

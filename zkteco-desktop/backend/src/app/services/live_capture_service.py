import threading
import time
import os
import random
from datetime import datetime
from zk import ZK
from app.models import AttendanceLog, DoorAccessLog
from app.repositories import (
    attendance_repo,
    device_repo,
    user_repo,
    door_repo,
    door_access_repo,
)
from app.shared.logger import app_logger
from app.events import device_event_stream
from struct import unpack
from socket import timeout
import struct

# Multi-device live capture support
from .multi_device_live_capture import (
    multi_device_config,
    device_health_monitor,
    device_safety_manager,
)


class MultiDeviceLiveCaptureManager:
    """Manages live capture threads for multiple devices"""

    def __init__(self):
        self.device_threads = {}  # device_id -> thread
        self.device_locks = {}  # device_id -> lock
        self.stop_flags = {}  # device_id -> stop flag (NEW)
        self.main_lock = threading.Lock()
        self.max_concurrent_devices = multi_device_config.get(
            "max_concurrent_devices", 10
        )

    def start_device_capture(self, device_id: str):
        """Start live capture for a specific device with safety checks"""
        with self.main_lock:
            # Check if already running (ENHANCED logging)
            if device_id in self.device_threads:
                thread = self.device_threads[device_id]
                if thread.is_alive():
                    app_logger.warning(
                        f"Live capture already running for device {device_id} (thread: {thread.name}, alive: {thread.is_alive()})"
                    )
                    return
                else:
                    app_logger.info(f"Cleaning up dead thread for device {device_id}")
                    del self.device_threads[device_id]

            # Safety validation
            active_count = len(
                [t for t in self.device_threads.values() if t.is_alive()]
            )
            can_start, reason = device_safety_manager.validate_device_start(
                device_id, active_count
            )

            if not can_start:
                app_logger.error(f"Cannot start device {device_id}: {reason}")
                return

            # Create device-specific lock if needed
            if device_id not in self.device_locks:
                self.device_locks[device_id] = threading.Lock()

            # Initialize stop flag to False (NEW)
            self.stop_flags[device_id] = False

            app_logger.info(f"Starting live capture thread for device {device_id}")

            try:
                thread = threading.Thread(
                    target=self._device_capture_wrapper,
                    args=(device_id,),
                    daemon=True,
                    name=f"LiveCapture-{device_id}",
                )
                self.device_threads[device_id] = thread
                thread.start()

                # Record successful start
                device_health_monitor.record_connection(device_id)
                app_logger.info(
                    f"Live capture thread started successfully for device {device_id}"
                )

            except Exception as e:
                app_logger.error(
                    f"Failed to start live capture thread for device {device_id}: {e}"
                )
                device_health_monitor.record_error(device_id, str(e))
                # Clean up on failure
                if device_id in self.device_threads:
                    del self.device_threads[device_id]
                if device_id in self.stop_flags:
                    del self.stop_flags[device_id]

    def _device_capture_wrapper(self, device_id: str):
        """Wrapper for device capture with error isolation and monitoring"""
        try:
            live_capture_worker(device_id)
        except Exception as e:
            app_logger.error(f"Live capture worker error for device {device_id}: {e}")
            device_health_monitor.record_error(device_id, str(e))
        finally:
            device_health_monitor.record_disconnection(device_id)
            app_logger.info(f"Live capture worker finished for device {device_id}")

    def stop_device_capture(self, device_id: str, wait_timeout: float = 3.0):
        """Stop live capture for a specific device

        Args:
            device_id: Device ID to stop
            wait_timeout: Max seconds to wait for thread to stop (default: 3.0)
                         Should be > socket timeout (1s) to allow graceful stop
        """
        thread_to_wait = None

        with self.main_lock:
            if device_id in self.device_threads:
                thread = self.device_threads[device_id]
                if thread.is_alive():
                    app_logger.info(
                        f"Stopping live capture thread for device {device_id}"
                    )
                    # Set stop flag to signal thread to stop (NEW)
                    self.stop_flags[device_id] = True
                    thread_to_wait = thread
                device_health_monitor.record_disconnection(device_id)
                del self.device_threads[device_id]

        # Wait for thread to stop outside of lock (NEW)
        if thread_to_wait and thread_to_wait.is_alive():
            app_logger.info(
                f"Waiting up to {wait_timeout}s for device {device_id} thread to stop..."
            )
            thread_to_wait.join(timeout=wait_timeout)
            if thread_to_wait.is_alive():
                app_logger.warning(
                    f"Device {device_id} thread did not stop within {wait_timeout}s, continuing anyway"
                )
            else:
                app_logger.info(f"Device {device_id} thread stopped successfully")

    def stop_all_captures(self):
        """Stop all live capture threads"""
        # Get device IDs WITHOUT holding lock (FIXED - avoid deadlock)
        with self.main_lock:
            device_ids = list(self.device_threads.keys())

        # Stop devices one by one (each will acquire lock independently)
        for device_id in device_ids:
            self.stop_device_capture(device_id)

    def get_active_devices(self):
        """Get list of devices with active capture threads"""
        with self.main_lock:
            active_devices = []
            for device_id, thread in list(self.device_threads.items()):
                if thread.is_alive():
                    active_devices.append(device_id)
                else:
                    # Clean up dead threads
                    del self.device_threads[device_id]
            return active_devices

    def is_device_active(self, device_id: str):
        """Check if device has active capture thread"""
        with self.main_lock:
            return (
                device_id in self.device_threads
                and self.device_threads[device_id].is_alive()
            )

    def should_stop(self, device_id: str) -> bool:
        """Check if device should stop (NEW - for thread to check)"""
        return self.stop_flags.get(device_id, False)


# Global multi-device manager instance
multi_device_manager = MultiDeviceLiveCaptureManager()

# Legacy support - single thread capture
capture_thread = None
capture_lock = threading.Lock()


def strtobool(val):
    """Helper to convert string to bool."""
    return val.lower() in ("y", "yes", "t", "true", "on", "1")


# ====================
# OLD IMPLEMENTATION - RESTORED WITH ENHANCED PARSING (Date: 2025-09-05)
# ====================
def live_capture_worker(device_id=None):
    """The background worker function that captures attendance with enhanced parsing.

    Args:
        device_id (str, optional): Specific device ID to capture from.
                                 If None, uses active device (legacy mode).
    """

    use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))

    if use_mock:
        # Use mock implementation for testing
        app_logger.info(f"Using mock device for live capture (device_id: {device_id})")
        _mock_live_capture_worker(device_id)
        return

    # Import here to avoid circular imports
    from app.config.config_manager import config_manager
    from app.device.connection_manager import connection_manager

    zk = None
    target_device = None

    # Exponential backoff configuration
    initial_delay = 10  # Start with 10 seconds
    max_delay = 300  # Cap at 5 minutes
    backoff_multiplier = 2  # Double each time
    jitter_range = 0.2  # ±20% random jitter

    current_delay = initial_delay
    error_count = 0
    error_log_threshold = 5  # Log every 5th error

    def calculate_backoff_delay(base_delay, max_delay, jitter_range):
        """Calculate delay with exponential backoff and jitter"""
        # Add random jitter (±jitter_range%)
        jitter = base_delay * jitter_range * (random.random() * 2 - 1)
        delay_with_jitter = base_delay + jitter
        # Ensure within bounds
        return max(initial_delay, min(delay_with_jitter, max_delay))

    while True:
        # Check stop flag first (NEW)
        if device_id and multi_device_manager.should_stop(device_id):
            app_logger.info(
                f"Stop flag detected for device {device_id}, exiting worker"
            )
            break
        try:
            # Get target device info
            if device_id:
                # Multi-device mode - get specific device
                target_device = config_manager.get_device(device_id)
                if not target_device:
                    app_logger.error(f"Device {device_id} not found in database")
                    time.sleep(10)
                    continue

                # Check device type - skip live capture for push devices
                device_type = target_device.get("device_type", "pull")
                if device_type == "push":
                    app_logger.info(
                        f"Device {device_id} is push type, skipping live capture (push devices send data automatically)"
                    )
                    break

                if not target_device.get("is_active", True):
                    app_logger.info(
                        f"Device {device_id} is inactive, stopping live capture"
                    )
                    break

            else:
                # Legacy mode - get active device
                target_device = config_manager.get_active_device()
                if not target_device:
                    app_logger.error(
                        "No active device found in database for live capture"
                    )
                    time.sleep(10)
                    continue
                device_id = target_device.get("id")

                # Check device type for legacy mode too
                device_type = target_device.get("device_type", "pull")
                if device_type == "push":
                    app_logger.info(
                        f"Active device {device_id} is push type, skipping live capture"
                    )
                    break

            ip = target_device.get("ip")
            if not ip:
                app_logger.error(f"Device {device_id} has no IP address configured")
                time.sleep(10)
                continue

            # Use connection manager for device-specific connection
            if device_id:
                # Configure device in connection manager if not already done
                device_config = {
                    "ip": target_device.get("ip"),
                    "port": target_device.get("port", 4370),
                    "password": target_device.get("password", 0),
                    "timeout": target_device.get("timeout", 30),
                    "force_udp": target_device.get("force_udp", False),
                    "verbose": False,
                }
                connection_manager.configure_device(device_id, device_config)
                zk = connection_manager.get_device_connection(device_id)
            else:
                # Legacy mode
                zk = connection_manager.get_connection()

            # Use custom live capture with enhanced parsing
            # Reset backoff on successful connection
            error_count = 0
            current_delay = initial_delay
            _enhanced_live_capture(zk, device_id)

        except (OSError, BrokenPipeError, ConnectionError) as e:
            # Check if stopped intentionally
            if device_id and multi_device_manager.should_stop(device_id):
                app_logger.debug(
                    f"Device {device_id} stopped intentionally, not reconnecting"
                )
                break

            # Exponential backoff with jitter
            error_count += 1

            # Log error periodically
            if error_count % error_log_threshold == 0:
                app_logger.error(
                    f"Live capture connection error for device {device_id} ({error_count} consecutive errors, next retry in {current_delay:.1f}s): {e}"
                )

            if zk:
                try:
                    zk.disconnect()
                except:
                    pass

            # Calculate next delay with jitter
            actual_delay = calculate_backoff_delay(
                current_delay, max_delay, jitter_range
            )
            time.sleep(actual_delay)

            # Increase delay for next time (exponential backoff)
            current_delay = min(current_delay * backoff_multiplier, max_delay)

        except Exception as e:
            # Check if stopped intentionally
            if device_id and multi_device_manager.should_stop(device_id):
                app_logger.debug(
                    f"Device {device_id} stopped intentionally, not reconnecting"
                )
                break

            # Exponential backoff with jitter
            error_count += 1

            # Log error periodically
            if error_count % error_log_threshold == 0:
                app_logger.error(
                    f"Live capture error for device {device_id} ({error_count} consecutive errors, next retry in {current_delay:.1f}s): {e}"
                )

            if zk:
                try:
                    zk.disconnect()
                except:
                    pass

            # Calculate next delay with jitter
            actual_delay = calculate_backoff_delay(
                current_delay, max_delay, jitter_range
            )
            time.sleep(actual_delay)

            # Increase delay for next time (exponential backoff)
            current_delay = min(current_delay * backoff_multiplier, max_delay)
        else:
            # Check if stopped intentionally
            if device_id and multi_device_manager.should_stop(device_id):
                app_logger.debug(
                    f"Device {device_id} stopped intentionally, exiting worker"
                )
                break
            app_logger.debug(
                f"Live capture loop exited for device {device_id}. Reconnecting in 10s."
            )
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            time.sleep(10)

    # Final cleanup when worker exits (NEW)
    if device_id and device_id in multi_device_manager.stop_flags:
        del multi_device_manager.stop_flags[device_id]
        app_logger.info(f"Cleaned up stop flag for device {device_id}")


def _mock_live_capture_worker(device_id=None):
    """Mock implementation for testing

    Args:
        device_id (str, optional): Specific device ID for mock capture.
                                 If None, uses environment variables.
    """
    from app.device.mock import ZKMock
    from app.config.config_manager import config_manager

    zk = None
    target_device = None

    while True:
        try:
            if device_id:
                # Multi-device mock mode
                target_device = config_manager.get_device(device_id)
                if not target_device:
                    app_logger.error(f"Mock device {device_id} not found in database")
                    time.sleep(10)
                    continue

                ip = target_device.get("ip")
                port = int(target_device.get("port", 4370))
                password = int(target_device.get("password", 0))

                app_logger.info(
                    f"Mock live capture: Connecting to device {device_id}..."
                )
            else:
                # Legacy mock mode
                ip = os.environ.get("DEVICE_IP")
                port = int(os.environ.get("DEVICE_PORT", 4370))
                password = int(os.environ.get("PASSWORD", 0))

                app_logger.info("Mock live capture: Connecting to device...")

            zk = ZKMock(ip, port=port, password=password, timeout=30, verbose=False)
            zk.connect()
            app_logger.info(
                f"Mock live capture: Connected successfully (device_id: {device_id})"
            )

            for attendance in zk.live_capture():
                if attendance is None:
                    continue

                app_logger.info(
                    f"Mock live capture: Received attendance event for user {attendance} (device_id: {device_id})"
                )

                # Use updated function that gets device info from database
                _queue_attendance_event(
                    attendance.user_id, attendance.status, attendance.punch, device_id
                )

        except Exception as e:
            app_logger.error(f"Mock live capture error (device_id: {device_id}): {e}")
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            time.sleep(10)


# ====================
# ENHANCED LIVE CAPTURE WITH CUSTOM PARSING - Integrated from NEW IMPLEMENTATION (Date: 2025-09-05)
# ====================


def _enhanced_live_capture(zk, device_id=None):
    """Enhanced live capture with custom socket parsing and proper error handling

    Args:
        zk: ZK device connection instance
        device_id (str, optional): Device ID for logging and event processing
    """
    app_logger.info(
        f"Starting enhanced live capture with custom socket parsing (device_id: {device_id})"
    )

    try:
        # Wrap all device commands in try-except to handle broken pipe (FIXED)
        try:
            zk.cancel_capture()
        except Exception as e:
            app_logger.debug(f"cancel_capture error (safe to ignore): {e}")

        try:
            zk.verify_user()
        except Exception as e:
            app_logger.debug(f"verify_user error (safe to ignore): {e}")

        try:
            zk.enable_device()
        except Exception as e:
            app_logger.warning(f"enable_device error: {e}")
            raise  # This is critical, re-raise

        try:
            zk.reg_event(1)
        except Exception as e:
            app_logger.warning(f"reg_event error: {e}")
            raise  # This is critical, re-raise

        zk._ZK__sock.settimeout(
            1
        )  # 1 second timeout for responsive stop (FIXED from 10s)
        zk.end_live_capture = False

        while not zk.end_live_capture:
            # Check stop flag (NEW)
            if device_id and multi_device_manager.should_stop(device_id):
                app_logger.info(
                    f"Stop flag detected in live capture for device {device_id}, exiting"
                )
                break
            try:
                # Check socket state before attempting to read
                if not zk.is_connect:
                    app_logger.warning("Device connection lost during live capture")
                    break

                data_recv = zk._ZK__sock.recv(1032)

                # Log raw data received from device
                app_logger.info(
                    f"Raw data received: {data_recv.hex()} (length: {len(data_recv)})"
                )

                zk._ZK__ack_ok()

                if zk.tcp:
                    size = unpack("<HHI", data_recv[:8])[2]
                    header = unpack("HHHH", data_recv[8:16])
                    data = data_recv[16:]
                else:
                    size = len(data_recv)
                    header = unpack("<4H", data_recv[:8])
                    data = data_recv[8:]

                if not header[0] == 500:
                    continue
                if not len(data):
                    continue

                while len(data) >= 10:
                    user_id, _status, _punch, _timehex, data = _parse_attendance_data(
                        data
                    )

                    if isinstance(user_id, int):
                        user_id = str(user_id)
                    else:
                        user_id = (user_id.split(b"\x00")[0]).decode(errors="ignore")

                    # Parse device timestamp from _timehex
                    device_timestamp = _parse_device_timestamp(_timehex)

                    app_logger.info(
                        f"Live capture: Attendance detected for user_id: {user_id}, status: {_status}, punch: {_punch}, device_time: {device_timestamp} (device_id: {device_id})"
                    )

                    # Use updated function that gets device info from database
                    _queue_attendance_event(
                        user_id, _status, _punch, device_id, device_timestamp
                    )

            except timeout:
                app_logger.debug("Socket timeout in live capture - continuing...")
                continue
            except (OSError, BrokenPipeError, ConnectionError) as e:
                app_logger.error(f"Socket connection error in live capture: {e}")
                raise  # Re-raise to trigger reconnection
            except BlockingIOError:
                continue
            except (KeyboardInterrupt, SystemExit):
                app_logger.info("Live capture interrupted by user")
                break

    except Exception as e:
        app_logger.error(f"Live capture error: {e}")
        raise
    finally:
        try:
            # Reset socket timeout (FIXED - wrapped)
            try:
                if hasattr(zk, "_ZK__sock") and zk._ZK__sock:
                    zk._ZK__sock.settimeout(None)
            except Exception as e:
                app_logger.debug(f"Error resetting socket timeout: {e}")

            # Unregister event (FIXED - wrapped)
            try:
                zk.reg_event(0)
            except Exception as e:
                app_logger.debug(f"Error unregistering event: {e}")

            # Gracefully disconnect device (FIXED - already wrapped)
            try:
                zk.disconnect()
                app_logger.info(f"Device {device_id} disconnected gracefully")
            except Exception as disc_error:
                app_logger.debug(
                    f"Error disconnecting device {device_id}: {disc_error}"
                )

            app_logger.info("Live capture cleanup completed")
        except Exception as e:
            app_logger.error(f"Error cleaning up live capture: {e}")


def _parse_attendance_data(data):
    """Parse attendance data from different packet formats"""
    if len(data) == 10:
        user_id, _status, _punch, _timehex = unpack("<HBB6s", data)
        remaining_data = data[10:]
    elif len(data) == 12:
        user_id, _status, _punch, _timehex = unpack("<IBB6s", data)
        remaining_data = data[12:]
    elif len(data) == 14:
        user_id, _status, _punch, _timehex, _other = unpack("<HBB6s4s", data)
        remaining_data = data[14:]
    elif len(data) == 32:
        user_id, _status, _punch, _timehex = unpack("<24sBB6s", data[:32])
        remaining_data = data[32:]
    elif len(data) == 36:
        user_id, _status, _punch, _timehex, _other = unpack("<24sBB6s4s", data[:36])
        remaining_data = data[36:]
    elif len(data) == 37:
        user_id, _status, _punch, _timehex, _other = unpack("<24sBB6s5s", data[:37])
        remaining_data = data[37:]
    elif len(data) >= 52:
        user_id, _status, _punch, _timehex, _other = unpack("<24sBB6s20s", data[:52])
        remaining_data = data[52:]
    else:
        # Fallback for unknown formats
        user_id, _status, _punch, _timehex = 0, 0, 0, b"\x00\x00\x00\x00\x00\x00"
        remaining_data = b""

    return user_id, _status, _punch, _timehex, remaining_data


def _parse_device_timestamp(timehex_bytes):
    """
    Parse device timestamp from 6-byte timehex format
    ZK Device format: 6 bytes representing YY MM DD HH MM SS in BCD or binary
    """
    try:
        if len(timehex_bytes) != 6:
            app_logger.warning(
                f"Invalid timehex length: {len(timehex_bytes)}, expected 6 bytes"
            )
            return None

        # Try to unpack as little-endian integers
        # Some devices use different formats, so we try multiple approaches
        try:
            # Method 1: Unpack as 6 individual bytes (most common)
            year, month, day, hour, minute, second = struct.unpack("<6B", timehex_bytes)

            # Convert 2-digit year to 4-digit (assume 2000-2099 range)
            if year < 50:  # 0-49 -> 2000-2049
                year += 2000
            elif year < 100:  # 50-99 -> 2050-2099
                year += 2000
            else:  # already 4-digit or invalid
                year = year if year > 1900 else year + 2000

        except struct.error:
            # Method 2: Try different unpacking format
            app_logger.debug("Trying alternative timestamp format...")
            timestamp_int = struct.unpack("<I", timehex_bytes[:4])[0]

            # Extract date/time components from packed integer
            year = (timestamp_int & 0x3F) + 2000  # 6 bits for year
            month = (timestamp_int >> 6) & 0x0F  # 4 bits for month
            day = (timestamp_int >> 10) & 0x1F  # 5 bits for day
            hour = (timestamp_int >> 15) & 0x1F  # 5 bits for hour
            minute = (timestamp_int >> 20) & 0x3F  # 6 bits for minute
            second = (timestamp_int >> 26) & 0x3F  # 6 bits for second

        # Validate date/time components
        if not (1 <= month <= 12):
            app_logger.warning(f"Invalid month: {month}")
            return None
        if not (1 <= day <= 31):
            app_logger.warning(f"Invalid day: {day}")
            return None
        if not (0 <= hour <= 23):
            app_logger.warning(f"Invalid hour: {hour}")
            return None
        if not (0 <= minute <= 59):
            app_logger.warning(f"Invalid minute: {minute}")
            return None
        if not (0 <= second <= 59):
            app_logger.warning(f"Invalid second: {second}")
            return None

        # Create datetime object
        device_time = datetime(year, month, day, hour, minute, second)

        # Log for debugging
        app_logger.debug(
            f"Parsed device timestamp: {device_time} from bytes: {timehex_bytes.hex()}"
        )

        return device_time

    except Exception as e:
        app_logger.error(
            f"Error parsing device timestamp from {timehex_bytes.hex()}: {e}"
        )
        return None


def _get_active_device_info():
    """Get active device info from database"""
    try:
        # Get active device from database
        devices = device_repo.get_all()
        active_device = None
        for device in devices:
            if hasattr(device, "is_active") and device.is_active:
                active_device = device
                break

        if active_device:
            return active_device.id, getattr(active_device, "serial_number", None)

        # Fallback: use environment variables
        device_id = os.environ.get("DEVICE_ID", os.environ.get("DEVICE_IP", "unknown"))
        serial_number = os.environ.get("DEVICE_SERIAL", None)
        app_logger.warning(
            f"No active device found in database, using fallback: device_id={device_id}, serial={serial_number}"
        )
        return device_id, serial_number

    except Exception as e:
        app_logger.error(f"Error getting active device info: {e}")
        # Emergency fallback
        device_id = os.environ.get("DEVICE_ID", os.environ.get("DEVICE_IP", "unknown"))
        return device_id, None


def _ensure_user_exists_for_pull(
    user_id: str, device_id: str, serial_number: str
) -> None:
    """
    Ensure user exists in database for pull device. If not, create with default values.

    This prevents attendance records from being orphaned when device sends
    attendance data before user sync.

    Args:
        user_id: User ID from device
        device_id: Device ID
        serial_number: Device serial number

    Side effects:
        - Creates user in database if not exists
    """
    try:
        # Check if user exists for this device
        user = user_repo.get_by_user_id(user_id, device_id)

        if user:
            # User already exists
            return

        # User doesn't exist - auto-create with default values
        from app.models import User

        app_logger.info(
            f"[PULL AUTO-CREATE] User {user_id} not found, creating with default values "
            f"(device={device_id}, serial={serial_number})"
        )

        # ============================================================
        # COMMENTED OUT: Profile copy logic - can be re-enabled if needed
        # ============================================================
        # Try to find source user from other devices with same user_id
        # source_user = user_repo.find_first_by_user_id(
        #     user_id, exclude_device_id=device_id if device_id else None
        # )

        # Prepare profile data
        # profile_payload = {}
        # synced_at_copy = None

        # if source_user:
        #     # Copy profile from existing user on another device
        #     # Use same fields as push protocol
        #     PROFILE_COPY_FIELDS = (
        #         "full_name",
        #         "employee_code",
        #         "position",
        #         "department",
        #         "employee_object",
        #     )
        #     OPTIONAL_PROFILE_COPY_FIELDS = (
        #         "avatar_url",
        #         "external_user_id",
        #         "synced_at",
        #     )

        #     fields = PROFILE_COPY_FIELDS + OPTIONAL_PROFILE_COPY_FIELDS
        #     for field in fields:
        #         value = getattr(source_user, field, None)
        #         if value not in (None, ""):
        #             profile_payload[field] = value

        #     synced_at_copy = profile_payload.pop(
        #         "synced_at", getattr(source_user, "synced_at", None)
        #     )

        #     app_logger.debug(
        #         f"[PULL AUTO-CREATE] Copying profile from source user: {source_user.id}"
        #     )
        # else:
        #     # No source user - derive external_user_id from user_id
        #     try:
        #         fallback_external_id = int(str(user_id).strip())
        #         profile_payload["external_user_id"] = fallback_external_id
        #     except (TypeError, ValueError):
        #         pass
        # ============================================================

        # Simplified: No profile copy, external_user_id will be set by cron
        source_user = None
        profile_payload = {}
        synced_at_copy = None

        # Create new user
        new_user = User(
            user_id=user_id,
            name=f"User {user_id}",  # Default name
            device_id=device_id,
            serial_number=serial_number,
            privilege=0,  # Default to regular user
            group_id=0,  # Default group
            is_synced=True if source_user else False,
            synced_at=synced_at_copy,
            **profile_payload,
        )

        created_user = user_repo.create(new_user)

        if created_user:
            app_logger.info(
                f"[PULL AUTO-CREATE] OK Created user {user_id} "
                f"(name='{new_user.name}', device={device_id})"
            )
        else:
            app_logger.warning(f"[PULL AUTO-CREATE] Failed to create user {user_id}")

    except Exception as e:
        # Don't fail attendance save if user creation fails
        app_logger.error(
            f"[PULL AUTO-CREATE] Error ensuring user {user_id} exists: {e}"
        )


def _queue_attendance_event(
    member_id, method, action, device_id=None, device_timestamp=None
):
    """
    Queue attendance event and save to the appropriate log (door or attendance).
    If the device is linked to a door, save to door_access_logs.
    Otherwise, save to attendance_logs.
    """
    try:
        current_time = datetime.now()
        serial_number = None

        # Get device info
        if device_id:
            from app.config.config_manager import config_manager

            device = config_manager.get_device(device_id)
            if device:
                serial_number = device.get("serial_number")
        else:
            device_id, serial_number = _get_active_device_info()

        # Ensure user exists to get user info
        _ensure_user_exists_for_pull(str(member_id), device_id, serial_number)
        user = user_repo.get_by_user_id(str(member_id), device_id)
        user_name = user.name if user else "Unknown User"
        db_user_id = user.id if user else None

        actual_timestamp = device_timestamp if device_timestamp else current_time

        # Check if device is associated with a door
        doors = door_repo.get_by_device_id(device_id)
        if doors:
            door = doors[0]
            app_logger.info(
                f"Device {device_id} is linked to door {door.id}. Logging to DoorAccessLog."
            )

            door_log = DoorAccessLog(
                door_id=door.id,
                user_id=db_user_id,
                user_name=user_name,
                action="access_granted",  # Map attendance event to a door action
                status="success",
                timestamp=actual_timestamp,
                notes=f"Event from ZK device. Method: {method}, Punch Action: {action}",
            )
            door_access_repo.create(door_log)
            app_logger.info(
                f"Live capture: Saved new door access log for door {door.id}"
            )

            # For realtime stream, we can create a similar payload
            event_data = {
                "id": door_log.id,
                "user_id": str(member_id),
                "name": user_name,
                "timestamp": actual_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "action": "access_granted",
                "status": "success",
                "type": "door_log",  # Add type to distinguish on frontend
                "door_id": door.id,
                "door_name": door.name,
                "device_id": device_id,
            }
            device_event_stream.publish(event_data)
            app_logger.info(
                f"Live capture: Published realtime door event for user {member_id}"
            )

        else:
            # Original logic: save to attendance_logs
            app_logger.info(
                f"Device {device_id} is not linked to a door. Logging to AttendanceLog."
            )
            attendance_log = AttendanceLog(
                user_id=str(member_id),
                timestamp=actual_timestamp,
                method=method,
                action=action,
                device_id=device_id,
                serial_number=serial_number,
                original_status=action,
                raw_data={
                    "original_status": method,
                    "original_punch": action,
                    "device_timestamp": device_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    if device_timestamp
                    else None,
                    "server_timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp_source": "device" if device_timestamp else "server",
                    "device_info": {
                        "device_id": device_id,
                        "serial_number": serial_number,
                    },
                },
                is_synced=False,
            )
            saved_log, is_new = attendance_repo.create_safe(attendance_log)
            if is_new:
                app_logger.info(
                    f"Live capture: Saved new attendance log to database with ID {saved_log.id}"
                )
            else:
                app_logger.info(
                    f"Live capture: Found existing attendance log with ID {saved_log.id}, skipped duplicate"
                )

            # Get user info with all new fields for event stream
            user = user_repo.get_by_user_id(str(member_id), device_id)
            avatar_url = user.avatar_url if user else None
            full_name = user.full_name if user and user.full_name else user_name
            employee_code = user.employee_code if user and user.employee_code else ""
            position = user.position if user and user.position else ""
            department = user.department if user and user.department else ""
            notes = user.notes if user and user.notes else ""
            gender = user.gender if user and user.gender else ""
            hire_date = user.hire_date if user and user.hire_date else ""

            # Queue for realtime streaming (with new fields)
            event_data = {
                "id": saved_log.id,
                "user_id": str(member_id),
                "name": user_name,
                "avatar_url": avatar_url,
                "timestamp": actual_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "method": method,
                "action": action,
                "type": "attendance_log",  # Add type
                "device_id": device_id,
                "is_synced": False,
                "full_name": full_name,
                "employee_code": employee_code,
                "position": position,
                "department": department,
                "notes": notes,
                "gender": gender,
                "hire_date": hire_date,
            }
            device_event_stream.publish(event_data)
            app_logger.info(
                f"Live capture: Published realtime attendance event for user {member_id}"
            )

    except Exception as e:
        app_logger.error(f"Error processing attendance event: {e}", exc_info=True)
        # Even if database save fails, try to queue for realtime
        try:
            fallback_event = {
                "user_id": str(member_id),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "method": method,
                "action": action,
                "device_id": device_id,
                "error": "Database save failed",
            }
            device_event_stream.publish(fallback_event)
        except Exception as queue_error:
            app_logger.error(f"Error queuing fallback event: {queue_error}")


# ====================
# MULTI-DEVICE FUNCTIONS
# ====================


def start_multi_device_capture():
    """Start live capture for all active pull devices in the database."""
    from app.config.config_manager import config_manager

    try:
        # Get all active devices
        active_devices = config_manager.get_devices_by_status(is_active=True)

        if not active_devices:
            app_logger.warning("No active devices found for multi-device live capture")
            return

        # Filter out push devices (they don't need live capture)
        pull_devices = [
            d for d in active_devices if d.get("device_type", "pull") == "pull"
        ]
        push_devices_count = len(active_devices) - len(pull_devices)

        if push_devices_count > 0:
            app_logger.info(
                f"Skipping {push_devices_count} push device(s) - they send data automatically"
            )

        if not pull_devices:
            app_logger.info("No pull devices found for live capture")
            return

        app_logger.info(
            f"Starting multi-device live capture for {len(pull_devices)} pull device(s)"
        )

        for device in pull_devices:
            device_id = device.get("id")
            device_name = device.get("name", "Unknown")

            try:
                multi_device_manager.start_device_capture(device_id)
                app_logger.info(
                    f"Started live capture for device: {device_name} (ID: {device_id})"
                )
            except Exception as e:
                app_logger.error(
                    f"Failed to start live capture for device {device_name} (ID: {device_id}): {e}"
                )

        # Log current status
        active_captures = multi_device_manager.get_active_devices()
        app_logger.info(
            f"Multi-device live capture started. Active captures: {len(active_captures)} devices"
        )

    except Exception as e:
        app_logger.error(f"Error starting multi-device live capture: {e}")


def stop_multi_device_capture():
    """Stop live capture for all devices."""
    try:
        active_devices = multi_device_manager.get_active_devices()
        app_logger.info(
            f"Stopping multi-device live capture for {len(active_devices)} devices"
        )

        multi_device_manager.stop_all_captures()
        app_logger.info("Multi-device live capture stopped")

    except Exception as e:
        app_logger.error(f"Error stopping multi-device live capture: {e}")


def start_device_capture(device_id: str):
    """Start live capture for a specific device.

    Args:
        device_id (str): Device ID to start capture for
    """
    try:
        from app.config.config_manager import config_manager

        # Verify device exists and is active
        device = config_manager.get_device(device_id)
        if not device:
            app_logger.error(f"Device {device_id} not found")
            return False

        if not device.get("is_active", True):
            app_logger.warning(f"Device {device_id} is not active")
            return False

        multi_device_manager.start_device_capture(device_id)
        app_logger.info(f"Started live capture for device {device_id}")
        return True

    except Exception as e:
        app_logger.error(f"Error starting live capture for device {device_id}: {e}")
        return False


def stop_device_capture(device_id: str):
    """Stop live capture for a specific device.

    Args:
        device_id (str): Device ID to stop capture for
    """
    try:
        multi_device_manager.stop_device_capture(device_id)
        app_logger.info(f"Stopped live capture for device {device_id}")
        return True

    except Exception as e:
        app_logger.error(f"Error stopping live capture for device {device_id}: {e}")
        return False


def ensure_pull_devices_capturing() -> dict:
    """Ensure all active pull devices have live capture threads running."""
    summary = {
        "active_checked": 0,
        "pull_devices": 0,
        "already_running": 0,
        "auto_started": 0,
        "errors": [],
    }

    try:
        from app.config.config_manager import config_manager

        active_devices = config_manager.get_devices_by_status(is_active=True)
        summary["active_checked"] = len(active_devices)

        for device in active_devices:
            device_id = device.get("id")
            if not device_id:
                continue

            if device.get("device_type", "pull") != "pull":
                continue

            summary["pull_devices"] += 1

            if multi_device_manager.is_device_active(device_id):
                summary["already_running"] += 1
                continue

            try:
                app_logger.info(
                    f"[LiveCapture] Auto-starting capture for pull device {device_id}"
                )
                multi_device_manager.start_device_capture(device_id)
                summary["auto_started"] += 1
            except Exception as start_error:
                msg = (
                    f"Failed to auto-start live capture for device {device_id}: "
                    f"{start_error}"
                )
                summary["errors"].append(msg)
                app_logger.error(msg)

    except Exception as error:
        msg = f"ensure_pull_devices_capturing encountered an error: {error}"
        summary["errors"].append(msg)
        app_logger.error(msg, exc_info=True)

    return summary


def get_capture_status():
    """Get status of all live capture threads.

    Returns:
        dict: Status information about active captures
    """
    try:
        active_devices = multi_device_manager.get_active_devices()

        status = {
            "active_captures": len(active_devices),
            "devices": active_devices,
            "max_concurrent": multi_device_manager.max_concurrent_devices,
        }

        return status

    except Exception as e:
        app_logger.error(f"Error getting capture status: {e}")
        return {"error": str(e)}


# ====================
# LEGACY FUNCTIONS (for backward compatibility)
# ====================


def start_live_capture_thread():
    """Starts the live capture thread if it's not already running (legacy mode)."""
    global capture_thread
    with capture_lock:
        if capture_thread is None or not capture_thread.is_alive():
            app_logger.info("Starting live capture background thread (legacy mode)")
            capture_thread = threading.Thread(target=live_capture_worker, daemon=True)
            capture_thread.start()

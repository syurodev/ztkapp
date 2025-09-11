import threading
import time
import os
from datetime import datetime
from zk import ZK
from zkteco.events import events_queue
from zkteco.logger import app_logger
from zkteco.zk_mock import ZKMock
from zkteco.database.models import AttendanceLog, attendance_repo, device_repo
from struct import unpack
from socket import timeout
import struct

# To prevent starting multiple threads
capture_thread = None
capture_lock = threading.Lock()

def strtobool(val):
    """Helper to convert string to bool."""
    return val.lower() in ('y', 'yes', 't', 'true', 'on', '1')

# ====================
# OLD IMPLEMENTATION - RESTORED WITH ENHANCED PARSING (Date: 2025-09-05)
# ====================
def live_capture_worker():
    """The background worker function that captures attendance with enhanced parsing."""

    use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))
    
    if use_mock:
        # Use mock implementation for testing
        app_logger.info("Using mock device for live capture")
        _mock_live_capture_worker()
        return
    
    # Main implementation for real devices
    ip = os.environ.get('DEVICE_IP')
    port = int(os.environ.get('DEVICE_PORT', 4370))
    password = int(os.environ.get('PASSWORD', 0))

    zk = None

    while True:
        try:
            app_logger.info("Live capture thread: Connecting to device...")
            zk = ZK(ip, port=port, password=password, timeout=30, verbose=False)
            zk.connect()
            app_logger.info("Live capture thread: Connected successfully.")

            # Use custom live capture with enhanced parsing
            _enhanced_live_capture(zk)

        except (OSError, BrokenPipeError, ConnectionError) as e:
            app_logger.error(f"Live capture socket error: {e}")
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            app_logger.info("Live capture thread: Reconnecting in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            app_logger.error(f"Live capture thread error: {e}")
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            app_logger.info("Live capture thread: Reconnecting in 10 seconds...")
            time.sleep(10)
        else:
            app_logger.warning("Live capture loop exited. Reconnecting in 10 seconds.")
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            time.sleep(10)

def _mock_live_capture_worker():
    """Mock implementation for testing"""
    from zkteco.zk_mock import ZKMock
    
    ip = os.environ.get('DEVICE_IP')
    port = int(os.environ.get('DEVICE_PORT', 4370))
    password = int(os.environ.get('PASSWORD', 0))

    zk = None
    while True:
        try:
            app_logger.info("Mock live capture: Connecting to device...")
            zk = ZKMock(ip, port=port, password=password, timeout=30, verbose=False)
            zk.connect()
            app_logger.info("Mock live capture: Connected successfully.")

            for attendance in zk.live_capture():
                if attendance is None:
                    continue

                app_logger.info(f"Mock live capture: Received attendance event for user {attendance}")

                # Use updated function that gets device info from database  
                _queue_attendance_event(attendance.user_id, attendance.status, attendance.punch, None)

        except Exception as e:
            app_logger.error(f"Mock live capture error: {e}")
            if zk:
                try:
                    zk.disconnect()
                except:
                    pass
            time.sleep(10)

# ====================
# ENHANCED LIVE CAPTURE WITH CUSTOM PARSING - Integrated from NEW IMPLEMENTATION (Date: 2025-09-05)
# ====================

def _enhanced_live_capture(zk):
    """Enhanced live capture with custom socket parsing and proper error handling"""
    app_logger.info("Starting enhanced live capture with custom socket parsing")
    
    try:
        zk.cancel_capture()
        zk.verify_user()
        zk.enable_device()
        zk.reg_event(1)
        zk._ZK__sock.settimeout(10)  # 10 second timeout
        zk.end_live_capture = False
        
        while not zk.end_live_capture:
            try:
                # Check socket state before attempting to read
                if not zk.is_connect:
                    app_logger.warning("Device connection lost during live capture")
                    break
                
                data_recv = zk._ZK__sock.recv(1032)
                
                # Log raw data received from device
                app_logger.info(f"Raw data received: {data_recv.hex()} (length: {len(data_recv)})")
                
                zk._ZK__ack_ok()

                if zk.tcp:
                    size = unpack('<HHI', data_recv[:8])[2]
                    header = unpack('HHHH', data_recv[8:16])
                    data = data_recv[16:]
                else:
                    size = len(data_recv)
                    header = unpack('<4H', data_recv[:8])
                    data = data_recv[8:]

                if not header[0] == 500:
                    continue
                if not len(data):
                    continue
                    
                while len(data) >= 10:
                    user_id, _status, _punch, _timehex, data = _parse_attendance_data(data)
                    
                    if isinstance(user_id, int):
                        user_id = str(user_id)
                    else:
                        user_id = (user_id.split(b'\x00')[0]).decode(errors='ignore')
                    
                    # Parse device timestamp from _timehex
                    device_timestamp = _parse_device_timestamp(_timehex)
                    
                    app_logger.info(f"Live capture: Attendance detected for user_id: {user_id}, status: {_status}, punch: {_punch}, device_time: {device_timestamp}")
                    
                    # Use updated function that gets device info from database
                    _queue_attendance_event(user_id, _status, _punch, None, device_timestamp)
                    
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
            if hasattr(zk, '_ZK__sock') and zk._ZK__sock:
                zk._ZK__sock.settimeout(None)
            zk.reg_event(0)
            app_logger.info("Live capture cleanup completed")
        except Exception as e:
            app_logger.error(f"Error cleaning up live capture: {e}")

def _parse_attendance_data(data):
    """Parse attendance data from different packet formats"""
    if len(data) == 10:
        user_id, _status, _punch, _timehex = unpack('<HBB6s', data)
        remaining_data = data[10:]
    elif len(data) == 12:
        user_id, _status, _punch, _timehex = unpack('<IBB6s', data)
        remaining_data = data[12:]
    elif len(data) == 14:
        user_id, _status, _punch, _timehex, _other = unpack('<HBB6s4s', data)
        remaining_data = data[14:]
    elif len(data) == 32:
        user_id, _status, _punch, _timehex = unpack('<24sBB6s', data[:32])
        remaining_data = data[32:]
    elif len(data) == 36:
        user_id, _status, _punch, _timehex, _other = unpack('<24sBB6s4s', data[:36])
        remaining_data = data[36:]
    elif len(data) == 37:
        user_id, _status, _punch, _timehex, _other = unpack('<24sBB6s5s', data[:37])
        remaining_data = data[37:]
    elif len(data) >= 52:
        user_id, _status, _punch, _timehex, _other = unpack('<24sBB6s20s', data[:52])
        remaining_data = data[52:]
    else:
        # Fallback for unknown formats
        user_id, _status, _punch, _timehex = 0, 0, 0, b'\x00\x00\x00\x00\x00\x00'
        remaining_data = b''
        
    return user_id, _status, _punch, _timehex, remaining_data

def _parse_device_timestamp(timehex_bytes):
    """
    Parse device timestamp from 6-byte timehex format
    ZK Device format: 6 bytes representing YY MM DD HH MM SS in BCD or binary
    """
    try:
        if len(timehex_bytes) != 6:
            app_logger.warning(f"Invalid timehex length: {len(timehex_bytes)}, expected 6 bytes")
            return None
            
        # Try to unpack as little-endian integers
        # Some devices use different formats, so we try multiple approaches
        try:
            # Method 1: Unpack as 6 individual bytes (most common)
            year, month, day, hour, minute, second = struct.unpack('<6B', timehex_bytes)
            
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
            timestamp_int = struct.unpack('<I', timehex_bytes[:4])[0]
            
            # Extract date/time components from packed integer
            year = (timestamp_int & 0x3F) + 2000  # 6 bits for year
            month = (timestamp_int >> 6) & 0x0F   # 4 bits for month
            day = (timestamp_int >> 10) & 0x1F    # 5 bits for day
            hour = (timestamp_int >> 15) & 0x1F   # 5 bits for hour
            minute = (timestamp_int >> 20) & 0x3F # 6 bits for minute
            second = (timestamp_int >> 26) & 0x3F # 6 bits for second
        
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
        app_logger.debug(f"Parsed device timestamp: {device_time} from bytes: {timehex_bytes.hex()}")
        
        return device_time
        
    except Exception as e:
        app_logger.error(f"Error parsing device timestamp from {timehex_bytes.hex()}: {e}")
        return None

def _get_active_device_info():
    """Get active device info from database"""
    try:
        # Get active device from database  
        devices = device_repo.get_all()
        active_device = None
        for device in devices:
            if hasattr(device, 'is_active') and device.is_active:
                active_device = device
                break
        
        if active_device:
            return active_device.id, getattr(active_device, 'serial_number', None)
        
        # Fallback: use environment variables
        device_id = os.environ.get('DEVICE_ID', os.environ.get('DEVICE_IP', 'unknown'))
        serial_number = os.environ.get('DEVICE_SERIAL', None)
        app_logger.warning(f"No active device found in database, using fallback: device_id={device_id}, serial={serial_number}")
        return device_id, serial_number
        
    except Exception as e:
        app_logger.error(f"Error getting active device info: {e}")
        # Emergency fallback
        device_id = os.environ.get('DEVICE_ID', os.environ.get('DEVICE_IP', 'unknown'))
        return device_id, None

def _queue_attendance_event(member_id, status, punch, device_id=None, device_timestamp=None):
    """Queue attendance event to events_queue and save to database"""
    try:
        current_time = datetime.now()
        
        # Get active device info if device_id not provided
        if not device_id:
            device_id, serial_number = _get_active_device_info()
            app_logger.info(f"Using active device: device_id={device_id}, serial_number={serial_number}")
        
        # Use device timestamp if available, otherwise fallback to server time
        actual_timestamp = device_timestamp if device_timestamp else current_time
        
        # Log timestamp source for debugging
        timestamp_source = "device" if device_timestamp else "server"
        app_logger.debug(f"Using {timestamp_source} timestamp: {actual_timestamp}")
        
        # Create AttendanceLog object
        attendance_log = AttendanceLog(
            user_id=str(member_id),
            timestamp=actual_timestamp,  # Use device timestamp
            method=status,  # 1: fingerprint, 4: card, etc.
            action=punch,   # 0: checkin, 1: checkout, etc.
            device_id=device_id,
            serial_number=serial_number if 'serial_number' in locals() else None,
            raw_data={
                "original_status": status,
                "original_punch": punch,
                "device_timestamp": device_timestamp.strftime("%Y-%m-%d %H:%M:%S") if device_timestamp else None,
                "server_timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_source": timestamp_source,
                "device_info": {
                    "device_id": device_id,
                    "serial_number": serial_number if 'serial_number' in locals() else None
                }
            },
            is_synced=False  # Default to not synced
        )
        
        # Save to database safely (avoid duplicates)
        saved_log, is_new = attendance_repo.create_safe(attendance_log)
        if is_new:
            app_logger.info(f"Live capture: Saved new attendance log to database with ID {saved_log.id}")
        else:
            app_logger.info(f"Live capture: Found existing attendance log with ID {saved_log.id}, skipped duplicate")
        
        # Queue for realtime streaming (existing functionality)
        event_data = {
            "id": saved_log.id,  # Include database ID
            "user_id": str(member_id),
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,  # Chấm bằng vân tay hoặc thẻ
            "punch": punch,    # checkin checkout
            "device_id": device_id,
            "is_synced": False
        }
        events_queue.put(event_data)
        app_logger.info(f"Live capture: Queued realtime event for user {member_id}")
        
    except Exception as e:
        app_logger.error(f"Error processing attendance event: {e}")
        # Even if database save fails, try to queue for realtime
        try:
            fallback_event = {
                "user_id": str(member_id),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "punch": punch,
                "device_id": device_id,
                "error": "Database save failed"
            }
            events_queue.put(fallback_event)
        except Exception as queue_error:
            app_logger.error(f"Error queuing fallback event: {queue_error}")


def start_live_capture_thread():
    """Starts the live capture thread if it's not already running."""
    global capture_thread
    with capture_lock:
        if capture_thread is None or not capture_thread.is_alive():
            app_logger.info("Starting live capture background thread.")
            capture_thread = threading.Thread(target=live_capture_worker, daemon=True)
            capture_thread.start()
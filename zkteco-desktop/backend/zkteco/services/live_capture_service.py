import threading
import time
import os
from datetime import datetime
from zk import ZK
from zkteco.events import events_queue
from zkteco.logger import app_logger
from zkteco.zk_mock import ZKMock
from struct import unpack
from socket import timeout

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

                event_data = {
                    "user_id": str(attendance.user_id),
                    "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": attendance.status,
                    "punch": attendance.punch
                }
                events_queue.put(event_data)

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
                        
                    app_logger.info(f"Live capture: Attendance detected for user_id: {user_id}, status: {_status}, punch: {_punch}")
                    _queue_attendance_event(user_id, _status, _punch)
                    
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

def _queue_attendance_event(member_id, status, punch):
    """Queue attendance event to events_queue"""
    try:
        event_data = {
            "user_id": str(member_id),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status, #Chấm bằng vân tay hoặc thẻ
            "punch": punch, #checkin checkout
        }
        events_queue.put(event_data)
        app_logger.info(f"Live capture: Queued event for user {member_id}")
    except Exception as e:
        app_logger.error(f"Error queuing attendance event: {e}")


def start_live_capture_thread():
    """Starts the live capture thread if it's not already running."""
    global capture_thread
    with capture_lock:
        if capture_thread is None or not capture_thread.is_alive():
            app_logger.info("Starting live capture background thread.")
            capture_thread = threading.Thread(target=live_capture_worker, daemon=True)
            capture_thread.start()
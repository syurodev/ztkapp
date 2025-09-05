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
# OLD IMPLEMENTATION - COMMENTED OUT FOR ROLLBACK (Date: 2025-09-05)
# ====================
# def live_capture_worker():
#     """The background worker function that captures attendance."""

#     use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))
#     zk_class = ZKMock if use_mock else ZK

#     ip = os.environ.get('DEVICE_IP')
#     port = int(os.environ.get('DEVICE_PORT', 4370))
#     password = int(os.environ.get('PASSWORD', 0))

#     zk = None

#     while True:
#         try:
#             app_logger.info("Live capture thread: Connecting to device...")
#             zk = zk_class(ip, port=port, password=password, timeout=30, verbose=False)
#             zk.connect()
#             app_logger.info("Live capture thread: Connected successfully.")

#             for attendance in zk.live_capture():
#                 if attendance is None:
#                     continue

#                 app_logger.info(f"Live capture: Received attendance event for user {attendance}")

#                 # The frontend will now be responsible for mapping status and punch codes.
#                 event_data = {
#                     "user_id": str(attendance.user_id),
#                     "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
#                     "status": attendance.status,
#                     "punch": attendance.punch
#                 }
#                 events_queue.put(event_data)
#                 app_logger.info(f"Live capture: Queued event for user {attendance.user_id}")

#         except Exception as e:
#             app_logger.error(f"Live capture thread error: {e}")
#             if zk:
#                 zk.disconnect()
#             app_logger.info("Live capture thread: Reconnecting in 10 seconds...")
#             time.sleep(10)
#         else:
#             app_logger.warning("Live capture loop exited. Reconnecting in 10 seconds.")
#             if zk:
#                 zk.disconnect()
#             time.sleep(10)

# ====================
# NEW IMPLEMENTATION - Based on live_capture.py (Date: 2025-09-05)
# ====================

def live_capture_worker():
    """Enhanced live capture using custom socket parsing from live_capture.py"""
    
    use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))
    
    if use_mock:
        # Keep mock implementation for testing
        app_logger.info("Using mock device for live capture")
        _mock_live_capture_worker()
        return
    
    # Use enhanced ZktecoWrapper for real device
    ip = os.environ.get('DEVICE_IP')
    port = int(os.environ.get('DEVICE_PORT', 4370))
    password = int(os.environ.get('DEVICE_PASSWORD', 1))
    verbose = bool(strtobool(os.getenv("FLASK_DEBUG", "false")))
    
    while True:
        try:
            app_logger.info(f"Enhanced live capture: Initializing connection to {ip}:{port}")
            wrapper = ZktecoWrapper(
                ZK, ip, port=port, verbose=verbose, 
                password=password, enable_live_capture=True
            )
            # If we get here, connection was successful and live capture started
            break
        except Exception as e:
            app_logger.error(f"Enhanced live capture: Failed to initialize ZktecoWrapper: {e}")
            app_logger.info("Enhanced live capture: Retrying in 10 seconds...")
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
                zk.disconnect()
            time.sleep(10)


# ====================
# ENHANCED ZKTECO WRAPPER - Extracted from live_capture.py (Date: 2025-09-05)
# ====================

class ZktecoWrapper:
    """Enhanced ZKTeco wrapper with custom socket parsing for better packet handling"""
    
    def __init__(self, zk_class, ip, port=4370, verbose=False, timeout=None, password=1, force_udp=False, enable_live_capture=False):
        try:
            self.zk = zk_class(
                ip,
                port=port,
                timeout=timeout,
                password=password,
                force_udp=force_udp,
                verbose=verbose
            )
            self.ip = ip
            self.port = port
            self.connect(enable_live_capture)
        except Exception as e:
            app_logger.error(f"Could not connect to Zkteco device on {ip}:{port} : {e}")
            raise

    def start_live_capture_thread(self):
        """Start the live capture in a separate thread"""
        self.live_capture_thread = threading.Thread(target=self.live_capture, daemon=True)
        self.live_capture_thread.start()

    def live_capture(self, new_timeout=None):
        """Enhanced live capture with custom socket parsing"""
        app_logger.info("Starting enhanced live capture with custom socket parsing")
        
        try:
            self.zk.cancel_capture()
            self.zk.verify_user()
            self.enable_device()
            self.zk.reg_event(1)
            self.zk._ZK__sock.settimeout(new_timeout)
            self.zk.end_live_capture = False
            
            while not self.zk.end_live_capture:
                try:
                    data_recv = self.zk._ZK__sock.recv(1032)
                    self.zk._ZK__ack_ok()

                    if self.zk.tcp:
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
                        user_id, _status, _punch, _timehex, data = self._parse_attendance_data(data)
                        
                        if isinstance(user_id, int):
                            user_id = str(user_id)
                        else:
                            user_id = (user_id.split(b'\\x00')[0]).decode(errors='ignore')
                            
                        app_logger.info(f"Enhanced capture: Attendance detected for user_id: {user_id}, status: {_status}, punch: {_punch}")
                        self.queue_attendance_event(user_id, _status, _punch)
                        
                except timeout:
                    app_logger.debug("Socket timeout in live capture")
                except BlockingIOError:
                    pass
                except (KeyboardInterrupt, SystemExit):
                    break
                    
        except Exception as e:
            app_logger.error(f"Live capture error: {e}")
            raise
        finally:
            try:
                self.zk._ZK__sock.settimeout(None)
                self.zk.reg_event(0)
            except Exception as e:
                app_logger.error(f"Error cleaning up live capture: {e}")

    def _parse_attendance_data(self, data):
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
            user_id, _status, _punch, _timehex = 0, 0, 0, b'\\x00\\x00\\x00\\x00\\x00\\x00'
            remaining_data = b''
            
        return user_id, _status, _punch, _timehex, remaining_data

    def queue_attendance_event(self, member_id, status, punch):
        """Queue attendance event to events_queue instead of sending HTTP request"""
        try:
            event_data = {
                "user_id": str(member_id),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "punch": punch
            }
            events_queue.put(event_data)
            app_logger.info(f"Enhanced capture: Queued event for user {member_id}")
        except Exception as e:
            app_logger.error(f"Error queuing attendance event: {e}")

    def connect(self, enable_live_capture=False):
        """Connect to device with retry logic"""
        if self.zk.is_connect and self.zk.helper.test_ping():
            if enable_live_capture:
                self.start_live_capture_thread()
            return

        retry_count = 0
        max_retries_log = 10

        while True:
            try:
                self.zk.connect()
                app_logger.info(f"Enhanced wrapper: Connected to ZK device successfully at {self.ip}:{self.port}")
                retry_count = 0
                if enable_live_capture:
                    self.start_live_capture_thread()
                self.keepAlive()
                return
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries_log:
                    app_logger.warning(f"Enhanced wrapper: Failed to connect to ZK device. Retrying... ({e})")
                time.sleep(6)
                continue

    def keepAlive(self):
        """Keep connection alive with ping checks"""
        while True:
            try:
                isDeviceAlive = self.zk.helper.test_ping()
                if not isDeviceAlive:
                    app_logger.warning("Enhanced wrapper: Device disconnected, terminating live capture.")
                    self.zk.end_live_capture = True
                    return
                time.sleep(15)
            except Exception as e:
                app_logger.error(f"Error in keepAlive: {e}")
                return

    def enable_device(self):
        """Enable the device"""
        self.zk.enable_device()

    def disable_device(self):
        """Disable the device"""  
        self.zk.disable_device()


def start_live_capture_thread():
    """Starts the live capture thread if it's not already running."""
    global capture_thread
    with capture_lock:
        if capture_thread is None or not capture_thread.is_alive():
            app_logger.info("Starting live capture background thread.")
            capture_thread = threading.Thread(target=live_capture_worker, daemon=True)
            capture_thread.start()

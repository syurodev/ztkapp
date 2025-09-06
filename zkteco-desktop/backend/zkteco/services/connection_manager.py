import threading
import time
import os
from typing import Optional, Type
from zk import ZK
from zkteco.logger import app_logger
from zkteco.zk_mock import ZKMock


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0)."""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError(f"invalid truth value {val!r}")


class ZkConnectionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ZkConnectionManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._connections: dict = {}  # device_id -> ZK instance
        self._connection_locks: dict = {}  # device_id -> Lock
        self._device_configs: dict = {}  # device_id -> config
        self._last_ping_times: dict = {}  # device_id -> timestamp
        self._main_lock = threading.Lock()
        
        # Legacy support
        self._zk_instance: Optional[ZK] = None
        self._connection_lock = threading.Lock()
        self._config = {}
        self._last_ping_time = 0
        self._ping_interval = 30  # seconds
        self._max_retries = 3
        self._retry_delay = 2  # seconds

        app_logger.info("ZkConnectionManager initialized")

    def configure_device(self, device_id: str, config: dict):
        """Configure connection parameters for a specific device"""
        with self._main_lock:
            # Ensure device has a lock
            if device_id not in self._connection_locks:
                self._connection_locks[device_id] = threading.Lock()
                
            with self._connection_locks[device_id]:
                # Check if config has actually changed to avoid unnecessary resets
                old_config = self._device_configs.get(device_id, {})
                if old_config == config:
                    app_logger.debug(f"Configuration unchanged for device {device_id}, skipping reset")
                    return
                    
                self._device_configs[device_id] = config.copy()
                app_logger.info(f"Device {device_id} configured with: {config}")
                
                # Only reset connection if critical connection parameters changed
                connection_params = ['ip', 'port', 'password', 'timeout', 'force_udp']
                config_changed = any(old_config.get(param) != config.get(param) for param in connection_params)
                
                if device_id in self._connections and config_changed:
                    app_logger.info(f"Critical connection parameters changed for device {device_id}, resetting connection")
                    self.reset_device_connection(device_id)
                elif device_id in self._connections:
                    app_logger.debug(f"Non-critical parameters changed for device {device_id}, keeping existing connection")
    
    def configure(self, config: dict):
        """Legacy configure method - uses active device"""
        from zkteco.config.config_manager_sqlite import config_manager
        active_device = config_manager.get_active_device()
        
        if active_device:
            # Configure the active device
            device_config = {
                'ip': config.get('ip') or active_device.get('ip'),
                'port': config.get('port') or active_device.get('port'),
                'password': config.get('password') or active_device.get('password'),
                'timeout': config.get('timeout') or active_device.get('timeout'),
                'force_udp': config.get('force_udp') or active_device.get('force_udp'),
                'verbose': config.get('verbose', False),
                'retry_count': config.get('retry_count') or active_device.get('retry_count'),
                'retry_delay': config.get('retry_delay') or active_device.get('retry_delay'),
                'ping_interval': config.get('ping_interval') or active_device.get('ping_interval')
            }
            self.configure_device(active_device['id'], device_config)
        else:
            # Legacy fallback
            with self._connection_lock:
                old_config = self._config.copy() if self._config else {}
                self._config = config.copy()
                self._ping_interval = config.get('ping_interval', 30)
                self._max_retries = config.get('retry_count', 3)
                self._retry_delay = config.get('retry_delay', 2)
                
                app_logger.info(f"Legacy ZkConnectionManager configured with: {config}")
                
                connection_params = ['ip', 'port', 'password', 'timeout', 'force_udp']
                config_changed = any(old_config.get(param) != config.get(param) for param in connection_params)
                
                if self._zk_instance and config_changed:
                    app_logger.info("Critical connection parameters changed, resetting legacy connection")
                    self.reset_connection()
                elif self._zk_instance:
                    app_logger.debug("Non-critical parameters changed, keeping existing legacy connection")

    def get_device_connection(self, device_id: str) -> ZK:
        """Get a healthy ZK connection for a specific device"""
        with self._main_lock:
            # Ensure device has a lock
            if device_id not in self._connection_locks:
                self._connection_locks[device_id] = threading.Lock()
                
        with self._connection_locks[device_id]:
            app_logger.debug(f"get_device_connection() called for device {device_id} - instance exists: {device_id in self._connections}")
            
            if device_id in self._connections:
                connection = self._connections[device_id]
                app_logger.debug(f"Current instance is_connect: {connection.is_connect}")
                last_ping = self._last_ping_times.get(device_id, 0)
                app_logger.debug(f"Last ping time: {last_ping}, current time: {time.time()}")
            
            if device_id not in self._connections or not self._is_device_connection_healthy(device_id):
                app_logger.info(f"Establishing new connection for device {device_id} due to unhealthy or missing connection")
                self._establish_device_connection(device_id)
            else:
                app_logger.debug(f"Using existing healthy connection for device {device_id}")
            return self._connections[device_id]
    
    def get_connection(self) -> ZK:
        """Legacy get connection method - uses active device"""
        from zkteco.config.config_manager_sqlite import config_manager
        active_device = config_manager.get_active_device()
        
        if active_device:
            # Configure device if not already configured
            if active_device['id'] not in self._device_configs:
                device_config = {
                    'ip': active_device.get('ip'),
                    'port': active_device.get('port'),
                    'password': active_device.get('password'),
                    'timeout': active_device.get('timeout'),
                    'force_udp': active_device.get('force_udp'),
                    'verbose': bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
                    'retry_count': active_device.get('retry_count'),
                    'retry_delay': active_device.get('retry_delay'),
                    'ping_interval': active_device.get('ping_interval')
                }
                self.configure_device(active_device['id'], device_config)
            
            return self.get_device_connection(active_device['id'])
        else:
            # Legacy fallback
            with self._connection_lock:
                app_logger.debug(f"Legacy get_connection() called - instance exists: {self._zk_instance is not None}")
                if self._zk_instance:
                    app_logger.debug(f"Current instance is_connect: {self._zk_instance.is_connect}")
                    app_logger.debug(f"Last ping time: {self._last_ping_time}, current time: {time.time()}")
                
                if self._zk_instance is None or not self._is_connection_healthy():
                    app_logger.info("Establishing new legacy connection due to unhealthy or missing connection")
                    self._establish_connection()
                else:
                    app_logger.debug("Using existing healthy legacy connection")
                return self._zk_instance
    
    def ensure_device_connection(self, device_id: str) -> ZK:
        """Ensure device connection is active and reconnect if needed - more aggressive check"""
        with self._main_lock:
            if device_id not in self._connection_locks:
                self._connection_locks[device_id] = threading.Lock()
                
        with self._connection_locks[device_id]:
            app_logger.info(f"ensure_device_connection() called for device {device_id} - instance exists: {device_id in self._connections}")
            
            # Always do a fresh health check for critical operations
            if device_id not in self._connections:
                app_logger.info(f"No connection exists for device {device_id}, creating new one")
                self._establish_device_connection(device_id)
                return self._connections[device_id]
            
            connection = self._connections[device_id]
            config = self._device_configs.get(device_id, {})
            app_logger.info(f"Current connection state for device {device_id} - is_connect: {connection.is_connect}")
            app_logger.info(f"Connection config: {config}")
                
            # Force a ping test regardless of timing for ensure_connection
            try:
                if not connection.is_connect:
                    app_logger.warning(f"Connection status is False for device {device_id}, reconnecting")
                    self._establish_device_connection(device_id)
                elif hasattr(connection, 'helper'):
                    app_logger.info(f"Testing ping for device {device_id}...")
                    ping_result = connection.helper.test_ping()
                    app_logger.info(f"Ping test result for device {device_id}: {ping_result}")
                    if not ping_result:
                        app_logger.warning(f"Ping test failed for device {device_id}, reconnecting")
                        self._establish_device_connection(device_id)
                    else:
                        app_logger.info(f"Ping test passed for device {device_id} - connection is healthy")
                        # Ensure device is enabled before returning the connection
                        try:
                            app_logger.info(f"Ensuring device {device_id} is enabled...")
                            connection.enable_device()
                            app_logger.info(f"Device {device_id} enabled successfully")
                        except Exception as enable_error:
                            app_logger.warning(f"Failed to enable device {device_id}, reconnecting: {enable_error}")
                            self._establish_device_connection(device_id)
                else:
                    app_logger.warning(f"No helper available for device {device_id}, reconnecting")
                    self._establish_device_connection(device_id)
            except Exception as e:
                app_logger.error(f"Connection check failed for device {device_id}, reconnecting: {e}")
                self._establish_device_connection(device_id)
                
            return self._connections[device_id]
    
    def ensure_connection(self) -> ZK:
        """Legacy ensure connection method - uses active device"""
        from zkteco.config.config_manager_sqlite import config_manager
        active_device = config_manager.get_active_device()
        
        if active_device:
            # Configure device if not already configured
            if active_device['id'] not in self._device_configs:
                device_config = {
                    'ip': active_device.get('ip'),
                    'port': active_device.get('port'),
                    'password': active_device.get('password'),
                    'timeout': active_device.get('timeout'),
                    'force_udp': active_device.get('force_udp'),
                    'verbose': bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
                    'retry_count': active_device.get('retry_count'),
                    'retry_delay': active_device.get('retry_delay'),
                    'ping_interval': active_device.get('ping_interval')
                }
                self.configure_device(active_device['id'], device_config)
            
            return self.ensure_device_connection(active_device['id'])
        else:
            # Legacy fallback
            with self._connection_lock:
                app_logger.info(f"Legacy ensure_connection() called - instance exists: {self._zk_instance is not None}")
                
                if self._zk_instance is None:
                    app_logger.info("No legacy connection exists, creating new one")
                    self._establish_connection()
                    return self._zk_instance
                
                app_logger.info(f"Current legacy connection state - is_connect: {self._zk_instance.is_connect}")
                app_logger.info(f"Legacy connection config: {self._config}")
                    
                # Force a ping test regardless of timing for ensure_connection
                try:
                    if not self._zk_instance.is_connect:
                        app_logger.warning("Legacy connection status is False, reconnecting")
                        self._establish_connection()
                    elif hasattr(self._zk_instance, 'helper'):
                        app_logger.info("Testing ping for legacy connection...")
                        ping_result = self._zk_instance.helper.test_ping()
                        app_logger.info(f"Legacy ping test result: {ping_result}")
                        if not ping_result:
                            app_logger.warning("Legacy ping test failed, reconnecting")
                            self._establish_connection()
                        else:
                            app_logger.info("Legacy ping test passed - connection is healthy")
                            try:
                                app_logger.info("Ensuring legacy device is enabled...")
                                self._zk_instance.enable_device()
                                app_logger.info("Legacy device enabled successfully")
                            except Exception as enable_error:
                                app_logger.warning(f"Failed to enable legacy device, reconnecting: {enable_error}")
                                self._establish_connection()
                    else:
                        app_logger.warning("No helper available for legacy connection, reconnecting")
                        self._establish_connection()
                except Exception as e:
                    app_logger.error(f"Legacy connection check failed, reconnecting: {e}")
                    self._establish_connection()
                    
                return self._zk_instance

    def _is_device_connection_healthy(self, device_id: str) -> bool:
        """Check if device connection is healthy"""
        app_logger.debug(f"_is_device_connection_healthy() called for device {device_id}")
        
        if device_id not in self._connections:
            app_logger.debug(f"No instance exists for device {device_id} - unhealthy")
            return False

        connection = self._connections[device_id]
        
        # Skip ping test for mock devices
        if hasattr(connection, '__class__') and 'Mock' in connection.__class__.__name__:
            app_logger.debug(f"Mock device {device_id} - is_connect: {connection.is_connect}")
            return connection.is_connect

        # Always check connection status first
        if not connection.is_connect:
            app_logger.debug(f"Connection status is False for device {device_id} - unhealthy")
            return False

        current_time = time.time()
        last_ping_time = self._last_ping_times.get(device_id, 0)
        time_since_last_ping = current_time - last_ping_time
        
        # Get ping interval from device config
        config = self._device_configs.get(device_id, {})
        ping_check_interval = config.get('ping_interval', 10)
        
        app_logger.debug(f"Device {device_id} - Time since last ping: {time_since_last_ping}s, interval: {ping_check_interval}s")
        
        # Only ping if enough time has passed since last ping
        if time_since_last_ping < ping_check_interval:
            app_logger.debug(f"Device {device_id} within ping interval - assuming healthy")
            return True

        try:
            app_logger.debug(f"Performing ping test for device {device_id}...")
            # Perform actual ping test
            ping_result = connection.helper.test_ping()
            app_logger.debug(f"Ping test result for device {device_id}: {ping_result}")
            
            if ping_result:
                self._last_ping_times[device_id] = current_time
                app_logger.debug(f"Ping successful for device {device_id} - connection healthy")
                return True
            else:
                app_logger.warning(f"Connection ping test failed for device {device_id} - device not responding")
                return False
        except Exception as e:
            app_logger.warning(f"Connection health check failed for device {device_id}: {e}")
            return False
    
    def _is_connection_healthy(self) -> bool:
        """Legacy connection health check"""
        app_logger.debug("Legacy _is_connection_healthy() called")
        
        if self._zk_instance is None:
            app_logger.debug("No legacy instance exists - unhealthy")
            return False

        # Skip ping test for mock devices
        if hasattr(self._zk_instance, '__class__') and 'Mock' in self._zk_instance.__class__.__name__:
            app_logger.debug(f"Legacy mock device - is_connect: {self._zk_instance.is_connect}")
            return self._zk_instance.is_connect

        # Always check connection status first
        if not self._zk_instance.is_connect:
            app_logger.debug("Legacy connection status is False - unhealthy")
            return False

        current_time = time.time()
        time_since_last_ping = current_time - self._last_ping_time
        
        # Reduce ping interval to check more frequently (every 10 seconds instead of 30)
        ping_check_interval = 10
        
        app_logger.debug(f"Legacy - Time since last ping: {time_since_last_ping}s, interval: {ping_check_interval}s")
        
        # Only ping if enough time has passed since last ping
        if time_since_last_ping < ping_check_interval:
            app_logger.debug("Legacy within ping interval - assuming healthy")
            return True

        try:
            app_logger.debug("Performing legacy ping test...")
            # Perform actual ping test
            ping_result = self._zk_instance.helper.test_ping()
            app_logger.debug(f"Legacy ping test result: {ping_result}")
            
            if ping_result:
                self._last_ping_time = current_time
                app_logger.debug("Legacy ping successful - connection healthy")
                return True
            else:
                app_logger.warning("Legacy connection ping test failed - device not responding")
                return False
        except Exception as e:
            app_logger.warning(f"Legacy connection health check failed: {e}")
            return False

    def _establish_device_connection(self, device_id: str):
        """Establish a new ZK connection for a specific device"""
        app_logger.info(f"_establish_device_connection() called for device {device_id}")
        
        if device_id not in self._device_configs:
            app_logger.error(f"Device {device_id} not configured")
            raise ValueError(f"Device {device_id} not configured. Call configure_device() first.")

        config = self._device_configs[device_id]
        app_logger.info(f"Using config for device {device_id}: {config}")

        # Close existing connection if any
        if device_id in self._connections:
            app_logger.info(f"Closing existing connection for device {device_id}")
            try:
                self._connections[device_id].disconnect()
                app_logger.info(f"Successfully closed existing connection for device {device_id}")
            except Exception as e:
                app_logger.warning(f"Error closing existing connection for device {device_id}: {e}")

        # Determine ZK class (mock or real)
        use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))
        zk_class = ZKMock if use_mock else ZK
        app_logger.info(f"Using ZK class for device {device_id}: {zk_class.__name__}, mock: {use_mock}")

        # Create new ZK instance
        connection_params = {
            'ip': config.get('ip'),
            'port': config.get('port', 4370),
            'timeout': config.get('timeout', 10),
            'password': config.get('password', 0),
            'force_udp': config.get('force_udp', False),
            'verbose': config.get('verbose', False)
        }
        app_logger.info(f"Creating ZK instance for device {device_id} with params: {connection_params}")
        
        zk_instance = zk_class(**connection_params)
        self._connections[device_id] = zk_instance

        # Connect with retry logic
        self._connect_device_with_retry(device_id)
    
    def _establish_connection(self):
        """Legacy establish connection"""
        app_logger.info("Legacy _establish_connection() called")
        
        if not self._config:
            app_logger.error("Legacy connection not configured")
            raise ValueError("Legacy connection not configured. Call configure() first.")

        app_logger.info(f"Using legacy config: {self._config}")

        # Close existing connection if any
        if self._zk_instance:
            app_logger.info("Closing existing legacy connection")
            try:
                self._zk_instance.disconnect()
                app_logger.info("Successfully closed existing legacy connection")
            except Exception as e:
                app_logger.warning(f"Error closing existing legacy connection: {e}")

        # Determine ZK class (mock or real)
        use_mock = bool(strtobool(os.getenv("USE_MOCK_DEVICE", "false")))
        zk_class = ZKMock if use_mock else ZK
        app_logger.info(f"Using ZK class for legacy: {zk_class.__name__}, mock: {use_mock}")

        # Create new ZK instance
        connection_params = {
            'ip': self._config.get('ip'),
            'port': self._config.get('port', 4370),
            'timeout': self._config.get('timeout', 10),
            'password': self._config.get('password', 0),
            'force_udp': self._config.get('force_udp', False),
            'verbose': self._config.get('verbose', False)
        }
        app_logger.info(f"Creating legacy ZK instance with params: {connection_params}")
        
        self._zk_instance = zk_class(**connection_params)

        # Connect with retry logic
        self._connect_with_retry()

    def _connect_device_with_retry(self, device_id: str):
        """Connect device with retry mechanism"""
        app_logger.info(f"_connect_device_with_retry() called for device {device_id}")
        
        config = self._device_configs[device_id]
        max_retries = config.get('retry_count', 3)
        retry_delay = config.get('retry_delay', 2)
        retry_count = 0

        while retry_count < max_retries:
            try:
                app_logger.info(f"Connection attempt {retry_count + 1}/{max_retries} for device {device_id}")
                app_logger.info(f"Calling connect() on ZK instance for device {device_id}...")
                
                self._connections[device_id].connect()
                
                app_logger.info(f"connect() returned successfully for device {device_id}")
                app_logger.info(f"Post-connect is_connect status for device {device_id}: {self._connections[device_id].is_connect}")
                app_logger.info(f"Successfully connected to ZK device {device_id} at {config.get('ip')}:{config.get('port')}")
                
                self._last_ping_times[device_id] = time.time()
                app_logger.info(f"Set last ping time for device {device_id} to: {self._last_ping_times[device_id]}")
                
                return
                
            except Exception as e:
                retry_count += 1
                app_logger.error(f"Connection attempt {retry_count}/{max_retries} failed for device {device_id} with error: {type(e).__name__}: {e}")
                
                if retry_count >= max_retries:
                    app_logger.error(f"Failed to connect to ZK device {device_id} after {max_retries} attempts: {e}")
                    raise e
                    
                app_logger.warning(f"Retrying device {device_id} connection in {retry_delay}s...")
                time.sleep(retry_delay)
    
    def _connect_with_retry(self):
        """Legacy connect with retry mechanism"""
        app_logger.info("Legacy _connect_with_retry() called")
        retry_count = 0

        while retry_count < self._max_retries:
            try:
                app_logger.info(f"Legacy connection attempt {retry_count + 1}/{self._max_retries}")
                app_logger.info(f"Calling connect() on legacy ZK instance...")
                
                self._zk_instance.connect()
                
                app_logger.info(f"Legacy connect() returned successfully")
                app_logger.info(f"Legacy post-connect is_connect status: {self._zk_instance.is_connect}")
                app_logger.info(f"Successfully connected to legacy ZK device at {self._config.get('ip')}:{self._config.get('port')}")
                
                self._last_ping_time = time.time()
                app_logger.info(f"Set legacy last ping time to: {self._last_ping_time}")
                
                return
                
            except Exception as e:
                retry_count += 1
                app_logger.error(f"Legacy connection attempt {retry_count}/{self._max_retries} failed with error: {type(e).__name__}: {e}")
                
                if retry_count >= self._max_retries:
                    app_logger.error(f"Failed to connect to legacy ZK device after {self._max_retries} attempts: {e}")
                    raise e
                    
                app_logger.warning(f"Retrying legacy connection in {self._retry_delay}s...")
                time.sleep(self._retry_delay)

    def disconnect_device(self, device_id: str):
        """Disconnect from a specific ZK device"""
        if device_id in self._connection_locks:
            with self._connection_locks[device_id]:
                if device_id in self._connections:
                    try:
                        self._connections[device_id].disconnect()
                        app_logger.info(f"Disconnected from ZK device {device_id}")
                    except Exception as e:
                        app_logger.error(f"Error disconnecting from ZK device {device_id}: {e}")
                    finally:
                        del self._connections[device_id]
                        if device_id in self._last_ping_times:
                            del self._last_ping_times[device_id]
    
    def disconnect_all_devices(self):
        """Disconnect from all devices"""
        with self._main_lock:
            device_ids = list(self._connections.keys())
            for device_id in device_ids:
                self.disconnect_device(device_id)
    
    def disconnect(self):
        """Legacy disconnect from ZK device"""
        with self._connection_lock:
            if self._zk_instance:
                try:
                    self._zk_instance.disconnect()
                    app_logger.info("Disconnected from legacy ZK device")
                except Exception as e:
                    app_logger.error(f"Error disconnecting from legacy ZK device: {e}")
                finally:
                    self._zk_instance = None

    def is_device_connected(self, device_id: str) -> bool:
        """Check if a specific device is currently connected"""
        if device_id in self._connection_locks:
            with self._connection_locks[device_id]:
                return device_id in self._connections and self._connections[device_id].is_connect
        return False
    
    def is_connected(self) -> bool:
        """Legacy check if currently connected"""
        from zkteco.config.config_manager_sqlite import config_manager
        active_device = config_manager.get_active_device()
        
        if active_device:
            return self.is_device_connected(active_device['id'])
        else:
            # Legacy fallback
            with self._connection_lock:
                return self._zk_instance is not None and self._zk_instance.is_connect

    def reset_device_connection(self, device_id: str):
        """Force reset a specific device connection"""
        if device_id in self._connection_locks:
            with self._connection_locks[device_id]:
                app_logger.info(f"Resetting ZK connection for device {device_id}")
                if device_id in self._connections:
                    try:
                        self._connections[device_id].disconnect()
                    except:
                        pass
                    del self._connections[device_id]
                if device_id in self._last_ping_times:
                    del self._last_ping_times[device_id]
    
    def reset_connection(self):
        """Legacy force reset the connection"""
        from zkteco.config.config_manager_sqlite import config_manager
        active_device = config_manager.get_active_device()
        
        if active_device:
            self.reset_device_connection(active_device['id'])
        else:
            # Legacy fallback
            with self._connection_lock:
                app_logger.info("Resetting legacy ZK connection")
                if self._zk_instance:
                    try:
                        self._zk_instance.disconnect()
                    except:
                        pass
                self._zk_instance = None



# Global instance
connection_manager = ZkConnectionManager()

def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0)."""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError(f"invalid truth value {val!r}")

import os
import time
import requests
from typing import Type

from dotenv import load_dotenv
from zk import ZK, const

from zkteco.logger import app_logger
from zkteco.zk_mock import ZKMock
from zkteco.services.connection_manager import connection_manager
from zkteco.config.config_manager_sqlite import config_manager
from zkteco.database.models import user_repo

load_dotenv()

class ZkService:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def create_user(self, user_id, user_data, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"create_user() called with user_id: {user_id}, data: {user_data}, device_id: {target_device_id}")
        zk_instance = None
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            app_logger.info(f"Got connection, is_connect: {zk_instance.is_connect}")
            
            app_logger.info("Disabling device...")
            zk_instance.disable_device()
            app_logger.info("Device disabled")

            app_logger.info("Setting user...")
            zk_instance.set_user(
                uid=user_id,
                name=user_data.get('name'),
                privilege=user_data.get('privilege', const.USER_DEFAULT),
                password=user_data.get('password', ''),
                group_id=user_data.get('group_id', 0),
                user_id=str(user_id),
                card=user_data.get('card', 0)
            )
            app_logger.info("User set successfully")
        except Exception as e:
            app_logger.error(f"Error in create_user: {type(e).__name__}: {e}")
            raise
        finally:
            if zk_instance:
                app_logger.info("Enabling device...")
                zk_instance.enable_device()
                app_logger.info("Device enabled")
            app_logger.info("create_user() completed")

    def get_all_users(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"get_all_users() called for device {target_device_id}")
        zk_instance = None
        device_was_disabled = False
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            app_logger.info(f"Got connection, is_connect: {zk_instance.is_connect}")
            
            app_logger.info("Disabling device...")
            zk_instance.disable_device()
            device_was_disabled = True
            app_logger.info("Device disabled")
            
            app_logger.info("Getting users...")
            users = zk_instance.get_users()
            app_logger.info(f"Retrieved {len(users)} users")

            return users
        except Exception as e:
            app_logger.error(f"Error in get_all_users: {type(e).__name__}: {e}")
            # If we got a TCP error and device was disabled, try to reset connection
            if device_was_disabled and "TCP" in str(e):
                app_logger.warning(f"TCP error after device disable, resetting connection for device {target_device_id}")
                if target_device_id:
                    connection_manager.reset_device_connection(target_device_id)
                else:
                    connection_manager.reset_connection()
            raise
        finally:
            if zk_instance and device_was_disabled:
                try:
                    app_logger.info("Enabling device...")
                    zk_instance.enable_device()
                    app_logger.info("Device enabled")
                except Exception as enable_error:
                    app_logger.error(f"Failed to enable device: {enable_error}")
                    # Reset connection if enable fails
                    if target_device_id:
                        connection_manager.reset_device_connection(target_device_id)
                    else:
                        connection_manager.reset_connection()
            app_logger.info("get_all_users() completed")

    def delete_user(self, user_id, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.delete_user(
                uid=user_id,
                user_id=str(user_id)
            )
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def enroll_user(self, user_id, temp_id, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.enroll_user(
                uid = user_id,
                temp_id = temp_id,
                user_id = str(user_id)
            )
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def cancel_enroll_user(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.end_live_capture = True
            zk_instance.disable_device()
            zk_instance.cancel_capture()
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def delete_user_template(self, user_id, temp_id, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.delete_user_template(
                uid = user_id,
                temp_id = temp_id,
                user_id= str(user_id)
            )
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_user_template(self, user_id, temp_id, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            template = zk_instance.get_user_template(
                uid = user_id,
                temp_id = temp_id,
                user_id = str(user_id)
            )
            return template
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_attendance(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            attendance = zk_instance.get_attendance()

            return attendance
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_device_info(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"get_device_info() called for device {target_device_id}")
        zk_instance = None
        device_was_disabled = False
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(target_device_id)
            else:
                zk_instance = connection_manager.ensure_connection()
            app_logger.info(f"Got connection, is_connect: {zk_instance.is_connect}")
            
            app_logger.info("Disabling device...")
            zk_instance.disable_device()
            device_was_disabled = True
            app_logger.info("Device disabled")
            
            app_logger.info("Getting device information...")
            device_info = {
                'current_time': zk_instance.get_time().strftime('%Y-%m-%d %H:%M:%S') if zk_instance.get_time() else None,
                'firmware_version': zk_instance.get_firmware_version(),
                'device_name': zk_instance.get_device_name(),
                'serial_number': zk_instance.get_serialnumber(),
                'mac_address': zk_instance.get_mac(),
                'face_version': zk_instance.get_face_version(),
                'fp_version': zk_instance.get_fp_version(),
                'platform': zk_instance.get_platform()
            }
            
            # Get network information
            try:
                network_info = zk_instance.get_network_params()
                device_info['network'] = {
                    'ip': network_info.get('ip'),
                    'netmask': network_info.get('mask'),
                    'gateway': network_info.get('gateway')
                }
            except Exception as network_error:
                app_logger.warning(f"Could not get network info: {network_error}")
                device_info['network'] = None
            
            app_logger.info(f"Retrieved device info: {device_info}")
            return device_info
            
        except Exception as e:
            app_logger.error(f"Error in get_device_info: {type(e).__name__}: {e}")
            if device_was_disabled and "TCP" in str(e):
                app_logger.warning(f"TCP error after device disable, resetting connection for device {target_device_id}")
                if target_device_id:
                    connection_manager.reset_device_connection(target_device_id)
                else:
                    connection_manager.reset_connection()
            raise
        finally:
            if zk_instance and device_was_disabled:
                try:
                    app_logger.info("Enabling device...")
                    zk_instance.enable_device()
                    app_logger.info("Device enabled")
                except Exception as enable_error:
                    app_logger.error(f"Failed to enable device: {enable_error}")
                    if target_device_id:
                        connection_manager.reset_device_connection(target_device_id)
                    else:
                        connection_manager.reset_connection()
            app_logger.info("get_device_info() completed")

    def save_device_info_to_config(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"save_device_info_to_config() called for device {target_device_id}")
        try:
            device_info = self.get_device_info(target_device_id)
            
            # Save device info to config
            config_manager.save_device_info(device_info, target_device_id)
            app_logger.info(f"Device info saved to config successfully for device {target_device_id}")
            
            return device_info
        except Exception as e:
            app_logger.error(f"Error in save_device_info_to_config for device {target_device_id}: {type(e).__name__}: {e}")
            raise

    def sync_employee(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"sync_employee() called for device {target_device_id}")
        try:
            # Get active device info
            if target_device_id:
                device = config_manager.get_device(target_device_id)
            else:
                device = config_manager.get_active_device()
                target_device_id = device['id'] if device else None
            
            if not device:
                raise ValueError("No device found for sync")
            
            # Get all users from database for this device
            db_users = user_repo.get_all(device_id=target_device_id)
            app_logger.info(f"Retrieved {len(db_users)} users from database for sync to external API")
            
            # Get external API URL from config (new dynamic approach)
            external_api_domain = config_manager.get_external_api_url()
            
            if not external_api_domain:
                raise ValueError("EXTERNAL_API_DOMAIN not configured in config.json")
            
            external_api_url = external_api_domain + '/time-clock-employees/sync'
            
            # Get device info for serial number
            device_info = device.get('device_info', {})
            serial_number = device_info.get('serial_number', target_device_id or 'unknown')
            
            # Format employees data from database users
            employees = []
            user_ids_to_sync = []  # Track user IDs that will be synced
            
            for user in db_users:
                employee = {
                    "userId": user.user_id,
                    "name": user.name,
                    "groupId": user.group_id
                }
                employees.append(employee)
                user_ids_to_sync.append(user.id)  # Store the database ID for later update
            
            if not employees:
                return {
                    'success': True,
                    'employees_count': 0,
                    'message': 'No users to sync'
                }
            
            # Prepare sync data
            sync_data = {
                "timestamp": int(time.time()),
                "employees": employees
            }
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'x-device-sync': serial_number,
                'ProjectId': "1055"
            }
            
            # Make API request
            response = requests.post(
                external_api_url,
                json=sync_data,
                headers=headers,
                timeout=30
            )

            data = response.json()

            if data.get('status') != 200:
                return {
                    'success': False,
                    'message': data.get('message')
                }
            
            response.raise_for_status()
            
            # If sync successful, update users as synced in database
            from datetime import datetime
            synced_count = 0
            
            for user_id in user_ids_to_sync:
                try:
                    user_repo.update(user_id, {
                        'is_synced': True,
                        'synced_at': datetime.now()
                    })
                    synced_count += 1
                except Exception as update_error:
                    app_logger.warning(f"Failed to update sync status for user {user_id}: {update_error}")
            
            app_logger.info(f"Successfully synced {len(employees)} employees to external API and updated {synced_count} users in database")
            
            return {
                'success': True,
                'employees_count': len(employees),
                'synced_users_count': synced_count,
                'timestamp': sync_data['timestamp'],
                'response_status': response.status_code,
                'external_api_response': data
            }
            
        except requests.exceptions.RequestException as e:
            app_logger.error(f"HTTP error in sync_employee: {e}")
            raise
        except Exception as e:
            app_logger.error(f"Error in sync_employee: {type(e).__name__}: {e}")
            raise



def get_zk_service(device_id: str = None):
    if device_id:
        # Get specific device configuration
        device = config_manager.get_device(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")
            
        # Configure the connection manager for this device
        device_config = {
            'ip': device.get('ip'),
            'port': device.get('port'),
            'password': device.get('password'),
            'timeout': device.get('timeout'),
            'force_udp': device.get('force_udp'),
            'verbose': bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
            'retry_count': device.get('retry_count'),
            'retry_delay': device.get('retry_delay'),
            'ping_interval': device.get('ping_interval')
        }
        
        connection_manager.configure_device(device_id, device_config)
        return ZkService(device_id)
        
    else:
        # Legacy mode - use active device or fallback to old config
        active_device = config_manager.get_active_device()
        
        if active_device:
            return get_zk_service(active_device['id'])
        else:
            # Legacy fallback
            config = config_manager.get_config()
            connection_config = {
                'ip': config.get('DEVICE_IP'),
                'port': int(config.get('DEVICE_PORT', 4370)),
                'password': int(config.get('DEVICE_PASSWORD', 0)),
                'verbose': bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
                'timeout': config.get('CONNECTION_TIMEOUT', 10),
                'force_udp': config.get('CONNECTION_FORCE_UDP', False),
                'retry_count': config.get('CONNECTION_RETRY_COUNT', 3),
                'retry_delay': config.get('CONNECTION_RETRY_DELAY', 2),
                'ping_interval': config.get('CONNECTION_PING_INTERVAL', 30)
            }
            
            connection_manager.configure(connection_config)
            return ZkService()

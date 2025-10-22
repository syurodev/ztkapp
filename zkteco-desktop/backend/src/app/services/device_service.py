import os
import json
import time
import signal
import requests
from typing import Any, Dict, List, Optional, Type

from dotenv import load_dotenv

# Import the new library and its user object
from pyzatt.pyzatt import ZKSS
from pyzatt.pyzatt import ZKUser as PyzattUser
from pyzatt.pyzatt import ATTen as PyzattAttendance

# Keep the old User object for type compatibility in other parts of the app for now
from zk.user import User as PyzkUser
from app.models.attendance import AttendanceLog as PyzkAttendance

from app.shared.logger import app_logger
from app.config.config_manager import config_manager
from app.repositories import user_repo, attendance_repo
from app.models import AttendanceLog, SyncStatus
from app.services.external_api_service import external_api_service

load_dotenv()


class ZkService:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def _get_z_instance(self):
        """Helper to get a configured ZKSS instance."""
        target_device_id = self.device_id
        if not target_device_id:
            active_device = config_manager.get_active_device()
            if not active_device:
                raise ValueError("No active device configured.")
            target_device_id = active_device["id"]

        device_config = config_manager.get_device(target_device_id)
        if not device_config:
            raise ValueError(f"Device {target_device_id} not found in config")

        ip = device_config.get("ip")
        port = device_config.get("port", 4370)

        app_logger.info(f"Creating ZKSS instance for {ip}:{port}")
        return ZKSS(), ip, port

    def get_all_users(self, timeout=10):
        """Get all users from device using pyzatt."""
        app_logger.info(
            f"get_all_users() called for device {self.device_id} using pyzatt with a timeout of {timeout} seconds"
        )
        z, ip, port = self._get_z_instance()

        def handler(signum, frame):
            raise TimeoutError("Device connection timed out")

        # Set the timeout alarm
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

        try:
            app_logger.info(f"Connecting to {ip}:{port} with pyzatt...")
            z.connect_net(ip, dev_port=port)
            app_logger.info("pyzatt connection successful. Fetching users...")

            z.read_all_user_id()
            pyzatt_users = list(z.users.values())
            app_logger.info(
                f"Successfully fetched {len(pyzatt_users)} users with pyzatt."
            )

            adapted_users = []
            for u in pyzatt_users:
                adapted_user = PyzkUser(
                    uid=u.user_sn,
                    name=u.user_name,
                    privilege=u.admin_level,
                    password=u.user_password,
                    group_id=str(u.user_group),
                    user_id=u.user_id,
                    card=u.card_number,
                )
                adapted_users.append(adapted_user)

            return adapted_users

        except TimeoutError as e:
            app_logger.error(f"Timeout error in get_all_users: {e}")
            raise  # Re-raise the exception to be caught by the caller
        except Exception as e:
            app_logger.error(
                f"Error in get_all_users with pyzatt: {type(e).__name__}: {e}"
            )
            import traceback

            traceback.print_exc()
            raise
        finally:
            # Disable the alarm
            signal.alarm(0)
            if hasattr(z, "connected_flg") and z.connected_flg:
                z.disconnect()
                app_logger.info("pyzatt disconnection successful.")

    def get_attendance(self):
        """Get attendance records from device using pyzatt."""
        app_logger.info(
            f"get_attendance() called for device {self.device_id} using pyzatt"
        )
        z, ip, port = self._get_z_instance()
        try:
            # Add a small delay to let the device recover from previous session
            app_logger.info("Waiting 1 second before new connection...")
            time.sleep(1)

            app_logger.info(f"Connecting to {ip}:{port} with pyzatt...")
            z.connect_net(ip, dev_port=port)
            app_logger.info("pyzatt connection successful. Fetching attendance...")

            z.read_att_log()
            pyzatt_logs = z.att_log
            app_logger.info(
                f"Successfully fetched {len(pyzatt_logs)} attendance logs with pyzatt."
            )

            adapted_logs = []
            for log in pyzatt_logs:
                # The old pyzk Attendance object for compatibility
                adapted_log = PyzkAttendance(
                    user_id=log.user_id,
                    timestamp=log.att_time,
                    status=log.ver_state,
                    punch=log.ver_type,
                    uid=log.user_sn,
                )
                adapted_logs.append(adapted_log)

            # The rest of the function that saves to DB remains the same
            synced_count = 0
            duplicate_count = 0
            buffer: List[AttendanceLog] = []
            BATCH_SIZE = 500

            target_device_id = self.device_id
            device_info = config_manager.get_device(target_device_id)
            device_serial = device_info.get("serial_number") if device_info else None

            def flush_buffer():
                nonlocal synced_count, duplicate_count, buffer
                if not buffer:
                    return
                inserted, skipped = attendance_repo.bulk_insert_ignore(buffer)
                synced_count += inserted
                duplicate_count += skipped
                buffer.clear()

            for record in adapted_logs:
                try:
                    attendance_log_obj = AttendanceLog(
                        user_id=str(record.user_id),
                        timestamp=record.timestamp,
                        method=record.status,
                        action=record.punch,
                        device_id=target_device_id,
                        serial_number=device_serial,
                        raw_data={"uid": record.uid, "sync_source": "pyzatt_sync"},
                        sync_status=SyncStatus.PENDING,
                        is_synced=False,
                    )
                    buffer.append(attendance_log_obj)
                    if len(buffer) >= BATCH_SIZE:
                        flush_buffer()
                except Exception as record_error:
                    app_logger.error(
                        f"Error processing adapted attendance record {record}: {record_error}"
                    )
                    continue

            flush_buffer()

            app_logger.info(
                f"Smart sync completed with pyzatt: {synced_count} new records, {duplicate_count} duplicates skipped"
            )

            return {
                "records": adapted_logs,
                "sync_stats": {
                    "total_from_device": len(adapted_logs),
                    "new_records_saved": synced_count,
                    "duplicates_skipped": duplicate_count,
                },
            }

        except Exception as e:
            app_logger.error(
                f"Error in get_attendance with pyzatt: {type(e).__name__}: {e}"
            )
            import traceback

            traceback.print_exc()
            raise
        finally:
            if hasattr(z, "connected_flg") and z.connected_flg:
                z.disconnect()
                app_logger.info("pyzatt disconnection successful.")

    # All other methods are now explicitly not implemented for pull devices
    def _not_implemented(self):
        app_logger.warning("This function has not been refactored for pyzatt yet.")
        raise NotImplementedError(
            "This function is not available after pyzatt migration."
        )

    def create_user(self, *args, **kwargs):
        self._not_implemented()

    def delete_user(self, *args, **kwargs):
        self._not_implemented()

    def enroll_user(self, *args, **kwargs):
        self._not_implemented()

    def cancel_enroll_user(self, *args, **kwargs):
        self._not_implemented()

    def delete_user_template(self, *args, **kwargs):
        self._not_implemented()

    def get_user_template(self, *args, **kwargs):
        self._not_implemented()

    def get_device_info(self, *args, **kwargs):
        self._not_implemented()

    def save_device_info_to_config(self, *args, **kwargs):
        self._not_implemented()

    def sync_employee(self, device_id: str = None):
        """
        Sync all users from the active device from local DB to external API, and then
        update the local DB with data from the external API.
        """
        try:
            target_device_id = device_id or self.device_id
            if not target_device_id:
                active_device = config_manager.get_active_device()
                if not active_device:
                    raise ValueError("No active device configured.")
                target_device_id = active_device["id"]

            # Step 1: Sync all users from DB to external API
            all_users = user_repo.get_all(target_device_id)

            if not all_users:
                app_logger.info(
                    f"No users found for device {target_device_id} to sync."
                )
                return {
                    "success": True,
                    "message": f"No users found for device {target_device_id} to sync.",
                    "synced_users_count": 0,
                    "employees_count": 0,
                }

            device_config = config_manager.get_device(target_device_id)
            if not device_config:
                return {
                    "success": False,
                    "error": "No device configuration found",
                    "synced_users_count": 0,
                    "employees_count": 0,
                }

            device_serial = device_config.get(
                "serial_number", target_device_id or "unknown"
            )

            employees = []
            for user in all_users:
                employee_data = {
                    "userId": user.user_id,
                    "name": user.name,
                    "card": user.card or "",
                    "privilege": user.privilege,
                    "password": user.password or "",
                    "groupId": user.group_id,
                }
                employees.append(employee_data)

            app_logger.info(
                f"Step 1: Performing a full sync of {len(employees)} users to external API for device {device_serial}"
            )
            sync_result = external_api_service.sync_employees(employees, device_serial)

            if sync_result.get("status") != 200:
                error_msg = sync_result.get(
                    "message", "Unknown error from external API"
                )
                app_logger.warning(f"External API sync failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "synced_users_count": 0,
                    "employees_count": len(all_users),
                }

            for user in all_users:
                user_repo.mark_as_synced(user.id)

            app_logger.info(
                f"Step 1 successfully completed full sync of {len(all_users)} users to external API for device {target_device_id}"
            )

            # Step 2: Fetch data from external API and update local DB
            app_logger.info(
                f"Step 2: Fetching user details from external API for device {target_device_id}"
            )
            update_result = self.sync_all_users_from_external_api(
                device_id=target_device_id
            )

            return {
                "success": True,
                "message": f"Successfully synced {len(all_users)} users to external API and updated {update_result.get('updated_count', 0)} users from external API.",
                "synced_users_count": len(all_users),
                "employees_count": len(all_users),
                "update_result": update_result,
            }

        except Exception as e:
            app_logger.error(f"Error in sync_employee: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "synced_users_count": 0,
                "employees_count": 0,
            }

    def sync_all_users_from_external_api(self, device_id: str = None):
        """
        Fetch user details from external API and update local DB
        NOTE: This does NOT interact with device - only API and DB
        Works for both pull and push devices
        """
        try:
            target_device_id = device_id or self.device_id

            # Get all users from DB
            all_users = user_repo.get_all(target_device_id)

            if not all_users:
                app_logger.info(f"No users found in DB for device {target_device_id}")
                return {
                    "success": True,
                    "message": "No users to update",
                    "updated_count": 0,
                    "total_users": 0,
                }

            # Get device config for serial number
            device_config = (
                config_manager.get_device(target_device_id)
                if target_device_id
                else config_manager.get_active_device()
            )
            if not device_config:
                return {
                    "success": False,
                    "error": "No device configuration found",
                    "updated_count": 0,
                    "total_users": len(all_users),
                }

            device_serial = device_config.get(
                "serial_number", target_device_id or "unknown"
            )

            # Prepare user list for API query
            users_query = []
            for user in all_users:
                users_query.append({"id": int(user.user_id), "serial": device_serial})

            # Process users in batches of 100 to avoid timeout
            BATCH_SIZE = 100
            total_batches = (len(users_query) + BATCH_SIZE - 1) // BATCH_SIZE
            app_logger.info(
                f"Processing {len(users_query)} users in {total_batches} batch(es) of {BATCH_SIZE}"
            )

            all_employees_data = []
            for batch_index in range(0, len(users_query), BATCH_SIZE):
                batch = users_query[batch_index : batch_index + BATCH_SIZE]
                batch_num = (batch_index // BATCH_SIZE) + 1

                # Fetch employee details from external API
                api_response = external_api_service.get_employees_by_user_ids(batch)

                if api_response.get("status") != 200:
                    error_msg = api_response.get(
                        "message", "Unknown error from external API"
                    )
                    app_logger.warning(
                        f"Batch {batch_num}/{total_batches} failed: {error_msg}"
                    )
                    # Continue with next batch instead of returning error
                    continue

                # Extract employee data
                # API can return data as array directly or as object with employees key
                data = api_response.get("data", [])
                if isinstance(data, dict):
                    employees_data = data.get("employees", [])
                elif isinstance(data, list):
                    employees_data = data
                else:
                    employees_data = []

                if employees_data:
                    all_employees_data.extend(employees_data)

            if not all_employees_data:
                app_logger.info("No employee details returned from external API")
                return {
                    "success": True,
                    "message": "No employee details to update",
                    "updated_count": 0,
                    "total_users": len(all_users),
                }

            # Update local users with employee details
            updated_count = 0
            for employee in all_employees_data:
                # API returns time_clock_user_id as string
                user_id = str(employee.get("time_clock_user_id"))
                api_serial = employee.get("serial_number", "")

                # Find matching user in DB by user_id AND serial_number
                # This ensures we update the correct user when multiple devices have same user_id
                if api_serial:
                    # If API returns serial, match both user_id and serial
                    matching_user = next(
                        (
                            u
                            for u in all_users
                            if u.user_id == user_id and u.serial_number == api_serial
                        ),
                        None,
                    )
                else:
                    # If API doesn't return serial (empty string), fall back to user_id only
                    # But prefer users from the current device_serial
                    matching_user = next(
                        (
                            u
                            for u in all_users
                            if u.user_id == user_id and u.serial_number == device_serial
                        ),
                        None,
                    )
                    if not matching_user:
                        # Still not found? Try without serial restriction
                        matching_user = next(
                            (u for u in all_users if u.user_id == user_id), None
                        )

                if matching_user:
                    # Prepare update data
                    updates = {}

                    employee_id_value = employee.get("employee_id")

                    if employee_id_value:
                        updates["external_user_id"] = employee_id_value

                    if employee.get("employee_avatar"):
                        updates["avatar_url"] = employee["employee_avatar"]

                    if employee.get("employee_name"):
                        updates["full_name"] = employee["employee_name"]

                    if employee.get("employee_user_name"):
                        updates["employee_code"] = employee["employee_user_name"]

                    if employee.get("employee_role"):
                        updates["position"] = employee["employee_role"]

                    if employee.get("department"):
                        updates["department"] = employee["department"]

                    if employee.get("employee_object_text"):
                        updates["employee_object"] = employee["employee_object_text"]

                    if employee.get("notes"):
                        updates["notes"] = employee["notes"]

                    if employee.get("gender") is not None:
                        updates["gender"] = employee.get("gender")

                    if employee.get("hire_date"):
                        updates["hire_date"] = employee.get("hire_date")

                    # Only update if there's new data
                    if updates:
                        if user_repo.update(matching_user.id, updates):
                            updated_count += 1

                        else:
                            app_logger.warning(
                                f"[SYNC_USERS_API] Failed to update user {user_id} in DB"
                            )

            app_logger.info(
                f"Updated {updated_count}/{len(all_users)} users with employee details from external API"
            )

            return {
                "success": True,
                "message": f"Updated {updated_count} users with employee details",
                "updated_count": updated_count,
                "total_users": len(all_users),
            }

        except Exception as e:
            app_logger.error(
                f"Error in sync_all_users_from_external_api: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "updated_count": 0,
                "total_users": 0,
            }

    def _fetch_employee_details(self, *args, **kwargs):
        """
        DEPRECATED: Use sync_all_users_from_external_api() instead
        This method is kept for backward compatibility
        """
        app_logger.warning(
            "_fetch_employee_details() is deprecated, use sync_all_users_from_external_api()"
        )
        return self.sync_all_users_from_external_api(*args, **kwargs)


def get_zk_service(device_id: str = None):
    return ZkService(device_id)

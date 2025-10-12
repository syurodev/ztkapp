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
from typing import List, Type

from dotenv import load_dotenv
from zk import ZK, const

from app.shared.logger import app_logger
from app.device.mock import ZKMock
from app.device.connection_manager import connection_manager
from app.config.config_manager import config_manager
from app.repositories import user_repo, attendance_repo
from app.models import AttendanceLog, SyncStatus

load_dotenv()


class ZkService:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def _check_pull_device(self, device_id: str) -> None:
        """Check if device is pull type, raise ValueError if not"""
        from app.utils.device_helpers import require_pull_device

        require_pull_device(device_id)

    def create_user(self, user_id, user_data, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(
            f"create_user() called with user_id: {user_id}, data: {user_data}, device_id: {target_device_id}"
        )

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            app_logger.info(f"Got connection, is_connect: {zk_instance.is_connect}")

            app_logger.info("Disabling device...")
            zk_instance.disable_device()
            app_logger.info("Device disabled")

            app_logger.info("Setting user...")
            zk_instance.set_user(
                uid=user_id,
                name=user_data.get("name"),
                privilege=user_data.get("privilege", const.USER_DEFAULT),
                password=user_data.get("password", ""),
                group_id=user_data.get("group_id", 0),
                user_id=str(user_id),
                card=user_data.get("card", 0),
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

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        device_was_disabled = False
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
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
                app_logger.warning(
                    f"TCP error after device disable, resetting connection for device {target_device_id}"
                )
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

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.delete_user(uid=user_id, user_id=str(user_id))
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def enroll_user(self, user_id, temp_id, device_id: str = None):
        target_device_id = device_id or self.device_id

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.enroll_user(uid=user_id, temp_id=temp_id, user_id=str(user_id))
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def cancel_enroll_user(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
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
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            zk_instance.delete_user_template(
                uid=user_id, temp_id=temp_id, user_id=str(user_id)
            )
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_user_template(self, user_id, temp_id, device_id: str = None):
        target_device_id = device_id or self.device_id
        zk_instance = None
        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            zk_instance.disable_device()
            template = zk_instance.get_user_template(
                uid=user_id, temp_id=temp_id, user_id=str(user_id)
            )
            return template
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_attendance(self, device_id: str = None):
        """Get attendance records from device (smart sync with duplicate prevention)"""
        target_device_id = device_id or self.device_id
        app_logger.info(f"get_attendance() called for device {target_device_id}")

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        synced_count = 0
        duplicate_count = 0
        buffer: List[AttendanceLog] = []
        BATCH_SIZE = 500

        def flush_buffer():
            nonlocal synced_count, duplicate_count, buffer
            if not buffer:
                return
            inserted, skipped = attendance_repo.bulk_insert_ignore(buffer)
            synced_count += inserted
            duplicate_count += skipped
            buffer.clear()

        try:
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()

            # Get device info for serial_number
            device_info = (
                config_manager.get_device(target_device_id)
                if target_device_id
                else config_manager.get_active_device()
            )
            device_serial = None
            if device_info:
                device_serial = device_info.get("serial_number")
                if not device_serial:
                    # Fallback to device_info if serial_number column is empty
                    device_info_data = device_info.get("device_info", {})
                    device_serial = (
                        device_info_data.get("serial_number")
                        if device_info_data
                        else None
                    )

            zk_instance.disable_device()
            app_logger.info("Getting attendance records from device...")
            attendance_records = zk_instance.get_attendance()
            app_logger.info(
                f"Retrieved {len(attendance_records)} attendance records from device"
            )

            # Process each record with smart sync logic
            for record in attendance_records:
                try:
                    # Create AttendanceLog object with device timestamp
                    attendance_log = AttendanceLog(
                        user_id=str(record.user_id),
                        timestamp=record.timestamp,  # This is already device timestamp from pyzk
                        method=record.status,  # 1: fingerprint, 4: card, etc.
                        action=record.punch,  # 0: checkin, 1: checkout, etc.
                        device_id=target_device_id,
                        serial_number=device_serial,
                        raw_data={
                            "uid": record.uid if hasattr(record, "uid") else None,
                            "original_status": record.status,
                            "original_punch": record.punch,
                            "device_timestamp": record.timestamp.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "sync_source": "manual_device_sync",
                        },
                        sync_status=SyncStatus.PENDING,  # Default to pending
                        is_synced=False,  # kept for backward compatibility
                    )

                    buffer.append(attendance_log)

                    if len(buffer) >= BATCH_SIZE:
                        flush_buffer()
                        app_logger.debug(
                            f"Buffered batch flushed for device {target_device_id}: {synced_count} total new, {duplicate_count} duplicates so far"
                        )

                except Exception as record_error:
                    app_logger.error(
                        f"Error processing attendance record {record}: {record_error}"
                    )
                    continue

            # Flush any remaining buffered records
            flush_buffer()

            app_logger.info(
                f"Smart sync completed: {synced_count} new records, {duplicate_count} duplicates skipped"
            )

            # Return original records for backward compatibility, but add sync stats
            return {
                "records": attendance_records,
                "sync_stats": {
                    "total_from_device": len(attendance_records),
                    "new_records_saved": synced_count,
                    "duplicates_skipped": duplicate_count,
                },
            }

        except Exception as e:
            app_logger.error(f"Error in get_attendance: {type(e).__name__}: {e}")
            raise
        finally:
            if zk_instance:
                zk_instance.enable_device()

    def get_device_info(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"get_device_info() called for device {target_device_id}")

        # Check device type - only pull devices support this operation
        if target_device_id:
            self._check_pull_device(target_device_id)

        zk_instance = None
        device_was_disabled = False
        try:
            app_logger.info(f"Getting connection for device {target_device_id}...")
            if target_device_id:
                zk_instance = connection_manager.ensure_device_connection(
                    target_device_id
                )
            else:
                zk_instance = connection_manager.ensure_connection()
            app_logger.info(f"Got connection, is_connect: {zk_instance.is_connect}")

            app_logger.info("Disabling device...")
            zk_instance.disable_device()
            device_was_disabled = True
            app_logger.info("Device disabled")

            app_logger.info("Getting device information...")
            device_info = {
                "current_time": zk_instance.get_time().strftime("%Y-%m-%d %H:%M:%S")
                if zk_instance.get_time()
                else None,
                "firmware_version": zk_instance.get_firmware_version(),
                "device_name": zk_instance.get_device_name(),
                "serial_number": zk_instance.get_serialnumber(),
                "mac_address": zk_instance.get_mac(),
                "face_version": zk_instance.get_face_version(),
                "fp_version": zk_instance.get_fp_version(),
                "platform": zk_instance.get_platform(),
            }

            # Get network information
            try:
                network_info = zk_instance.get_network_params()
                device_info["network"] = {
                    "ip": network_info.get("ip"),
                    "netmask": network_info.get("mask"),
                    "gateway": network_info.get("gateway"),
                }
            except Exception as network_error:
                app_logger.warning(f"Could not get network info: {network_error}")
                device_info["network"] = None

            app_logger.info(f"Retrieved device info: {device_info}")
            return device_info

        except Exception as e:
            app_logger.error(f"Error in get_device_info: {type(e).__name__}: {e}")
            if device_was_disabled and "TCP" in str(e):
                app_logger.warning(
                    f"TCP error after device disable, resetting connection for device {target_device_id}"
                )
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
        app_logger.info(
            f"save_device_info_to_config() called for device {target_device_id}"
        )
        try:
            device_info = self.get_device_info(target_device_id)

            # Save device info to config
            config_manager.save_device_info(device_info, target_device_id)
            app_logger.info(
                f"Device info saved to config successfully for device {target_device_id}"
            )

            return device_info
        except Exception as e:
            app_logger.error(
                f"Error in save_device_info_to_config for device {target_device_id}: {type(e).__name__}: {e}"
            )
            raise

    def _fetch_employee_details(self, users: list, external_api_domain: str) -> dict:
        """
        Fetch employee details from external API after sync

        Args:
            users: List of User objects or dict with user_id and serial_number
            external_api_domain: External API base URL

        Returns:
            Dict mapping user_id -> {employee_id, employee_avatar}
        """
        try:
            api_url = external_api_domain + "/time-clock-employees/get-by-user-ids"
            api_key = config_manager.get_external_api_key()

            if not api_key:
                app_logger.warning(
                    "EXTERNAL_API_KEY not configured, skipping employee details fetch"
                )
                return {}

            # Build users array with id and serial_number
            users_array = []
            for user in users:
                if hasattr(user, "user_id"):
                    # User object from database
                    users_array.append(
                        {"id": user.user_id, "serial_number": user.serial_number or ""}
                    )
                elif isinstance(user, dict):
                    # Dict with user_id and serial_number
                    users_array.append(
                        {
                            "id": user.get("user_id", ""),
                            "serial_number": user.get("serial_number", ""),
                        }
                    )
                else:
                    # Fallback: just user_id string
                    users_array.append({"id": str(user), "serial_number": ""})

            request_body = {"users": users_array}
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "ProjectId": "1055",
            }

            app_logger.info(
                f"Fetching employee details for {len(users_array)} users from external API"
            )
            app_logger.debug(f"Request body: {request_body}")

            response = requests.post(
                api_url, json=request_body, headers=headers, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # Parse response: BaseResponse<List<TimeClockEmployeeInfoResponse>>
            if data.get("status") != 200:
                app_logger.warning(
                    f"Failed to fetch employee details: {data.get('message')}"
                )
                return {}

            employee_details = data.get("data", [])
            app_logger.info(
                f"Received {len(employee_details)} employee details from external API"
            )

            # Map (user_id, serial_number) -> details for unique identification
            result = {}
            for employee in employee_details:
                time_clock_user_id = employee.get("time_clock_user_id")
                serial_number = employee.get("serial_number")

                if time_clock_user_id and serial_number:
                    result[(time_clock_user_id, serial_number)] = {
                        "employee_id": employee.get("employee_id"),
                        "employee_name": employee.get("employee_name"),
                        "employee_avatar": employee.get("employee_avatar"),
                        # Map theo response API mới:
                        "full_name": employee.get("employee_name") or "",
                        "employee_code": employee.get("employee_user_name") or "",
                        "position": employee.get("employee_role") or "",
                        "employee_object": employee.get("employee_object_text") or "",
                        "department": "",  # Để trống theo yêu cầu
                        "notes": "",  # API không trả về notes
                    }

            app_logger.info(f"Successfully mapped details for {len(result)} employees")
            return result

        except requests.exceptions.RequestException as e:
            app_logger.error(f"HTTP error fetching employee details: {e}")
            return {}
        except Exception as e:
            app_logger.error(
                f"Error fetching employee details: {type(e).__name__}: {e}"
            )
            return {}

    def sync_employee(self, device_id: str = None):
        target_device_id = device_id or self.device_id
        app_logger.info(f"sync_employee() called for device {target_device_id}")

        # Note: This function works with both pull and push devices
        # It only syncs users from DB to external API (no device connection needed)
        # Push devices populate DB via push protocol, pull devices via manual sync

        try:
            # Get active device info
            if target_device_id:
                device = config_manager.get_device(target_device_id)
            else:
                device = config_manager.get_active_device()
                target_device_id = device["id"] if device else None

            if not device:
                raise ValueError("No device found for sync")

            # Get only unsynced users for this device
            db_users = user_repo.get_unsynced_users(device_id=target_device_id)
            app_logger.info(
                f"Retrieved {len(db_users)} unsynced users from database for sync to external API"
            )
            if not db_users:
                return {
                    "success": True,
                    "employees_count": 0,
                    "message": "No unsynced users found",
                }

            # Get external API URL from config (new dynamic approach)
            external_api_domain = config_manager.get_external_api_url()

            if not external_api_domain:
                raise ValueError("API_GATEWAY_DOMAIN not configured")

            external_api_url = external_api_domain + "/time-clock-employees/sync"

            # Get device info for serial number
            device_info = device.get("device_info", {})
            serial_number = device_info.get(
                "serial_number", target_device_id or "unknown"
            )

            # Format employees data from database users
            employees = []
            user_ids_to_sync = []  # Track user IDs that will be synced

            for user in db_users:
                employee = {
                    "userId": user.user_id,
                    "name": user.name,
                    "groupId": user.group_id,
                }
                employees.append(employee)
                user_ids_to_sync.append(
                    user.id
                )  # Store the database ID for later update

            # Prepare sync data
            sync_data = {"timestamp": int(time.time()), "employees": employees}

            app_logger.info(sync_data)

            # Get API key from config
            api_key = config_manager.get_external_api_key()
            if not api_key:
                app_logger.warning(
                    "EXTERNAL_API_KEY not configured, skipping employee sync"
                )
                return {"success": False, "message": "EXTERNAL_API_KEY not configured"}

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "x-device-sync": serial_number,
                "ProjectId": "1055",
            }

            # Make API request
            response = requests.post(
                external_api_url, json=sync_data, headers=headers, timeout=30
            )

            data = response.json()

            if data.get("status") != 200:
                return {"success": False, "message": data.get("message")}

            response.raise_for_status()

            # Sync successful - now try to fetch employee details (best effort)
            # IMPORTANT: Users will be marked as synced regardless of detail fetch success
            from datetime import datetime

            app_logger.info(
                "Sync successful, attempting to fetch employee details from external API..."
            )
            employee_details = self._fetch_employee_details(
                db_users, external_api_domain
            )

            # Log detail fetch result
            if employee_details:
                app_logger.info(
                    f"Successfully fetched details for {len(employee_details)} employees"
                )
            else:
                app_logger.warning(
                    "Failed to fetch employee details, but sync will continue (users will still be marked as synced)"
                )

            # Update users with sync status (and details if available)
            synced_count = 0
            updated_with_details_count = 0

            for user in db_users:
                try:
                    # Always mark as synced since main sync was successful
                    updates = {"is_synced": True, "synced_at": datetime.now()}

                    # Add employee details if available (optional enhancement)
                    lookup_key = (user.user_id, user.serial_number)
                    if employee_details and lookup_key in employee_details:
                        details = employee_details[lookup_key]
                        updates["external_user_id"] = details.get("employee_id")
                        updates["avatar_url"] = details.get("employee_avatar")

                        # Add new fields with safe defaults
                        updates["full_name"] = details.get("full_name") or ""
                        updates["employee_code"] = details.get("employee_code") or ""
                        updates["position"] = details.get("position") or ""
                        updates["employee_object"] = (
                            details.get("employee_object") or ""
                        )
                        updates["department"] = details.get("department") or ""
                        updates["notes"] = details.get("notes") or ""

                        app_logger.info(
                            f"User {user.user_id} ({user.name}) on device {user.serial_number}: marked as synced + mapped to employee_id={details.get('employee_id')}, "
                            f"full_name={details.get('full_name')}, code={details.get('employee_code')}, "
                            f"position={details.get('position')}, object={details.get('employee_object')}"
                        )
                        updated_with_details_count += 1
                    else:
                        app_logger.debug(
                            f"User {user.user_id} ({user.name}): marked as synced (no employee details)"
                        )

                    user_repo.update(user.id, updates)
                    synced_count += 1

                except Exception as update_error:
                    app_logger.warning(
                        f"Failed to update user {user.id}: {update_error}"
                    )

            app_logger.info(
                f"Successfully synced {len(employees)} employees to external API, "
                f"updated {synced_count} users in database ({updated_with_details_count} with employee details)"
            )

            return {
                "success": True,
                "employees_count": len(employees),
                "synced_users_count": synced_count,
                "updated_with_details_count": updated_with_details_count,
                "timestamp": sync_data["timestamp"],
                "response_status": response.status_code,
                "external_api_response": data,
            }

        except requests.exceptions.RequestException as e:
            app_logger.error(f"HTTP error in sync_employee: {e}")
            raise
        except Exception as e:
            app_logger.error(f"Error in sync_employee: {type(e).__name__}: {e}")
            raise

    def sync_all_users_from_external_api(self):
        """
        Sync all users from external API to update employee details (avatar, external_user_id)
        This is called periodically by scheduler to keep user data up-to-date

        Returns:
            Dict with sync results
        """
        try:
            app_logger.info("Starting periodic user sync from external API")

            # Get external API domain
            external_api_domain = config_manager.get_external_api_domain()
            if not external_api_domain:
                app_logger.warning(
                    "API_GATEWAY_DOMAIN not configured, skipping periodic user sync"
                )
                return {
                    "success": False,
                    "message": "API_GATEWAY_DOMAIN not configured",
                }

            # Get all users from database
            all_users = user_repo.get_all()
            if not all_users:
                app_logger.info(
                    "No users found in database, skipping periodic user sync"
                )
                return {
                    "success": True,
                    "message": "No users to sync",
                    "updated_count": 0,
                }

            # Fetch employee details from external API
            app_logger.info(
                f"Fetching employee details for {len(all_users)} users from external API"
            )
            employee_details = self._fetch_employee_details(
                all_users, external_api_domain
            )

            if not employee_details:
                app_logger.warning("No employee details received from external API")
                return {
                    "success": True,
                    "message": "No employee details received",
                    "updated_count": 0,
                }

            # Update users with employee details
            updated_count = 0
            for user in all_users:
                lookup_key = (user.user_id, user.serial_number)
                if lookup_key in employee_details:
                    details = employee_details[lookup_key]
                    updates = {
                        'external_user_id': details.get('employee_id'),
                        'avatar_url': details.get('employee_avatar')
                    }

                    try:
                        user_repo.update(user.id, updates)
                        updated_count += 1
                        app_logger.debug(
                            f"Updated user {user.user_id} ({user.name}) on device {user.serial_number}: "
                            f"employee_id={details.get('employee_id')}, "
                            f"avatar={'present' if details.get('employee_avatar') else 'none'}"
                        )

            app_logger.info(
                f"Periodic user sync completed: updated {updated_count} users out of {len(all_users)} total users"
            )

            return {
                "success": True,
                "total_users": len(all_users),
                "updated_count": updated_count,
                "employee_details_count": len(employee_details),
            }

        except Exception as e:
            app_logger.error(
                f"Error in sync_all_users_from_external_api: {type(e).__name__}: {e}"
            )
            return {"success": False, "error": str(e)}


def get_zk_service(device_id: str = None):
    if device_id:
        # Get specific device configuration
        device = config_manager.get_device(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        # Configure the connection manager for this device
        device_config = {
            "ip": device.get("ip"),
            "port": device.get("port"),
            "password": device.get("password"),
            "timeout": device.get("timeout"),
            "force_udp": device.get("force_udp"),
            "verbose": bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
            "retry_count": device.get("retry_count"),
            "retry_delay": device.get("retry_delay"),
            "ping_interval": device.get("ping_interval"),
        }

        connection_manager.configure_device(device_id, device_config)
        return ZkService(device_id)

    else:
        # Legacy mode - use active device or fallback to old config
        active_device = config_manager.get_active_device()

        if active_device:
            return get_zk_service(active_device["id"])
        else:
            # Legacy fallback
            config = config_manager.get_config()
            connection_config = {
                "ip": config.get("DEVICE_IP"),
                "port": int(config.get("DEVICE_PORT", 4370)),
                "password": int(config.get("DEVICE_PASSWORD", 0)),
                "verbose": bool(strtobool(os.getenv("FLASK_DEBUG", "false"))),
                "timeout": config.get("CONNECTION_TIMEOUT", 10),
                "force_udp": config.get("CONNECTION_FORCE_UDP", False),
                "retry_count": config.get("CONNECTION_RETRY_COUNT", 3),
                "retry_delay": config.get("CONNECTION_RETRY_DELAY", 2),
                "ping_interval": config.get("CONNECTION_PING_INTERVAL", 30),
            }

            connection_manager.configure(connection_config)
            return ZkService()

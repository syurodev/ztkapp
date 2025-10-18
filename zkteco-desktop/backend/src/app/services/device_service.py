import os
import json
import time
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

    def _normalize_user_id(self, user_id) -> Optional[str]:
        """Chuẩn hoá user_id về chuỗi số để đồng bộ giữa các luồng."""
        if user_id is None:
            return None
        try:
            return str(int(str(user_id).strip()))
        except (TypeError, ValueError):
            return None

    def _check_pull_device(self, device_id: str) -> None:
        """Check if device is pull type, raise ValueError if not"""
        from app.utils.device_helpers import require_pull_device

        require_pull_device(device_id)

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

    def get_all_users(self):
        """Get all users from device using pyzatt."""
        app_logger.info(
            f"get_all_users() called for device {self.device_id} using pyzatt"
        )
        z, ip, port = self._get_z_instance()
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

        except Exception as e:
            app_logger.error(
                f"Error in get_all_users with pyzatt: {type(e).__name__}: {e}"
            )
            import traceback

            traceback.print_exc()
            raise
        finally:
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

            # Build users array với user_id duy nhất (ưu tiên serial_number nếu có)
            users_map: Dict[str, Dict[str, Any]] = {}
            for user in users:
                raw_user_id = None
                serial_value = ""

                if hasattr(user, "user_id"):
                    # User object from database
                    raw_user_id = user.user_id
                    serial_value = user.serial_number or ""
                elif isinstance(user, dict):
                    # Dict with user_id and serial_number
                    raw_user_id = user.get("user_id", "") or ""
                    serial_value = user.get("serial_number", "") or ""
                else:
                    # Fallback: just user_id string
                    raw_user_id = user

                normalized_id = self._normalize_user_id(raw_user_id)
                if not normalized_id:
                    continue

                existing_entry = users_map.get(normalized_id)
                if not existing_entry or (
                    not existing_entry.get("serial_number") and serial_value
                ):
                    users_map[normalized_id] = {
                        "id": int(normalized_id),
                        "serial_number": serial_value or "",
                    }

            users_array = list(users_map.values())

            app_logger.info(
                f"Fetching employee details for {len(users_array)} users from external API"
            )

            data = external_api_service.get_employees_by_user_ids(users_array)

    def get_device_info(self, *args, **kwargs):
        self._not_implemented()

    def save_device_info_to_config(self, *args, **kwargs):
        self._not_implemented()

            # Map user_id -> details (đã chuẩn hoá)
            result = {}
            for employee in employee_details:
                normalized_id = self._normalize_user_id(
                    employee.get("time_clock_user_id")
                )

                if normalized_id:
                    result[normalized_id] = {
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

    def sync_all_users_from_external_api(self, *args, **kwargs):
        self._not_implemented()

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

            # Get device info for serial number
            device_info = device.get("device_info", {})
            serial_number = device_info.get(
                "serial_number", target_device_id or "unknown"
            )

            # Format employees data from database users
            employees = []
            user_ids_to_sync = []  # Track user IDs that will be synced

            for user in db_users:
                normalized_id = self._normalize_user_id(user.user_id)
                user_id_payload = int(normalized_id) if normalized_id else user.user_id
                employee = {
                    "userId": user_id_payload,
                    "name": user.name,
                    "groupId": user.group_id,
                }
                employees.append(employee)
                user_ids_to_sync.append(
                    user.id
                )  # Store the database ID for later update

            # Get API key from config
            if not config_manager.get_external_api_key():
                app_logger.warning(
                    "EXTERNAL_API_KEY not configured, skipping employee sync"
                )
                return {"success": False, "message": "EXTERNAL_API_KEY not configured"}

            # Make API request
            data = external_api_service.sync_employees(employees, serial_number)

            if data.get("status") != 200:
                return {"success": False, "message": data.get("message")}

            # Sync successful - now try to fetch employee details (best effort)
            # IMPORTANT: Users will be marked as synced regardless of detail fetch success
            from datetime import datetime

            app_logger.info(
                "Sync successful, attempting to fetch employee details from external API..."
            )
            employee_details = self._fetch_employee_details(db_users)

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

                    # Add employee details nếu có (chỉ theo user_id đã chuẩn hoá)
                    lookup_key = self._normalize_user_id(user.user_id)
                    if (
                        lookup_key
                        and employee_details
                        and lookup_key in employee_details
                    ):
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
                "timestamp": int(time.time()),
                "response_status": 200,
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
            employee_details = self._fetch_employee_details(all_users)

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
                lookup_key = self._normalize_user_id(user.user_id)
                if lookup_key and lookup_key in employee_details:
                    details = employee_details[lookup_key]
                    updates = {
                        "external_user_id": details.get("employee_id"),
                        "avatar_url": details.get("employee_avatar"),
                        "full_name": details.get("full_name") or "",
                        "employee_code": details.get("employee_code") or "",
                        "position": details.get("position") or "",
                        "employee_object": details.get("employee_object") or "",
                        "department": details.get("department") or "",
                        "notes": details.get("notes") or "",
                    }

                    try:
                        user_repo.update(user.id, updates)
                        updated_count += 1
                        app_logger.debug(
                            f"Updated user {user.user_id} ({user.name}) on device {user.serial_number}: "
                            f"employee_id={details.get('employee_id')}, "
                            f"avatar={'present' if details.get('employee_avatar') else 'none'}, "
                            f"full_name={details.get('full_name')}, "
                            f"code={details.get('employee_code')}, "
                            f"position={details.get('position')}, "
                            f"object={details.get('employee_object')}"
                        )
                    except Exception as update_error:
                        app_logger.warning(
                            f"Failed to update user {user.user_id} ({user.name}) on device {user.serial_number}: {update_error}"
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
    return ZkService(device_id)

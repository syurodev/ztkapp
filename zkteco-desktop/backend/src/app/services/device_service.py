import os
import json
import time  # Thêm import này
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

    def get_user_template(self, *args, **kwargs):
        self._not_implemented()

    def get_device_info(self, *args, **kwargs):
        self._not_implemented()

    def save_device_info_to_config(self, *args, **kwargs):
        self._not_implemented()

    def sync_employee(self, *args, **kwargs):
        self._not_implemented()

    def sync_all_users_from_external_api(self, *args, **kwargs):
        self._not_implemented()

    def _fetch_employee_details(self, *args, **kwargs):
        self._not_implemented()


def get_zk_service(device_id: str = None):
    return ZkService(device_id)

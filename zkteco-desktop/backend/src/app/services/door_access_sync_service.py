"""
Door Access Sync Service
Handles synchronization of door access logs to external API
"""

import time
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from app.shared.logger import app_logger
from app.repositories.door_access_repository import DoorAccessRepository
from app.repositories.setting_repository import setting_repo
from app.services.external_api_service import external_api_service
from app.config.config_manager import config_manager


class DoorAccessSyncService:
    """Service for syncing door access logs to external API"""

    def __init__(self):
        self.logger = app_logger
        self.door_access_repo = DoorAccessRepository()

    def sync_daily_door_access(
        self, target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync daily door access logs to external API.

        Groups door access logs by (user_id, door_id, date) and sends aggregated data.
        If API returns error, the entire batch fails (no partial success).

        Args:
            target_date: Date in YYYY-MM-DD format (default: today)

        Returns:
            Dict with sync results:
            {
                'success': bool,
                'date': str,
                'count': int,  # Number of aggregated records
                'synced_logs': int,  # Number of individual logs synced
                'message': str (optional),
                'error': str (optional)
            }
        """
        try:
            # Determine target date
            if target_date:
                sync_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            else:
                sync_date = date.today()

            sync_date_str = str(sync_date)

            self.logger.info(f"Starting door access sync for date: {sync_date_str}")

            # Get aggregated door access data
            aggregated_data = self.door_access_repo.get_aggregated_door_access(
                sync_date_str
            )

            if not aggregated_data:
                self.logger.info(
                    f"No unsynced door access logs found for {sync_date_str}"
                )
                return {
                    "success": True,
                    "date": sync_date_str,
                    "count": 0,
                    "synced_logs": 0,
                    "message": "No unsynced door access logs found",
                }

            # Filter out records without external_user_id
            valid_data = []
            all_log_ids = []

            for record in aggregated_data:
                all_log_ids.extend(record["log_ids"])

                # Skip if user doesn't have external_user_id
                if not record["external_user_id"]:
                    self.logger.warning(
                        f"Skipping door access for user_id {record['user_id']} "
                        f"(door {record['door_id']}) - no external_user_id"
                    )
                    continue

                valid_data.append(record)

            if not valid_data:
                self.logger.warning(
                    f"No valid door access records with external_user_id for {sync_date_str}"
                )
                return {
                    "success": True,
                    "date": sync_date_str,
                    "count": 0,
                    "synced_logs": 0,
                    "message": "No valid records with external_user_id",
                }

            # Get device serial number
            active_device = config_manager.get_active_device()
            if not active_device:
                return {
                    "success": False,
                    "error": "No active device configured",
                    "date": sync_date_str,
                    "count": 0,
                    "synced_logs": 0,
                }

            device_serial = active_device.get(
                "serial_number", active_device.get("id", "unknown")
            )

            # Get branch_id from settings
            branch_id_setting = setting_repo.get("ACTIVE_BRANCH_ID")
            branch_id = (
                branch_id_setting.value
                if (branch_id_setting and branch_id_setting.value)
                else "0"
            )

            # Build payload for external API
            door_access_data = []
            for record in valid_data:
                # Timestamps are already in HH:MM:SS format from repository
                # No need to parse and reformat
                door_access_data.append(
                    {
                        "user_id": str(record["user_id"]),
                        "door_id": str(record["door_id"]),
                        "date": sync_date_str,
                        "external_user_id": str(record["external_user_id"]),
                        "data": record["timestamps"],  # Already HH:MM:SS format
                    }
                )

            payload = {
                "timestamp": int(time.time()),
                "date": sync_date_str,
                "device_serial": device_serial,
                "branch_id": branch_id,
                "door_access_data": door_access_data,
            }

            self.logger.info(
                f"Sending {len(door_access_data)} aggregated door access records "
                f"({len(all_log_ids)} individual logs) to external API"
            )

            # Send to external API
            try:
                api_response = external_api_service.sync_door_access_data(
                    payload, device_serial
                )

                # Check response status
                status = api_response.get("status")

                if status not in (200, 201):
                    error_message = api_response.get(
                        "message", f"API returned status {status}"
                    )
                    self.logger.error(
                        f"External API error for door access sync: {error_message}"
                    )
                    return {
                        "success": False,
                        "error": error_message,
                        "date": sync_date_str,
                        "count": len(door_access_data),
                        "synced_logs": 0,
                        "response": api_response,
                    }

                # Success - mark all logs as synced
                synced_count = self.door_access_repo.mark_logs_as_synced(all_log_ids)

                self.logger.info(
                    f"Door access sync completed: {len(door_access_data)} aggregated records, "
                    f"{synced_count} individual logs marked as synced"
                )

                return {
                    "success": True,
                    "date": sync_date_str,
                    "count": len(door_access_data),
                    "synced_logs": synced_count,
                    "message": f"Successfully synced {synced_count} door access logs",
                    "response": api_response,
                }

            except Exception as api_error:
                self.logger.error(
                    f"Error calling external API for door access sync: {api_error}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": str(api_error),
                    "date": sync_date_str,
                    "count": len(door_access_data),
                    "synced_logs": 0,
                }

        except Exception as e:
            self.logger.error(
                f"Error in sync_daily_door_access: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "date": str(target_date or date.today()),
                "count": 0,
                "synced_logs": 0,
            }


# Singleton instance
door_access_sync_service = DoorAccessSyncService()

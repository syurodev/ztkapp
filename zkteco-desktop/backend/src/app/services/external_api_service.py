import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.shared.logger import app_logger
from app.config.config_manager import config_manager
from app.repositories import setting_repo


class ExternalAPIService:
    def __init__(self):
        self.base_url = config_manager.get_external_api_url()
        self.api_key = config_manager.get_external_api_key()
        self.project_id = "1055"

    def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Dict = None,
        serial_number: Optional[str] = None,
    ) -> Dict:
        if not self.base_url or not self.api_key:
            app_logger.error("External API URL or API Key is not configured.")
            raise ValueError(
                "API_GATEWAY_DOMAIN and EXTERNAL_API_KEY must be configured."
            )

        url = self.base_url + endpoint

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "ProjectId": self.project_id,
        }
        if serial_number:
            headers["x-device-sync"] = serial_number

        # Add branch ID to all requests except for the branches list itself
        # If no branch ID is configured, default to "0"
        if endpoint != "/time-clock-employees/branchs":
            branch_id_setting = setting_repo.get("ACTIVE_BRANCH_ID")
            branch_id = (
                branch_id_setting.value
                if (branch_id_setting and branch_id_setting.value)
                else "0"
            )
            headers["x-branch-id"] = branch_id

        redacted_headers = {
            key: (
                "***"
                if key.lower() in {"x-api-key", "authorization", "x-branch-id"}
                else value
            )
            for key, value in headers.items()
        }

        app_logger.info(
            f"External API Request -> Method: {method}, URL: {url}, Headers: {redacted_headers}"
        )

        payload_preview = None
        if payload is not None:
            try:
                payload_str = json.dumps(payload, default=str)
                if len(payload_str) > 2000:
                    payload_preview = payload_str[:2000] + "...[truncated]"
                else:
                    payload_preview = payload_str
            except (TypeError, ValueError):
                payload_preview = str(payload)

        if payload_preview is not None:
            app_logger.debug(f"External API Payload -> {payload_preview}")

        try:
            response = requests.request(
                method, url, json=payload, headers=headers, timeout=30
            )

            response_preview = response.text.strip()
            if len(response_preview) > 1000:
                response_preview = response_preview[:1000] + "...[truncated]"

            response.raise_for_status()

            app_logger.debug(
                "External API Response <- Status %s: %s",
                response.status_code,
                response_preview,
            )

            data = response.json()
            if data.get("status") != 200:
                app_logger.warning(
                    f"External API returned non-200 status: {data.get('message')}"
                )

            return data

        except requests.exceptions.RequestException as e:
            app_logger.error(f"HTTP error during external API call: {e}")
            raise

    def get_employees_by_user_ids(self, users: List[Dict[str, str]]) -> Dict:
        """
        Fetches employee details from the external API based on user IDs and serial numbers.
        """
        endpoint = "/time-clock-employees/get-by-user-ids"
        payload = {"users": users}
        return self._make_request("POST", endpoint, payload)

    def sync_employees(
        self, employees: List[Dict[str, Any]], serial_number: str
    ) -> Dict:
        """
        Syncs a list of employees to the external API.
        """
        endpoint = "/time-clock-employees/sync"
        payload = {"timestamp": int(time.time()), "employees": employees}
        return self._make_request(
            "POST", endpoint, payload, serial_number=serial_number
        )

    def sync_checkin_data(
        self, sync_payload: Dict[str, Any], serial_number: str
    ) -> Dict:
        """
        Syncs attendance/check-in data to the external API.
        """
        endpoint = "/time-clock-employees/sync-checkin-data"
        return self._make_request(
            "POST", endpoint, sync_payload, serial_number=serial_number
        )

    def sync_device(self, sync_data: Dict, serial_number: Optional[str]) -> Dict:
        """
        Syncs device information to the external API.
        """
        endpoint = "/time-clock-employees/sync-device"
        return self._make_request(
            "POST", endpoint, sync_data, serial_number=serial_number
        )

    def get_branches(self) -> Dict:
        """
        Fetches a list of branches from the external API.
        """
        endpoint = "/time-clock-employees/branches"
        return self._make_request("GET", endpoint)

    def sync_door_access_data(
        self, sync_payload: Dict[str, Any], serial_number: str
    ) -> Dict:
        """
        Syncs door access data to the external API.

        Args:
            sync_payload: Payload containing door access data
            serial_number: Device serial number

        Returns:
            API response dict
        """
        endpoint = "/time-clock-employees/sync-door-access-logs"
        return self._make_request(
            "POST", endpoint, sync_payload, serial_number=serial_number
        )

    def sync_doors(self, doors: List[Dict[str, Any]]) -> Dict:
        """
        Syncs a list of doors to the external API.
        """
        endpoint = "/time-clock-employees/doors"
        return self._make_request("POST", endpoint, doors)

    def sync_attendance_logs(
        self,
        attendance_logs: List[Any],
        serial_number: Optional[str] = None,
    ) -> Dict:
        """
        Sends raw attendance log records to the external API.

        Each record is normalized to the contract expected by the gateway:
        time_clock_user_id, serial_number, timestamp, method, action,
        raw_data, original_status.

        Args:
            attendance_logs: Iterable of AttendanceLog objects or dicts.
            serial_number: Optional device serial number override.

        Returns:
            API response dict.
        """
        if not attendance_logs:
            app_logger.info("No attendance logs provided for sync; skipping call.")
            return {"status": 204, "message": "No attendance logs to sync"}

        branch_setting = setting_repo.get("ACTIVE_BRANCH_ID")
        branch_id = (
            branch_setting.value
            if branch_setting and branch_setting.value not in (None, "")
            else "0"
        )

        normalized_logs: List[Dict[str, Any]] = []
        for log in attendance_logs:
            if isinstance(log, dict):
                record = log
                user_id = record.get("user_id") or record.get("time_clock_user_id")
                record_serial = record.get("serial_number")
                timestamp = record.get("timestamp")
                method = record.get("method")
                action = record.get("action")
                raw_data = record.get("raw_data")
                original_status = record.get("original_status")
            else:
                user_id = getattr(log, "user_id", None)
                record_serial = getattr(log, "serial_number", None)
                timestamp = getattr(log, "timestamp", None)
                method = getattr(log, "method", None)
                action = getattr(log, "action", None)
                raw_data = getattr(log, "raw_data", None)
                original_status = getattr(log, "original_status", None)

            timestamp_value = timestamp
            if isinstance(timestamp_value, datetime):
                timestamp_value = timestamp_value.strftime("%Y-%m-%d %H:%M:%S")
            elif timestamp_value is not None:
                timestamp_value = str(timestamp_value)

            if raw_data and isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except (json.JSONDecodeError, TypeError):
                    # Keep original string if it is not a JSON blob
                    pass

            if not user_id or not timestamp:
                app_logger.warning(
                    "Skipping attendance log without mandatory fields: %s", log
                )
                continue

            normalized_logs.append(
                {
                    "time_clock_user_id": user_id,
                    "serial_number": record_serial or serial_number or "",
                    "timestamp": timestamp_value,
                    "method": method,
                    "action": action,
                    "raw_data": raw_data,
                    "original_status": original_status,
                    "branch_id": branch_id,
                }
            )

        if not normalized_logs:
            app_logger.info(
                "All attendance logs were skipped due to missing mandatory fields."
            )
            return {"status": 204, "message": "No valid attendance logs to sync"}

        endpoint = "/time-clock-employees/sync-attendance-logs"
        payload = {
            "timestamp": int(time.time()),
            "attendance_logs": normalized_logs,
        }

        header_serial = serial_number or normalized_logs[0]["serial_number"]
        return self._make_request(
            "POST",
            endpoint,
            payload,
            serial_number=header_serial if header_serial else None,
        )


# Singleton instance
external_api_service = ExternalAPIService()

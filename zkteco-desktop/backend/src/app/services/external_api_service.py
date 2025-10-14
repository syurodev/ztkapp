
import requests
import json
import time
from typing import List, Dict, Any, Optional

from app.shared.logger import app_logger
from app.config.config_manager import config_manager
from app.repositories import setting_repo

class ExternalAPIService:
    def __init__(self):
        self.base_url = config_manager.get_external_api_url()
        self.api_key = config_manager.get_external_api_key()
        self.project_id = "1055"

    def _make_request(self, method: str, endpoint: str, payload: Dict = None, serial_number: Optional[str] = None) -> Dict:
        if not self.base_url or not self.api_key:
            app_logger.error("External API URL or API Key is not configured.")
            raise ValueError("API_GATEWAY_DOMAIN and EXTERNAL_API_KEY must be configured.")

        url = self.base_url + endpoint
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "ProjectId": self.project_id,
        }
        if serial_number:
            headers["x-device-sync"] = serial_number

        # Add branch ID to all requests except for the branches list itself
        if endpoint != "/time-clock-employees/branchs":
            branch_id_setting = setting_repo.get("ACTIVE_BRANCH_ID")
            if branch_id_setting and branch_id_setting.value:
                headers["x-branch-id"] = branch_id_setting.value

        redacted_headers = {
            key: ("***" if key.lower() in {"x-api-key", "authorization", "x-branch-id"} else value)
            for key, value in headers.items()
        }
        
        app_logger.info(
            f"External API Request -> Method: {method}, URL: {url}, Headers: {redacted_headers}"
        )
        if payload:
            app_logger.debug(f"Request Payload: {json.dumps(payload)}")

        try:
            response = requests.request(method, url, json=payload, headers=headers, timeout=30)
            
            response_preview = response.text.strip()
            if len(response_preview) > 1000:
                response_preview = response_preview[:1000] + "...[truncated]"
            
            app_logger.info(
                f"External API Response <- Status: {response.status_code}, Body: {response_preview}"
            )
            
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") != 200:
                app_logger.warning(f"External API returned non-200 status: {data.get('message')}")
            
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

    def sync_employees(self, employees: List[Dict[str, Any]], serial_number: str) -> Dict:
        """
        Syncs a list of employees to the external API.
        """
        endpoint = "/time-clock-employees/sync"
        payload = {"timestamp": int(time.time()), "employees": employees}
        return self._make_request("POST", endpoint, payload, serial_number=serial_number)

    def sync_checkin_data(self, sync_payload: Dict[str, Any], serial_number: str) -> Dict:
        """
        Syncs attendance/check-in data to the external API.
        """
        endpoint = "/time-clock-employees/sync-checkin-data"
        return self._make_request("POST", endpoint, sync_payload, serial_number=serial_number)

    def sync_device(self, sync_data: Dict, serial_number: Optional[str]) -> Dict:
        """
        Syncs device information to the external API.
        """
        endpoint = "/time-clock-employees/sync-device"
        return self._make_request("POST", endpoint, sync_data, serial_number=serial_number)

    def get_branches(self) -> Dict:
        """
        Fetches a list of branches from the external API.
        """
        endpoint = "/time-clock-employees/branches"
        return self._make_request("GET", endpoint)

# Singleton instance
external_api_service = ExternalAPIService()

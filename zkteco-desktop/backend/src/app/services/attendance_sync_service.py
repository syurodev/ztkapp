import time
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

from app.shared.logger import app_logger
from app.repositories import attendance_repo, user_repo
from app.models import SyncStatus
from app.database.connection import db_manager
from app.config.config_manager import config_manager


class AttendanceSyncService:
    """Service for syncing daily attendance data with first checkin/last checkout logic"""

    MAX_RECORDS_PER_REQUEST = 100

    def __init__(self):
        self.logger = app_logger

    def sync_attendance_daily(self, target_date: Optional[str] = None, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync daily attendance data with first checkin/last checkout logic and anti-duplicate protection

        Args:
            target_date: Date in YYYY-MM-DD format (default: today)
            device_id: Specific device ID (optional)

        Returns:
            Dict with sync results and statistics
        """
        try:
            # Parse target date or get all pending dates
            if target_date:
                sync_dates = [datetime.strptime(target_date, '%Y-%m-%d').date()]
            else:
                # Get all dates with pending records
                pending_dates = attendance_repo.get_pending_sync_dates(device_id)
                if not pending_dates:
                    return {
                        'success': True,
                        'message': 'No pending attendance data found',
                        'dates_processed': [],
                        'count': 0
                    }

                # Convert string dates to date objects
                sync_dates = [datetime.strptime(date_str, '%Y-%m-%d').date() for date_str in pending_dates]

            self.logger.info(f"Starting attendance sync for dates: {sync_dates}, device: {device_id or 'all'}")

            total_synced = 0
            processed_dates = []
            all_attendance_summaries = []

            external_api_domain = None

            # Process each date and collect all data
            for sync_date in sync_dates:
                self.logger.info(f"Processing attendance for date: {sync_date}")

                # Apply anti-duplicate logic and get attendance data
                attendance_summary = self._calculate_daily_attendance_with_dedup(sync_date, device_id)

                if attendance_summary:
                    # Add date and device info to each user summary
                    for user_summary in attendance_summary:
                        user_summary['date'] = str(sync_date)
                        user_summary['device_id'] = device_id

                        # Get device serial for this summary
                        if device_id:
                            device = config_manager.get_device(device_id)
                        else:
                            device = config_manager.get_active_device()

                        serial_number = 'unknown'
                        if device:
                            device_info = device.get('device_info', {})
                            serial_number = device_info.get('serial_number', device.get('serial_number', device_id or 'unknown'))

                        user_summary['device_serial'] = serial_number

                    total_synced += len(attendance_summary)
                    all_attendance_summaries.extend(attendance_summary)

                    # Lazy-load external API configuration
                    if external_api_domain is None:
                        external_api_domain = config_manager.get_external_api_url()
                        if not external_api_domain:
                            raise ValueError("API_GATEWAY_DOMAIN not configured")

                    total_batches = (len(attendance_summary) + self.MAX_RECORDS_PER_REQUEST - 1) // self.MAX_RECORDS_PER_REQUEST

                    for batch_index, batch in enumerate(
                        self._iter_record_batches(attendance_summary, self.MAX_RECORDS_PER_REQUEST),
                        start=1
                    ):
                        self.logger.info(
                            f"Sending attendance batch {batch_index}/{total_batches} for {sync_date} with {len(batch)} records"
                        )

                        sync_result = self._send_to_external_api(batch, sync_date, external_api_domain, device_id)

                        if sync_result.get('error'):
                            self.logger.warning(
                                f"Skipping remaining batches due to error: {sync_result['error']}"
                            )
                            break

                        self._process_api_response(sync_result.get('response_data', {}), batch)

                processed_dates.append(str(sync_date))

            # Save attendance summaries to JSON file for debugging
            import json
            import os
            debug_file = os.path.join(os.path.dirname(__file__), '..', '..', 'attendance_debug.json')
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(all_attendance_summaries, f, indent=2, ensure_ascii=False, default=str)
            app_logger.info(f"Saved {len(all_attendance_summaries)} attendance summaries to {debug_file}")

            self.logger.info(f"Attendance sync completed for {len(processed_dates)} dates: {total_synced} total records")

            return {
                'success': True,
                'dates_processed': processed_dates,
                'count': total_synced,
                'attendance_summary': all_attendance_summaries,
                'total_dates': len(processed_dates)
            }

        except Exception as e:
            self.logger.error(f"Error in sync_attendance_daily: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'dates_processed': []
            }

    def sync_first_checkins(self, target_date: Optional[str] = None, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Sync only first check-ins for the target date (defaults to today)."""
        try:
            # Determine target date
            if target_date:
                sync_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                sync_date = date.today()

            self.logger.info(
                f"Starting first-checkin sync for date: {sync_date}, device: {device_id or 'all'}"
            )

            attendance_summary = self._calculate_daily_attendance_with_dedup(sync_date, device_id)

            if not attendance_summary:
                return {
                    'success': True,
                    'message': 'No pending first checkins found',
                    'date': str(sync_date),
                    'count': 0
                }

            # Get device serial once per batch
            if device_id:
                device = config_manager.get_device(device_id)
            else:
                device = config_manager.get_active_device()

            serial_number = 'unknown'
            if device:
                device_info = device.get('device_info', {})
                serial_number = device_info.get('serial_number', device.get('serial_number', device_id or 'unknown'))

            # Prepare summaries for API (only checkins)
            for user_summary in attendance_summary:
                user_summary['date'] = str(sync_date)
                user_summary['device_id'] = device_id
                user_summary['device_serial'] = serial_number
                user_summary['last_checkout'] = None
                user_summary['last_checkout_id'] = None

            # Filter out summaries without a valid first checkin
            valid_summaries = [
                summary
                for summary in attendance_summary
                if summary.get('first_checkin') and (summary.get('external_user_id') or 0) > 0
            ]

            if not valid_summaries:
                self.logger.info(
                    "No first checkin records available after filtering, skipping sync"
                )
                return {
                    'success': True,
                    'date': str(sync_date),
                    'count': 0,
                    'synced_records': 0,
                    'message': 'No valid first checkins to sync'
                }

            external_api_domain = config_manager.get_external_api_url()
            if not external_api_domain:
                raise ValueError("API_GATEWAY_DOMAIN not configured")

            total_batches = (len(valid_summaries) + self.MAX_RECORDS_PER_REQUEST - 1) // self.MAX_RECORDS_PER_REQUEST
            synced_records = 0

            for batch_index, batch in enumerate(
                self._iter_record_batches(valid_summaries, self.MAX_RECORDS_PER_REQUEST),
                start=1
            ):
                self.logger.info(
                    f"[First Checkin Sync] Sending batch {batch_index}/{total_batches} with {len(batch)} records"
                )

                sync_result = self._send_to_external_api(batch, sync_date, external_api_domain, device_id)

                if sync_result.get('error'):
                    self.logger.warning(
                        f"[First Checkin Sync] Stopping due to error: {sync_result['error']}"
                    )
                    break

                synced_records += sync_result.get('sent_count', len(batch))
                self._process_api_response(sync_result.get('response_data', {}), batch)

            return {
                'success': True,
                'date': str(sync_date),
                'count': len(valid_summaries),
                'synced_records': synced_records
            }

        except Exception as e:
            self.logger.error(f"Error in sync_first_checkins: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'date': str(target_date or date.today())
            }

    def _calculate_daily_attendance(self, target_date: date, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculate first checkin and last checkout for each user on target date

        Args:
            target_date: Target date for calculation
            device_id: Optional device filter

        Returns:
            List of attendance summaries per user
        """
        try:
            # Query attendance logs for the target date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            # Get pending attendance logs for the date range
            if device_id:
                query = """
                    SELECT * FROM attendance_logs
                    WHERE device_id = ? AND timestamp BETWEEN ? AND ? AND sync_status = ?
                    ORDER BY user_id, timestamp
                """
                logs = db_manager.fetch_all(query, (device_id, start_datetime, end_datetime, SyncStatus.PENDING))
            else:
                query = """
                    SELECT * FROM attendance_logs
                    WHERE timestamp BETWEEN ? AND ? AND sync_status = ?
                    ORDER BY user_id, timestamp
                """
                logs = db_manager.fetch_all(query, (start_datetime, end_datetime, SyncStatus.PENDING))

            if not logs:
                return []

            # Group logs by user_id
            user_logs = defaultdict(list)
            for log in logs:
                user_logs[log['user_id']].append(log)

            # Get user names mapping
            users = user_repo.get_all(device_id)
            user_name_map = {user.user_id: user.name for user in users}
            user_external_id_map = {
                user.user_id: getattr(user, 'external_user_id', None) for user in users
            }

            # Calculate first checkin and last checkout for each user
            attendance_summary = []

            for user_id, logs_list in user_logs.items():
                # Separate checkin and checkout records
                checkins = [log for log in logs_list if log['action'] == 0]  # action=0 is checkin
                checkouts = [log for log in logs_list if log['action'] == 1]  # action=1 is checkout

                first_checkin = None
                last_checkout = None

                # Find first checkin (earliest timestamp)
                if checkins:
                    first_checkin_log = min(checkins, key=lambda x: x['timestamp'])
                    timestamp = first_checkin_log['timestamp']
                    # Handle both string and datetime objects
                    if isinstance(timestamp, str):
                        first_checkin = timestamp
                    else:
                        first_checkin = timestamp.strftime('%Y-%m-%d %H:%M:%S')

                # Find last checkout (latest timestamp)
                if checkouts:
                    last_checkout_log = max(checkouts, key=lambda x: x['timestamp'])
                    timestamp = last_checkout_log['timestamp']
                    # Handle both string and datetime objects
                    if isinstance(timestamp, str):
                        last_checkout = timestamp
                    else:
                        last_checkout = timestamp.strftime('%Y-%m-%d %H:%M:%S')

                # Only include users who have at least one checkin or checkout
                if first_checkin or last_checkout:
                    user_summary = {
                        'user_id': user_id,
                        'name': user_name_map.get(user_id, 'Unknown User'),
                        'external_user_id': user_external_id_map.get(user_id),
                        'first_checkin': first_checkin,
                        'last_checkout': last_checkout,
                        'total_checkins': len(checkins),
                        'total_checkouts': len(checkouts)
                    }
                    attendance_summary.append(user_summary)

            self.logger.info(f"Calculated attendance for {len(attendance_summary)} users on {target_date}")
            return attendance_summary

        except Exception as e:
            self.logger.error(f"Error calculating daily attendance: {e}")
            raise

    def _calculate_daily_attendance_with_dedup(self, target_date: date, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculate first checkin and last checkout with anti-duplicate logic

        Args:
            target_date: Target date for calculation
            device_id: Optional device filter

        Returns:
            List of attendance summaries per user with deduplication applied (includes record IDs)
        """
        try:
            # Get basic attendance summary with record IDs
            attendance_summary = self._calculate_daily_attendance_with_ids(target_date, device_id)

            if not attendance_summary:
                return []

            # Apply anti-duplicate logic for each user
            final_summary = []
            target_date_str = str(target_date)

            for user_summary in attendance_summary:
                user_id = user_summary['user_id']

                # Check if this user already has synced checkin for this date
                has_synced_checkin = attendance_repo.has_synced_record_for_date_action(
                    user_id, target_date_str, 0, device_id  # action=0 is checkin
                )

                # Check if this user already has synced checkout for this date
                has_synced_checkout = attendance_repo.has_synced_record_for_date_action(
                    user_id, target_date_str, 1, device_id  # action=1 is checkout
                )

                # Modify user summary based on existing synced records
                if has_synced_checkin:
                    user_summary['first_checkin'] = None  # Don't sync checkin again
                    user_summary['first_checkin_id'] = None
                    self.logger.info(f"User {user_id} already has synced checkin for {target_date_str}, skipping")

                if has_synced_checkout:
                    user_summary['last_checkout'] = None  # Don't sync checkout again
                    user_summary['last_checkout_id'] = None
                    self.logger.info(f"User {user_id} already has synced checkout for {target_date_str}, skipping")

                # Only include user if they have at least one valid record to sync
                if user_summary['first_checkin'] or user_summary['last_checkout']:
                    final_summary.append(user_summary)
                else:
                    self.logger.info(f"User {user_id} has no new records to sync for {target_date_str}")

            self.logger.info(f"After deduplication: {len(final_summary)} users to sync for {target_date}")
            return final_summary

        except Exception as e:
            self.logger.error(f"Error calculating daily attendance with dedup: {e}")
            raise

    def _calculate_daily_attendance_with_ids(self, target_date: date, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculate first checkin and last checkout for each user on target date with record IDs

        Args:
            target_date: Target date for calculation
            device_id: Optional device filter

        Returns:
            List of attendance summaries per user including record IDs
        """
        try:
            # Query attendance logs for the target date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            # Get pending attendance logs for the date range
            if device_id:
                query = """
                    SELECT * FROM attendance_logs
                    WHERE device_id = ? AND timestamp BETWEEN ? AND ? AND sync_status = ?
                    ORDER BY user_id, timestamp
                """
                logs = db_manager.fetch_all(query, (device_id, start_datetime, end_datetime, SyncStatus.PENDING))
            else:
                query = """
                    SELECT * FROM attendance_logs
                    WHERE timestamp BETWEEN ? AND ? AND sync_status = ?
                    ORDER BY user_id, timestamp
                """
                logs = db_manager.fetch_all(query, (start_datetime, end_datetime, SyncStatus.PENDING))

            if not logs:
                return []

            # Group logs by user_id
            user_logs = defaultdict(list)
            for log in logs:
                user_logs[log['user_id']].append(log)

            # Get user names mapping
            users = user_repo.get_all(device_id)
            user_name_map = {user.user_id: user.name for user in users}
            user_external_id_map = {
                user.user_id: getattr(user, 'external_user_id', None) for user in users
            }

            # Calculate first checkin and last checkout for each user with IDs
            attendance_summary = []

            for user_id, logs_list in user_logs.items():
                # Separate checkin and checkout records
                checkins = [log for log in logs_list if log['action'] == 0]  # action=0 is checkin
                checkouts = [log for log in logs_list if log['action'] == 1]  # action=1 is checkout

                first_checkin = None
                first_checkin_id = None
                last_checkout = None
                last_checkout_id = None

                # Find first checkin (earliest timestamp)
                if checkins:
                    first_checkin_log = min(checkins, key=lambda x: x['timestamp'])
                    timestamp = first_checkin_log['timestamp']
                    # Handle both string and datetime objects
                    if isinstance(timestamp, str):
                        first_checkin = timestamp
                    else:
                        first_checkin = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    first_checkin_id = first_checkin_log['id']

                # Find last checkout (latest timestamp)
                if checkouts:
                    last_checkout_log = max(checkouts, key=lambda x: x['timestamp'])
                    timestamp = last_checkout_log['timestamp']
                    # Handle both string and datetime objects
                    if isinstance(timestamp, str):
                        last_checkout = timestamp
                    else:
                        last_checkout = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    last_checkout_id = last_checkout_log['id']

                # Only include users who have at least one checkin or checkout
                if first_checkin or last_checkout:
                    user_summary = {
                        'user_id': user_id,
                        'name': user_name_map.get(user_id, 'Unknown User'),
                        'external_user_id': user_external_id_map.get(user_id),
                        'first_checkin': first_checkin,
                        'first_checkin_id': first_checkin_id,
                        'last_checkout': last_checkout,
                        'last_checkout_id': last_checkout_id,
                        'total_checkins': len(checkins),
                        'total_checkouts': len(checkouts)
                    }
                    attendance_summary.append(user_summary)

            self.logger.info(f"Calculated attendance with IDs for {len(attendance_summary)} users on {target_date}")
            return attendance_summary

        except Exception as e:
            self.logger.error(f"Error calculating daily attendance with IDs: {e}")
            raise

    def _finalize_sync_status(self, attendance_summary: List[Dict[str, Any]], sync_date: date, device_id: Optional[str] = None, synced_ids: List[int] = None):
        """
        Mark appropriate records as synced and others as skipped

        Args:
            attendance_summary: List of user attendance summaries that were sent to API
            sync_date: Date that was synced
            device_id: Optional device filter
            synced_ids: List of record IDs that were successfully synced (from API response)
        """
        try:
            target_date_str = str(sync_date)

            for user_summary in attendance_summary:
                user_id = user_summary['user_id']

                # If checkin was synced, mark the first checkin as synced and others as skipped
                if user_summary.get('first_checkin') and user_summary.get('first_checkin_id'):
                    checkin_id = user_summary['first_checkin_id']

                    # Check if this ID was successfully synced (if API provided feedback)
                    if synced_ids is None or checkin_id in synced_ids:
                        attendance_repo.update_sync_status(checkin_id, SyncStatus.SYNCED)
                        self.logger.info(f"User {user_id} checkin {checkin_id} marked as synced")
                    else:
                        self.logger.warning(f"User {user_id} checkin {checkin_id} was not confirmed by external API")

                    # Mark other checkin records as skipped
                    self._mark_other_records_as_skipped(user_id, target_date_str, 0, checkin_id, device_id)

                # If checkout was synced, mark the last checkout as synced and others as skipped
                if user_summary.get('last_checkout') and user_summary.get('last_checkout_id'):
                    checkout_id = user_summary['last_checkout_id']

                    # Check if this ID was successfully synced (if API provided feedback)
                    if synced_ids is None or checkout_id in synced_ids:
                        attendance_repo.update_sync_status(checkout_id, SyncStatus.SYNCED)
                        self.logger.info(f"User {user_id} checkout {checkout_id} marked as synced")
                    else:
                        self.logger.warning(f"User {user_id} checkout {checkout_id} was not confirmed by external API")

                    # Mark other checkout records as skipped
                    self._mark_other_records_as_skipped(user_id, target_date_str, 1, checkout_id, device_id)

            self.logger.info(f"Finalized sync status for {len(attendance_summary)} users on {target_date_str}")

        except Exception as e:
            self.logger.error(f"Error finalizing sync status: {e}")
            raise

    def _process_api_response(self, response_data: Dict[str, Any], attendance_summaries: List[Dict[str, Any]]):
        """
        Process API response and update record statuses based on success/error operations

        Args:
            response_data: Response from external API containing success and error operations
            attendance_summaries: List of all attendance summaries that were sent
        """
        try:
            if not response_data:
                self.logger.warning("No response data provided from API")
                return

            if 'data' not in response_data:
                self.logger.error(f"Invalid API response format - missing 'data' field: {response_data}")
                return

            data = response_data.get('data')
            if not data:
                self.logger.warning("Response data is None or empty")
                return

            success_operations = data.get('successOperations', [])
            errors = data.get('errors', [])

            self.logger.info(f"Processing API response: {len(success_operations)} success, {len(errors)} errors")

            # Process successful operations
            for success_op in success_operations:
                operation_id = success_op.get('operationId')
                if operation_id:
                    attendance_repo.update_sync_status(operation_id, SyncStatus.SYNCED)
                    self.logger.info(f"Record {operation_id} marked as synced successfully")

            # Process error operations
            for error in errors:
                user_id = error.get('userId')
                operation = error.get('operation')
                error_code = error.get('errorCode')
                error_message = error.get('errorMessage')

                # Get record IDs from error response
                if operation == 'CHECKIN':
                    record_id = error.get('firstCheckinId')
                elif operation == 'CHECKOUT':
                    record_id = error.get('lastCheckoutId')
                else:
                    continue

                # Update record with error status
                if record_id and record_id != 0:  # 0 means no record ID provided
                    attendance_repo.update_sync_error(record_id, error_code, error_message)
                    self.logger.warning(f"Record {record_id} marked as error: {error_code} - {error_message}")

            # Mark other records as skipped for each user summary
            for user_summary in attendance_summaries:
                user_id = user_summary['user_id']
                date = user_summary['date']
                device_id = user_summary.get('device_id')

                # Mark other checkin records as skipped if we processed the first checkin
                if user_summary.get('first_checkin_id'):
                    self._mark_other_records_as_skipped(user_id, date, 0, user_summary['first_checkin_id'], device_id)

                # Mark other checkout records as skipped if we processed the last checkout
                if user_summary.get('last_checkout_id'):
                    self._mark_other_records_as_skipped(user_id, date, 1, user_summary['last_checkout_id'], device_id)

            self.logger.info(f"Processed API response for {len(attendance_summaries)} attendance summaries")

        except Exception as e:
            self.logger.error(f"Error processing API response: {e}")
            raise

    def _finalize_sync_status_by_ids(self, attendance_summaries: List[Dict[str, Any]], synced_ids: List[int]):
        """
        DEPRECATED: Mark records as synced based on returned IDs from consolidated API response
        Use _process_api_response() instead for new response format handling

        Args:
            attendance_summaries: List of all attendance summaries that were sent
            synced_ids: List of record IDs that were successfully synced (from API response)
        """
        try:
            for user_summary in attendance_summaries:
                user_id = user_summary['user_id']
                date = user_summary['date']
                device_id = user_summary.get('device_id')

                # Check and mark checkin record
                if user_summary.get('first_checkin') and user_summary.get('first_checkin_id'):
                    checkin_id = user_summary['first_checkin_id']

                    if synced_ids is None or checkin_id in synced_ids:
                        attendance_repo.update_sync_status(checkin_id, SyncStatus.SYNCED)
                        self.logger.info(f"User {user_id} checkin {checkin_id} marked as synced")
                    else:
                        self.logger.warning(f"User {user_id} checkin {checkin_id} was not confirmed by external API")

                    # Mark other checkin records as skipped
                    self._mark_other_records_as_skipped(user_id, date, 0, checkin_id, device_id)

                # Check and mark checkout record
                if user_summary.get('last_checkout') and user_summary.get('last_checkout_id'):
                    checkout_id = user_summary['last_checkout_id']

                    if synced_ids is None or checkout_id in synced_ids:
                        attendance_repo.update_sync_status(checkout_id, SyncStatus.SYNCED)
                        self.logger.info(f"User {user_id} checkout {checkout_id} marked as synced")
                    else:
                        self.logger.warning(f"User {user_id} checkout {checkout_id} was not confirmed by external API")

                    # Mark other checkout records as skipped
                    self._mark_other_records_as_skipped(user_id, date, 1, checkout_id, device_id)

            self.logger.info(f"Finalized sync status for {len(attendance_summaries)} attendance summaries")

        except Exception as e:
            self.logger.error(f"Error finalizing sync status by IDs: {e}")
            raise

    def _mark_other_records_as_skipped(self, user_id: str, target_date_str: str, action: int, exclude_id: int, device_id: Optional[str] = None):
        """Mark other records as skipped (excluding the synced one)"""
        try:
            other_record_ids = attendance_repo.get_other_records_for_date_action(
                user_id, target_date_str, action, exclude_id, device_id
            )

            if other_record_ids:
                attendance_repo.mark_records_as_skipped(other_record_ids)
                action_name = "checkin" if action == 0 else "checkout"
                self.logger.info(f"User {user_id} {target_date_str}: marked {len(other_record_ids)} other {action_name} records as skipped")

        except Exception as e:
            self.logger.error(f"Error marking other records as skipped: {e}")
            raise

    def _mark_first_record_as_synced_others_skipped(self, user_id: str, target_date_str: str, action: int, device_id: Optional[str] = None):
        """Mark first record (earliest) as synced, others as skipped"""
        try:
            # Get all pending records for this user, date, and action
            if device_id:
                query = """
                    SELECT id FROM attendance_logs
                    WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND device_id = ? AND sync_status = ?
                    ORDER BY timestamp ASC
                """
                rows = db_manager.fetch_all(query, (user_id, target_date_str, action, device_id, SyncStatus.PENDING))
            else:
                query = """
                    SELECT id FROM attendance_logs
                    WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ?
                    ORDER BY timestamp ASC
                """
                rows = db_manager.fetch_all(query, (user_id, target_date_str, action, SyncStatus.PENDING))

            if rows:
                first_record_id = rows[0]['id']
                other_record_ids = [row['id'] for row in rows[1:]]

                # Mark first record as synced
                attendance_repo.update_sync_status(first_record_id, SyncStatus.SYNCED)

                # Mark other records as skipped
                if other_record_ids:
                    attendance_repo.mark_records_as_skipped(other_record_ids)

                action_name = "checkin" if action == 0 else "checkout"
                self.logger.info(f"User {user_id} {target_date_str}: marked 1 {action_name} as synced, {len(other_record_ids)} as skipped")

        except Exception as e:
            self.logger.error(f"Error marking first record as synced: {e}")
            raise

    def _mark_last_record_as_synced_others_skipped(self, user_id: str, target_date_str: str, action: int, device_id: Optional[str] = None):
        """Mark last record (latest) as synced, others as skipped"""
        try:
            # Get all pending records for this user, date, and action
            if device_id:
                query = """
                    SELECT id FROM attendance_logs
                    WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND device_id = ? AND sync_status = ?
                    ORDER BY timestamp DESC
                """
                rows = db_manager.fetch_all(query, (user_id, target_date_str, action, device_id, SyncStatus.PENDING))
            else:
                query = """
                    SELECT id FROM attendance_logs
                    WHERE user_id = ? AND DATE(timestamp) = ? AND action = ? AND sync_status = ?
                    ORDER BY timestamp DESC
                """
                rows = db_manager.fetch_all(query, (user_id, target_date_str, action, SyncStatus.PENDING))

            if rows:
                last_record_id = rows[0]['id']
                other_record_ids = [row['id'] for row in rows[1:]]

                # Mark last record as synced
                attendance_repo.update_sync_status(last_record_id, SyncStatus.SYNCED)

                # Mark other records as skipped
                if other_record_ids:
                    attendance_repo.mark_records_as_skipped(other_record_ids)

                action_name = "checkin" if action == 0 else "checkout"
                self.logger.info(f"User {user_id} {target_date_str}: marked 1 {action_name} as synced, {len(other_record_ids)} as skipped")

        except Exception as e:
            self.logger.error(f"Error marking last record as synced: {e}")
            raise

    def _iter_record_batches(self, records: List[Dict[str, Any]], batch_size: int):
        """Yield successive batches from the records list"""
        for index in range(0, len(records), batch_size):
            yield records[index:index + batch_size]

    def _send_to_external_api(self, attendance_summary: List[Dict[str, Any]], sync_date: date,
                             external_api_domain: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send attendance summary to external API

        Args:
            attendance_summary: List of user attendance summaries
            sync_date: Date being synced
            external_api_domain: External API domain URL
            device_id: Optional device ID

        Returns:
            API response data
        """
        try:
            if not attendance_summary:
                return {
                    'success': True,
                    'status_code': 204,
                    'response_data': None,
                    'sent_count': 0
                }

            filtered_summary = [
                record for record in attendance_summary
                if (record.get('external_user_id') or 0) > 0
            ]

            if not filtered_summary:
                self.logger.info(
                    "No attendance records have external_user_id, skipping external API call"
                )
                return {
                    'success': True,
                    'status_code': 204,
                    'response_data': None,
                    'sent_count': 0
                }

            # Construct API URL
            external_api_url = external_api_domain + '/time-clock-employees/sync-checkin-data'

            # Get device info for serial number
            if device_id:
                device = config_manager.get_device(device_id)
            else:
                device = config_manager.get_active_device()

            serial_number = 'unknown'
            if device:
                device_info = device.get('device_info', {})
                serial_number = device_info.get('serial_number', device.get('serial_number', device_id or 'unknown'))

            # Prepare sync data
            sync_data = {
                'timestamp': int(time.time()),
                'date': str(sync_date),
                'device_id': device_id,
                'device_serial': serial_number,
                'checkin_data_list': filtered_summary
            }

            app_logger.info(sync_data)


            # Get API key from config
            api_key = config_manager.get_external_api_key()
            if not api_key:
                self.logger.warning("EXTERNAL_API_KEY not configured, skipping daily attendance sync")
                return {
                    'error': 'EXTERNAL_API_KEY not configured'
                }

            # Prepare headers (similar to sync_employee)
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'x-device-sync': serial_number,
                'ProjectId': '1055'
            }

            # Make API request
            response = requests.post(
                external_api_url,
                json=sync_data,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            response_data = response.json()

            app_logger.info(response)
            app_logger.info(response_data)

            return {
                'status_code': response.status_code,
                'response_data': response_data,
                'sent_count': len(filtered_summary),
                'synced_ids': response_data.get('synced_ids') if response_data else None
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP error sending attendance data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error sending attendance data to external API: {e}")
            raise

    def get_daily_attendance_preview(self, target_date: Optional[str] = None, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get preview of daily attendance data without sending to external API

        Args:
            target_date: Date in YYYY-MM-DD format (default: today)
            device_id: Specific device ID (optional)

        Returns:
            Dict with attendance summary data
        """
        try:
            # Parse target date
            if target_date:
                sync_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                sync_date = date.today()

            # Get attendance data for the target date
            attendance_summary = self._calculate_daily_attendance(sync_date, device_id)

            return {
                'success': True,
                'date': str(sync_date),
                'count': len(attendance_summary),
                'attendance_summary': attendance_summary
            }

        except Exception as e:
            self.logger.error(f"Error in get_daily_attendance_preview: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'date': str(target_date or date.today())
            }

    def retry_error_records(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retry sync for records that previously failed with error status

        Args:
            device_id: Specific device ID (optional)

        Returns:
            Dict with retry results
        """
        try:
            # Get error records
            error_records = attendance_repo.get_error_records(device_id)

            if not error_records:
                return {
                    'success': True,
                    'message': 'No error records found to retry',
                    'count': 0
                }

            self.logger.info(f"Found {len(error_records)} error records to retry")

            # Reset error records to pending status for retry
            retry_count = 0
            for record in error_records:
                if attendance_repo.update_sync_status(record.id, SyncStatus.PENDING):
                    retry_count += 1

            self.logger.info(f"Reset {retry_count} error records to pending status")

            # Now sync these records using the normal sync process
            # Get unique dates from error records
            retry_dates = list(set([record.timestamp.date() for record in error_records]))

            total_synced = 0
            processed_dates = []

            for retry_date in retry_dates:
                # Use the normal sync process for this date
                sync_result = self.sync_attendance_daily(str(retry_date), device_id)
                if sync_result.get('success'):
                    total_synced += sync_result.get('count', 0)
                    processed_dates.extend(sync_result.get('dates_processed', []))

            return {
                'success': True,
                'message': f'Retry completed for {retry_count} error records',
                'retry_records_count': retry_count,
                'dates_processed': processed_dates,
                'total_synced': total_synced
            }

        except Exception as e:
            self.logger.error(f"Error in retry_error_records: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'retry_records_count': 0
            }

    def get_error_summary(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary of error records for admin review

        Args:
            device_id: Specific device ID (optional)

        Returns:
            Dict with error summary data
        """
        try:
            # Get error records
            error_records = attendance_repo.get_error_records(device_id)

            # Group errors by error code
            error_groups = {}
            for record in error_records:
                error_code = record.error_code or 'UNKNOWN'
                if error_code not in error_groups:
                    error_groups[error_code] = {
                        'count': 0,
                        'sample_message': record.error_message,
                        'records': []
                    }

                error_groups[error_code]['count'] += 1
                error_groups[error_code]['records'].append({
                    'id': record.id,
                    'user_id': record.user_id,
                    'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'action': 'CHECKIN' if record.action == 0 else 'CHECKOUT',
                    'error_message': record.error_message
                })

            # Get sync statistics
            sync_stats = attendance_repo.get_sync_stats(device_id)

            return {
                'success': True,
                'total_error_records': len(error_records),
                'error_groups': error_groups,
                'sync_statistics': sync_stats
            }

        except Exception as e:
            self.logger.error(f"Error in get_error_summary: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_error_records': 0
            }


# Service instance
attendance_sync_service = AttendanceSyncService()

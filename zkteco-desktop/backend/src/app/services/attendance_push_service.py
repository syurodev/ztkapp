from collections import defaultdict
from datetime import datetime
from typing import Iterable, Optional, Sequence, List, Dict, Tuple, Set, Any

from app.models import AttendanceLog
from app.repositories import attendance_repo
from app.services.external_api_service import external_api_service
from app.shared.logger import app_logger


def _normalize_logs(logs: Iterable[AttendanceLog]) -> List[AttendanceLog]:
    """Filter out None values and ensure logs have IDs for update."""
    normalized: List[AttendanceLog] = []
    for log in logs or []:
        if not log:
            continue
        normalized.append(log)
    return normalized


def _ensure_timestamp_str(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if value is None:
        return ""
    return str(value)


def _normalize_key_pair(user: Any, timestamp: Any) -> Tuple[str, str]:
    user_str = str(user).strip() if user is not None else ""
    timestamp_str = str(timestamp).strip() if timestamp is not None else ""
    if "T" in timestamp_str:
        # Replace ISO-style separator for consistency with DB format
        timestamp_str = timestamp_str.replace("T", " ")
    return user_str, timestamp_str


def _extract_log_key(log: Any) -> Tuple[str, str]:
    if isinstance(log, dict):
        user_id = log.get("user_id") or log.get("time_clock_user_id") or ""
        timestamp = log.get("timestamp")
    else:
        user_id = getattr(log, "user_id", "") or ""
        timestamp = getattr(log, "timestamp", None)

    return _normalize_key_pair(user_id, _ensure_timestamp_str(timestamp))


def _extract_acknowledged_keys(
    response: Optional[Dict[str, Any]],
) -> Set[Tuple[str, str]]:
    ack_keys: Set[Tuple[str, str]] = set()
    if not isinstance(response, dict):
        return ack_keys

    data = response.get("data")
    candidate_lists: List[List[Any]] = []

    if isinstance(data, list):
        candidate_lists.append(data)
    elif isinstance(data, dict):
        for key in (
            "attendance_logs",
            "records",
            "synced_logs",
            "items",
            "success_logs",
            "synced_records",
        ):
            value = data.get(key)
            if isinstance(value, list):
                candidate_lists.append(value)

    for items in candidate_lists:
        for item in items:
            if isinstance(item, dict):
                user = (
                    item.get("time_clock_user_id")
                    or item.get("user_id")
                    or item.get("employee_id")
                )
                timestamp = (
                    item.get("timestamp")
                    or item.get("datetime")
                    or item.get("clock_time")
                )
                if user is not None and timestamp:
                    ack_keys.add(_normalize_key_pair(user, timestamp))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                ack_keys.add(_normalize_key_pair(item[0], item[1]))
            elif isinstance(item, str) and "|" in item:
                user, timestamp = item.split("|", 1)
                ack_keys.add(_normalize_key_pair(user, timestamp))

    return ack_keys


def _extract_acknowledged_ids(response: Optional[Dict[str, Any]]) -> Set[int]:
    ack_ids: Set[int] = set()
    if not isinstance(response, dict):
        return ack_ids

    data = response.get("data")

    candidate_lists: List[List[Any]] = []
    if isinstance(data, dict):
        for key in ("synced_ids", "ids", "record_ids"):
            value = data.get(key)
            if isinstance(value, list):
                candidate_lists.append(value)
    elif isinstance(data, list):
        candidate_lists.append(data)

    for items in candidate_lists:
        for item in items:
            try:
                ack_ids.add(int(item))
            except (TypeError, ValueError):
                continue

    return ack_ids


def push_attendance_logs(
    logs: Sequence[AttendanceLog],
    serial_number: Optional[str] = None,
) -> Optional[dict]:
    """
    Push attendance logs to external API and mark them as pushed on success.

    Args:
        logs: AttendanceLog objects that have just been saved.
        serial_number: Device serial number for header routing (optional).

    Returns:
        API response dict when call happens, otherwise None.
    """
    if not logs:
        return None

    safe_logs = _normalize_logs(logs)
    if not safe_logs:
        return None

    log_id_list: List[int] = []
    log_key_map: Dict[int, Tuple[str, str]] = {}
    for log in safe_logs:
        log_id = getattr(log, "id", None)
        if isinstance(log_id, int):
            log_id_list.append(log_id)
        log_key_map[log_id] = _extract_log_key(log)

    try:
        response = external_api_service.sync_attendance_logs(
            safe_logs, serial_number=serial_number
        )
        status = response.get("status") if isinstance(response, dict) else None

        if status == 200:
            ack_keys = _extract_acknowledged_keys(response)
            ack_ids = _extract_acknowledged_ids(response)

            if ack_keys:
                pushed_ids = [
                    log_id
                    for log_id, key in log_key_map.items()
                    if isinstance(log_id, int) and key in ack_keys
                ]
                if len(pushed_ids) != len(log_id_list):
                    app_logger.warning(
                        "External API acknowledged %s/%s attendance logs",
                        len(pushed_ids),
                        len(log_id_list),
                    )
            elif ack_ids:
                pushed_ids = [log_id for log_id in log_id_list if log_id in ack_ids]
                if len(pushed_ids) != len(log_id_list):
                    app_logger.warning(
                        "External API acknowledged %s/%s attendance logs by ID",
                        len(pushed_ids),
                        len(log_id_list),
                    )
            else:
                pushed_ids = [log_id for log_id in log_id_list]
                if pushed_ids:
                    app_logger.debug(
                        "External API response lacked acknowledgement details; marking all %s log(s) as pushed",
                        len(pushed_ids),
                    )

            if pushed_ids:
                attendance_repo.mark_as_pushed(pushed_ids)
            app_logger.debug(
                "Marked %s attendance logs as pushed (status=200).", len(pushed_ids)
            )
        else:
            app_logger.warning(
                "External attendance sync returned non-200 status: %s message=%s",
                status,
                response.get("message") if isinstance(response, dict) else None,
            )

        return response
    except Exception as exc:
        app_logger.error(
            "Failed to push attendance logs to external API: %s", exc, exc_info=True
        )
        # Swallow exception so it doesn't break internal flow
        return None


def push_pending_attendance_logs(batch_size: int = 500) -> Dict[str, int]:
    """
    Fetch attendance logs with is_pushed = 0 and attempt to push them.

    Args:
        batch_size: Maximum number of records to process per run.

    Returns:
        Dict summary containing counts of processed/pushed logs.
    """
    try:
        pending_logs = attendance_repo.get_unpushed_logs(limit=batch_size)
    except Exception as exc:
        app_logger.error(
            "Failed to fetch unpushed attendance logs: %s", exc, exc_info=True
        )
        return {"count": 0, "groups": 0}

    if not pending_logs:
        app_logger.debug("No pending attendance logs found for batch push.")
        return {"count": 0, "groups": 0}

    grouped_logs: Dict[Optional[str], List[AttendanceLog]] = defaultdict(list)
    for log in pending_logs:
        grouped_logs[getattr(log, "serial_number", None)].append(log)

    for serial, logs in grouped_logs.items():
        for start in range(0, len(logs), batch_size):
            chunk = logs[start : start + batch_size]
            push_attendance_logs(chunk, serial_number=serial)

    return {"count": len(pending_logs), "groups": len(grouped_logs)}

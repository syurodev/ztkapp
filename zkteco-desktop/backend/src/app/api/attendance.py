from app.shared.logger import app_logger

from flask import Blueprint, jsonify, request
from app.services.device_service import get_zk_service
from app.services.attendance_sync_service import attendance_sync_service
from app.services.scheduler_service import scheduler_service
from app.services.attendance_cleanup_service import attendance_cleanup_service
from app.repositories import attendance_repo, user_repo
from flask import current_app
from datetime import datetime

bp = Blueprint("attendance", __name__, url_prefix="/")


def get_service():
    return get_zk_service()


def _map_user_names_to_logs(logs):
    """Helper function to map user names to attendance logs."""
    users = user_repo.get_all()
    user_map = {user.user_id: user.name for user in users}

    logs_with_names = []
    for log in logs:
        log_dict = log.to_dict()
        log_dict["name"] = user_map.get(log.user_id, "Unknown User")
        logs_with_names.append(log_dict)
    return logs_with_names


def _map_user_details_to_logs(logs):
    """Helper function to map user names, avatars, and employee details to attendance logs."""
    users = user_repo.get_all()
    # Use a composite key (user_id, serial_number) to handle duplicate user_ids across devices
    user_map = {
        (user.user_id, user.serial_number): {
            "name": user.name,
            "avatar_url": getattr(user, "avatar_url", None),
            "full_name": getattr(user, "full_name", None),
            "employee_code": getattr(user, "employee_code", None),
            "position": getattr(user, "position", None),
            "department": getattr(user, "department", None),
            "notes": getattr(user, "notes", None),
            "employee_object": getattr(
                user, "employee_object", None
            ),  # Add employee_object
        }
        for user in users
    }

    enriched_logs = []
    for log in logs:
        log_dict = log.to_dict()
        # Use the composite key for lookup
        user_info = user_map.get((log.user_id, log.serial_number))

        if user_info:
            log_dict["name"] = user_info["name"]
            log_dict["avatar_url"] = user_info["avatar_url"]
            log_dict["full_name"] = user_info["full_name"]
            log_dict["employee_code"] = user_info["employee_code"]
            log_dict["position"] = user_info["position"]
            log_dict["department"] = user_info["department"]
            log_dict["notes"] = user_info["notes"]
            log_dict["employee_object"] = user_info[
                "employee_object"
            ]  # Add employee_object
        else:
            log_dict["name"] = "Unknown User"
            log_dict["avatar_url"] = None
            log_dict["full_name"] = None
            log_dict["employee_code"] = None
            log_dict["position"] = None
            log_dict["department"] = None
            log_dict["notes"] = None
            log_dict["employee_object"] = None  # Add employee_object

        enriched_logs.append(log_dict)

    return enriched_logs


@bp.route("/attendance", methods=["GET"])
def get_attendance():
    """Get stored attendance logs with pagination and filtering"""
    try:
        # Query parameters
        device_id = request.args.get("device_id")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        user_id = request.args.get("user_id")
        date_str = request.args.get("date")  # Format: YYYY-MM-DD

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        # Parse date if provided
        start_date = None
        end_date = None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_date = datetime.combine(target_date, datetime.min.time())
                end_date = datetime.combine(target_date, datetime.max.time())
            except ValueError:
                return jsonify(
                    {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
                ), 400

        if user_id:
            logs = attendance_repo.get_by_user(user_id, limit)
        else:
            logs = attendance_repo.get_all(
                device_id, limit, offset, start_date, end_date
            )

        data = _map_user_details_to_logs(logs)

        return jsonify(
            {
                "success": True,
                "data": data,
                "pagination": {"limit": limit, "offset": offset, "count": len(logs)},
            }
        )

    except Exception as e:
        app_logger.error(f"Error getting attendance logs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/sync", methods=["POST"])
def sync_attendance():
    """Sync attendance logs from device to database"""
    try:
        app_logger.info("Syncing attendance from device")
        result = get_service().get_attendance()

        if isinstance(result, dict) and "records" in result:
            attendances = result["records"]
            sync_stats = result.get("sync_stats", {})
        else:
            attendances = result
            sync_stats = None

        if not attendances:
            return jsonify(
                {
                    "message": "Không có dữ liệu chấm công mới trên thiết bị",
                    "data": [],
                    "sync_stats": sync_stats,
                }
            )

        # The get_attendance service already saves to DB, so we just return the stats
        response = {
            "message": "Đồng bộ dữ liệu chấm công thành công",
            "sync_stats": sync_stats,
        }

        return jsonify(response)
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ dữ liệu chấm công: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500


# Sync Management APIs


@bp.route("/attendance/logs", methods=["GET"])
def get_attendance_logs():
    """Get stored attendance logs with pagination and filtering"""
    try:
        from datetime import datetime

        # Query parameters
        device_id = request.args.get("device_id")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        user_id = request.args.get("user_id")
        date_str = request.args.get("date")  # Format: YYYY-MM-DD

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        # Parse date filter if provided
        target_date = None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify(
                    {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
                ), 400

        if user_id:
            logs = attendance_repo.get_by_user(user_id, limit)
        elif target_date:
            # Get logs filtered by date
            logs = attendance_repo.get_by_date(target_date, device_id, limit, offset)
        else:
            logs = attendance_repo.get_all(device_id, limit, offset)

        data = _map_user_details_to_logs(logs)

        # Get total count for proper pagination
        if target_date:
            total_count = attendance_repo.get_count_by_date(target_date, device_id)
        else:
            total_count = attendance_repo.get_total_count(device_id)

        return jsonify(
            {
                "success": True,
                "data": data,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(logs),
                    "total_count": total_count,
                },
                "date": date_str,
            }
        )

    except Exception as e:
        app_logger.error(f"Error getting attendance logs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/unsynced", methods=["GET"])
def get_unsynced_logs():
    """Get attendance logs that haven't been synced to external system"""
    try:
        device_id = request.args.get("device_id")
        limit = int(request.args.get("limit", 1000))

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        logs = attendance_repo.get_unsynced_logs(device_id, limit)

        return jsonify(
            {
                "success": True,
                "data": [log.to_dict() for log in logs],
                "count": len(logs),
            }
        )

    except Exception as e:
        app_logger.error(f"Error getting unsynced logs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/<int:log_id>/sync", methods=["PUT"])
def mark_log_as_synced(log_id: int):
    """Mark a specific attendance log as synced"""
    try:
        success = attendance_repo.mark_as_synced(log_id)

        if success:
            app_logger.info(f"Marked attendance log {log_id} as synced")
            return jsonify(
                {
                    "success": True,
                    "message": f"Attendance log {log_id} marked as synced",
                    "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Attendance log {log_id} not found or already synced",
                }
            ), 404

    except Exception as e:
        app_logger.error(f"Error marking log {log_id} as synced: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/sync/batch", methods=["PUT"])
def mark_multiple_as_synced():
    """Mark multiple attendance logs as synced"""
    try:
        data = request.get_json()
        if not data or "log_ids" not in data:
            return jsonify(
                {"success": False, "error": "log_ids array is required in request body"}
            ), 400

        log_ids = data["log_ids"]
        if not isinstance(log_ids, list):
            return jsonify({"success": False, "error": "log_ids must be an array"}), 400

        synced_count = 0
        failed_ids = []

        for log_id in log_ids:
            try:
                if attendance_repo.mark_as_synced(int(log_id)):
                    synced_count += 1
                else:
                    failed_ids.append(log_id)
            except Exception as e:
                app_logger.error(f"Error syncing log {log_id}: {e}")
                failed_ids.append(log_id)

        app_logger.info(
            f"Batch sync completed: {synced_count} synced, {len(failed_ids)} failed"
        )

        return jsonify(
            {
                "success": True,
                "synced_count": synced_count,
                "failed_count": len(failed_ids),
                "failed_ids": failed_ids,
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    except Exception as e:
        app_logger.error(f"Error in batch sync: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/stats", methods=["GET"])
def get_sync_stats():
    """Get sync statistics for attendance logs"""
    try:
        device_id = request.args.get("device_id")
        stats = attendance_repo.get_sync_stats(device_id)

        return jsonify({"success": True, "stats": stats, "device_id": device_id})

    except Exception as e:
        app_logger.error(f"Error getting sync stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Daily Attendance Sync APIs


@bp.route("/attendance/sync-daily", methods=["POST"])
def sync_daily_attendance():
    """Sync daily attendance data with first checkin/last checkout logic"""
    try:
        data = request.get_json() or {}
        target_date = data.get("date")  # Optional: YYYY-MM-DD format
        device_id = data.get("device_id")  # Optional: specific device

        app_logger.info(
            f"Manual daily attendance sync triggered for date: {target_date or 'today'}, device: {device_id or 'all'}"
        )

        result = attendance_sync_service.sync_attendance_daily(
            target_date, device_id, ignore_error_limit=True
        )

        if result["success"]:
            dates_processed = result.get("dates_processed", [])
            date_info = (
                f"{len(dates_processed)} dates"
                if len(dates_processed) > 1
                else (dates_processed[0] if dates_processed else "today")
            )
            return jsonify(
                {
                    "success": True,
                    "message": f"Daily attendance sync completed for {date_info}",
                    "data": result,
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": result.get("error"),
                    "dates_processed": result.get("dates_processed", []),
                }
            ), 500

    except Exception as e:
        app_logger.error(f"Error in sync_daily_attendance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/daily-preview", methods=["GET"])
def preview_daily_attendance():
    """Preview daily attendance data without sending to external API"""
    try:
        target_date = request.args.get("date")  # Optional: YYYY-MM-DD format
        device_id = request.args.get("device_id")  # Optional: specific device

        result = attendance_sync_service.get_daily_attendance_preview(
            target_date, device_id
        )

        return jsonify(result)

    except Exception as e:
        app_logger.error(f"Error in preview_daily_attendance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Scheduler Management APIs


@bp.route("/attendance/scheduler/status", methods=["GET"])
def get_scheduler_status():
    """Get scheduler status and job information"""
    try:
        status = scheduler_service.get_all_jobs()
        return jsonify({"success": True, "scheduler": status})

    except Exception as e:
        app_logger.error(f"Error getting scheduler status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/scheduler/trigger", methods=["POST"])
def trigger_scheduler_job():
    """Manually trigger the daily attendance sync job"""
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id", "daily_attendance_sync")

        app_logger.info(f"Manual trigger requested for job: {job_id}")

        result = scheduler_service.trigger_job_manually(job_id)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "message": result.get("message"),
                    "data": result.get("result"),
                }
            )
        else:
            return jsonify({"success": False, "error": result.get("error")}), 500

    except Exception as e:
        app_logger.error(f"Error triggering scheduler job: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/history", methods=["GET"])
def get_attendance_history():
    """Get attendance history with smart filtering (first checkin/last checkout or synced records)

    Logic:
    - Group by user + date
    - For each group:
      - If checkin has synced record, use it; else use first checkin
      - If checkout has synced record, use it; else use last checkout
    """
    try:
        from datetime import datetime

        # Query parameters
        device_id = request.args.get("device_id")
        date_str = request.args.get("date")  # Format: YYYY-MM-DD

        # Parse date or default to today
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify(
                    {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
                ), 400
        else:
            target_date = datetime.now().date()

        # Get filtered logs from repository
        filtered_logs = attendance_repo.get_smart_filtered_by_date(
            target_date, device_id
        )

        # Map user names and avatars
        data = _map_user_details_to_logs(filtered_logs)

        return jsonify(
            {
                "success": True,
                "data": data,
                "date": target_date.strftime("%Y-%m-%d"),
                "count": len(data),
                "device_id": device_id,
            }
        )

    except Exception as e:
        app_logger.error(f"Error getting attendance history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Cleanup Management APIs


@bp.route("/attendance/cleanup/preview", methods=["GET"])
def preview_cleanup():
    """Preview what would be deleted in cleanup without actually deleting"""
    try:
        # Get retention days from query parameter (default: 365 = 1 year)
        retention_days = int(request.args.get("retention_days", 365))

        # Validate retention period
        if retention_days < 30:
            return jsonify(
                {
                    "success": False,
                    "error": "Retention period must be at least 30 days for safety",
                }
            ), 400

        result = attendance_cleanup_service.get_cleanup_preview(retention_days)

        return jsonify(result)

    except ValueError:
        return jsonify(
            {
                "success": False,
                "error": "Invalid retention_days parameter. Must be an integer.",
            }
        ), 400
    except Exception as e:
        app_logger.error(f"Error previewing cleanup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/attendance/cleanup", methods=["POST"])
def cleanup_old_attendance():
    """Delete old synced and skipped attendance records

    Only deletes records with sync_status = 'synced' or 'skipped'.
    NEVER deletes 'pending' records to prevent data loss.
    """
    try:
        data = request.get_json() or {}

        # Get retention days from request body (default: 365 = 1 year)
        retention_days = data.get("retention_days", 365)

        # Validate retention period
        if retention_days < 30:
            return jsonify(
                {
                    "success": False,
                    "error": "Retention period must be at least 30 days for safety",
                }
            ), 400

        # Require explicit confirmation for safety
        confirmed = data.get("confirmed", False)
        if not confirmed:
            return jsonify(
                {
                    "success": False,
                    "error": 'Cleanup requires explicit confirmation. Set "confirmed": true in request body.',
                }
            ), 400

        app_logger.info(f"Manual cleanup triggered: retention_days={retention_days}")

        result = attendance_cleanup_service.cleanup_old_attendance(retention_days)

        if result["success"]:
            return jsonify(
                {"success": True, "message": result["message"], "data": result}
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": result.get("error"),
                    "message": result.get("message"),
                }
            ), 500

    except Exception as e:
        app_logger.error(f"Error in cleanup_old_attendance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

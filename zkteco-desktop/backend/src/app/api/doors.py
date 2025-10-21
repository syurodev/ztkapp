"""
Door API endpoints
"""

from flask import Blueprint, jsonify, request
from app.shared.logger import app_logger
from app.services.door_service import door_service


bp = Blueprint("doors", __name__, url_prefix="/doors")


@bp.route("", methods=["GET"])
def get_all_doors():
    """Get all doors"""
    try:
        doors = door_service.get_all_doors()
        return jsonify({"success": True, "data": [door.to_dict() for door in doors]})
    except Exception as e:
        app_logger.error(f"Error getting doors: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy danh sách cửa: {str(e)}"}
        ), 500


@bp.route("/<int:door_id>", methods=["GET"])
def get_door(door_id):
    """Get door by ID"""
    try:
        door = door_service.get_door(door_id)
        if not door:
            return jsonify(
                {"success": False, "message": f"Không tìm thấy cửa với ID {door_id}"}
            ), 404

        return jsonify({"success": True, "data": door.to_dict()})
    except Exception as e:
        app_logger.error(f"Error getting door {door_id}: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy thông tin cửa: {str(e)}"}
        ), 500


@bp.route("", methods=["POST"])
def create_door():
    """Create new door"""
    try:
        data = request.json

        # Validate required fields
        if not data.get("name"):
            return jsonify(
                {"success": False, "message": "Tên cửa không được để trống"}
            ), 400

        # device_id is now optional - can be assigned later

        door = door_service.create_door(data)

        return jsonify(
            {"success": True, "message": "Tạo cửa thành công", "data": door.to_dict()}
        ), 201

    except Exception as e:
        app_logger.error(f"Error creating door: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi khi tạo cửa: {str(e)}"}), 500


@bp.route("/<int:door_id>", methods=["PUT"])
def update_door(door_id):
    """Update door"""
    try:
        data = request.json

        # Check if door exists
        door = door_service.get_door(door_id)
        if not door:
            return jsonify(
                {"success": False, "message": f"Không tìm thấy cửa với ID {door_id}"}
            ), 404

        # Remove fields that shouldn't be updated directly
        updates = {k: v for k, v in data.items() if k not in ["id", "created_at"]}

        success = door_service.update_door(door_id, updates)

        if success:
            updated_door = door_service.get_door(door_id)
            try:
                door_service.sync_single_door(updated_door)
            except Exception as e:
                app_logger.warning(
                    f"Failed to sync door {door_id} to external API after update: {e}"
                )

            return jsonify(
                {
                    "success": True,
                    "message": "Cập nhật cửa thành công",
                    "data": updated_door.to_dict(),
                }
            )
        else:
            return jsonify({"success": False, "message": "Không thể cập nhật cửa"}), 500

    except Exception as e:
        app_logger.error(f"Error updating door {door_id}: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi cập nhật cửa: {str(e)}"}
        ), 500


@bp.route("/<int:door_id>", methods=["DELETE"])
def delete_door(door_id):
    """Delete door"""
    try:
        # Check if door exists
        door = door_service.get_door(door_id)
        if not door:
            return jsonify(
                {"success": False, "message": f"Không tìm thấy cửa với ID {door_id}"}
            ), 404

        success = door_service.delete_door(door_id)

        if success:
            return jsonify({"success": True, "message": "Xóa cửa thành công"})
        else:
            return jsonify({"success": False, "message": "Không thể xóa cửa"}), 500

    except Exception as e:
        app_logger.error(f"Error deleting door {door_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi khi xóa cửa: {str(e)}"}), 500


@bp.route("/<int:door_id>/unlock", methods=["POST"])
def unlock_door(door_id):
    """Unlock door"""
    try:
        data = request.json or {}
        duration = data.get("duration", 3)  # Default 3 seconds
        user_id = data.get("user_id")
        user_name = data.get("user_name")

        # Validate duration
        if not isinstance(duration, int) or duration < 1 or duration > 60:
            return jsonify(
                {"success": False, "message": "Thời gian mở cửa phải từ 1-60 giây"}
            ), 400

        result = door_service.unlock_door(
            door_id=door_id, duration=duration, user_id=user_id, user_name=user_name
        )

        return jsonify({"success": True, "message": result["message"], "data": result})

    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        app_logger.error(f"Error unlocking door {door_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi khi mở cửa: {str(e)}"}), 500


@bp.route("/<int:door_id>/state", methods=["GET"])
def get_door_state(door_id):
    """Get door state"""
    try:
        state = door_service.get_door_state(door_id)
        return jsonify({"success": True, "data": state})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        app_logger.error(f"Error getting door state {door_id}: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy trạng thái cửa: {str(e)}"}
        ), 500


@bp.route("/<int:door_id>/access-logs", methods=["GET"])
def get_door_access_logs(door_id):
    """Get access logs for a door"""
    try:
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        logs = door_service.get_access_logs(door_id=door_id, limit=limit, offset=offset)

        return jsonify({"success": True, "data": [log.to_dict() for log in logs]})
    except Exception as e:
        app_logger.error(
            f"Error getting access logs for door {door_id}: {e}", exc_info=True
        )
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy nhật ký truy cập: {str(e)}"}
        ), 500


@bp.route("/device/<int:device_id>", methods=["GET"])
def get_doors_by_device(device_id):
    """Get all doors for a device"""
    try:
        doors = door_service.get_doors_by_device(device_id)
        return jsonify({"success": True, "data": [door.to_dict() for door in doors]})
    except Exception as e:
        app_logger.error(
            f"Error getting doors for device {device_id}: {e}", exc_info=True
        )
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy danh sách cửa: {str(e)}"}
        ), 500


@bp.route("/<int:door_id>/sync-from-attendance", methods=["POST"])
def sync_door_logs_from_attendance(door_id):
    """Sync attendance logs to this door's access logs"""
    try:
        new_logs_count = door_service.sync_logs_from_attendance(door_id)
        return jsonify(
            {
                "success": True,
                "message": f"Successfully synced {new_logs_count} new logs from attendance records.",
                "new_logs_count": new_logs_count,
            }
        )
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        app_logger.error(
            f"Error syncing attendance logs for door {door_id}: {e}", exc_info=True
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"An error occurred during sync: {str(e)}",
                }
            ),
            500,
        )


@bp.route("/access-logs", methods=["GET"])
def get_all_access_logs():
    """Get all access logs with optional filters"""
    try:
        user_id = request.args.get("user_id", type=int)
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        logs = door_service.get_access_logs(user_id=user_id, limit=limit, offset=offset)

        return jsonify({"success": True, "data": [log.to_dict() for log in logs]})
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Lỗi khi lấy nhật ký truy cập: {str(e)}"}
        ), 500


@bp.route("/sync-external", methods=["POST"])
def sync_doors_to_external_api():
    """Sync all doors to external API"""
    app_logger.info("Received request to sync all doors to external API")
    try:
        result = door_service.sync_doors_to_external_api()
        return jsonify(result)
    except Exception as e:
        app_logger.error(f"Error syncing doors to external API: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi đồng bộ cửa: {str(e)}"}
        ), 500


@bp.route("/access-logs/sync", methods=["POST"])
def sync_door_access_logs():
    """
    Manually trigger door access logs sync to external API

    Request body (optional):
        {
            "date": "2025-10-20"  # Target date in YYYY-MM-DD format (default: today)
        }
    """
    try:
        data = request.json or {}
        target_date = data.get("date")  # Optional, defaults to today in service

        app_logger.info(
            f"Manual door access sync triggered for date: {target_date or 'today'}"
        )

        # Import service
        from app.services.door_access_sync_service import door_access_sync_service

        # Trigger sync
        result = door_access_sync_service.sync_daily_door_access(target_date)

        if result.get("success"):
            synced_count = result.get("synced_logs", 0)
            total_count = result.get("count", 0)
            sync_date = result.get("date")

            message = f"Đã đồng bộ {synced_count} log ({total_count} records) cho ngày {sync_date}"

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "data": {
                        "synced_logs": synced_count,
                        "aggregated_records": total_count,
                        "date": sync_date,
                    },
                }
            )
        else:
            error_msg = result.get("error", "Unknown error")
            app_logger.error(f"Door access sync failed: {error_msg}")

            return jsonify(
                {
                    "success": False,
                    "message": f"Lỗi đồng bộ: {error_msg}",
                    "error": error_msg,
                }
            ), 500

    except Exception as e:
        app_logger.error(f"Error in manual door access sync: {e}", exc_info=True)
        return jsonify(
            {"success": False, "message": f"Lỗi khi đồng bộ log mở cửa: {str(e)}"}
        ), 500

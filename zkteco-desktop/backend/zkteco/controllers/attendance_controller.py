from zkteco.logger import app_logger

from flask import Blueprint, jsonify
from zkteco.services.zk_service import get_zk_service
from flask import current_app

bp = Blueprint('attendance', __name__, url_prefix='/')

def get_service():
    return get_zk_service()

def serialize_attendance(attendance):
    return {
        "user_id": attendance.user_id,
        "timestamp": attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        "status": attendance.status,
        "punch": attendance.punch,
        "uid": attendance.uid,
    }

@bp.route('/attendance', methods=['GET'])
def get_attendance():
    try:
        app_logger.info("Retrieving attendance")
        attendances = get_service().get_attendance()
        if not attendances:
            return jsonify({"message": "No attendance records found", "data": []})

        serialized_attendances = [serialize_attendance(att) for att in attendances]
        return jsonify({"message": "Attendance retrieved successfully", "data": serialized_attendances})
    except Exception as e:
        error_message = f"Error retrieving attendance: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500

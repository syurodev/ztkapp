from zkteco.logger import app_logger

from flask import Blueprint, jsonify, request
from zkteco.services.zk_service import get_zk_service
from zkteco.database.models import attendance_repo, user_repo
from flask import current_app
from datetime import datetime

bp = Blueprint('attendance', __name__, url_prefix='/')

def get_service():
    return get_zk_service()

def _map_user_names_to_logs(logs):
    """Helper function to map user names to attendance logs."""
    user_ids = {log.user_id for log in logs}
    users = user_repo.get_all()
    user_map = {user.user_id: user.name for user in users}

    logs_with_names = []
    for log in logs:
        log_dict = log.to_dict()
        log_dict['name'] = user_map.get(log.user_id, 'Unknown User')
        logs_with_names.append(log_dict)
    return logs_with_names

@bp.route('/attendance', methods=['GET'])
def get_attendance():
    """Get stored attendance logs with pagination and filtering"""
    try:
        # Query parameters
        device_id = request.args.get('device_id')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        user_id = request.args.get('user_id')

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        if user_id:
            logs = attendance_repo.get_by_user(user_id, limit)
        else:
            logs = attendance_repo.get_all(device_id, limit, offset)

        data = _map_user_names_to_logs(logs)

        return jsonify({
            'success': True,
            'data': data,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(logs)
            }
        })

    except Exception as e:
        app_logger.error(f"Error getting attendance logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/attendance/sync', methods=['POST'])
def sync_attendance():
    """Sync attendance logs from device to database"""
    try:
        app_logger.info("Syncing attendance from device")
        result = get_service().get_attendance()

        if isinstance(result, dict) and 'records' in result:
            attendances = result['records']
            sync_stats = result.get('sync_stats', {})
        else:
            attendances = result
            sync_stats = None

        if not attendances:
            return jsonify({
                "message": "No new attendance records found on device",
                "data": [],
                "sync_stats": sync_stats
            })

        # The get_attendance service already saves to DB, so we just return the stats
        response = {
            "message": "Attendance synced successfully",
            "sync_stats": sync_stats
        }

        return jsonify(response)
    except Exception as e:
        error_message = f"Error syncing attendance: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500

# Sync Management APIs

@bp.route('/attendance/logs', methods=['GET'])
def get_attendance_logs():
    """Get stored attendance logs with pagination and filtering"""
    try:
        # Query parameters
        device_id = request.args.get('device_id')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        user_id = request.args.get('user_id')

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        if user_id:
            logs = attendance_repo.get_by_user(user_id, limit)
        else:
            logs = attendance_repo.get_all(device_id, limit, offset)

        data = _map_user_names_to_logs(logs)

        # Get total count for proper pagination
        total_count = attendance_repo.get_total_count(device_id)

        return jsonify({
            'success': True,
            'data': data,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(logs),
                'total_count': total_count
            }
        })

    except Exception as e:
        app_logger.error(f"Error getting attendance logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/attendance/unsynced', methods=['GET'])
def get_unsynced_logs():
    """Get attendance logs that haven't been synced to external system"""
    try:
        device_id = request.args.get('device_id')
        limit = int(request.args.get('limit', 1000))

        # Validate limit
        limit = min(limit, 1000)  # Max 1000 records per request

        logs = attendance_repo.get_unsynced_logs(device_id, limit)

        return jsonify({
            'success': True,
            'data': [log.to_dict() for log in logs],
            'count': len(logs)
        })

    except Exception as e:
        app_logger.error(f"Error getting unsynced logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/attendance/<int:log_id>/sync', methods=['PUT'])
def mark_log_as_synced(log_id: int):
    """Mark a specific attendance log as synced"""
    try:
        success = attendance_repo.mark_as_synced(log_id)

        if success:
            app_logger.info(f"Marked attendance log {log_id} as synced")
            return jsonify({
                'success': True,
                'message': f'Attendance log {log_id} marked as synced',
                'synced_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Attendance log {log_id} not found or already synced'
            }), 404

    except Exception as e:
        app_logger.error(f"Error marking log {log_id} as synced: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/attendance/sync/batch', methods=['PUT'])
def mark_multiple_as_synced():
    """Mark multiple attendance logs as synced"""
    try:
        data = request.get_json()
        if not data or 'log_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'log_ids array is required in request body'
            }), 400

        log_ids = data['log_ids']
        if not isinstance(log_ids, list):
            return jsonify({
                'success': False,
                'error': 'log_ids must be an array'
            }), 400

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

        app_logger.info(f"Batch sync completed: {synced_count} synced, {len(failed_ids)} failed")

        return jsonify({
            'success': True,
            'synced_count': synced_count,
            'failed_count': len(failed_ids),
            'failed_ids': failed_ids,
            'synced_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        app_logger.error(f"Error in batch sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/attendance/stats', methods=['GET'])
def get_sync_stats():
    """Get sync statistics for attendance logs"""
    try:
        device_id = request.args.get('device_id')
        stats = attendance_repo.get_sync_stats(device_id)

        return jsonify({
            'success': True,
            'stats': stats,
            'device_id': device_id
        })

    except Exception as e:
        app_logger.error(f"Error getting sync stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

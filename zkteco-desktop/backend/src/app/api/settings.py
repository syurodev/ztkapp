from flask import Blueprint, jsonify, request
from app.repositories.setting_repository import setting_repo
from app.shared.logger import app_logger

bp = Blueprint('settings', __name__, url_prefix='/')

@bp.route('/settings', methods=['GET'])
def get_all_settings():
    """Get all application settings"""
    try:
        settings = setting_repo.get_all()

        # Get full setting objects with descriptions
        settings_with_details = []
        for key in settings.keys():
            setting = setting_repo.get(key)
            if setting:
                settings_with_details.append({
                    'key': setting.key,
                    'value': setting.value,
                    'description': setting.description
                })

        return jsonify({
            'success': True,
            'data': settings_with_details
        })

    except Exception as e:
        app_logger.error(f"Error getting settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/settings/<key>', methods=['GET'])
def get_setting(key: str):
    """Get a specific setting by key"""
    try:
        setting = setting_repo.get(key)

        # If not found, return success with a null value
        if not setting:
            return jsonify({
                'success': True,
                'data': {
                    'key': key,
                    'value': None,
                    'description': None
                }
            })

        return jsonify({
            'success': True,
            'data': {
                'key': setting.key,
                'value': setting.value,
                'description': setting.description
            }
        })

    except Exception as e:
        app_logger.error(f"Error getting setting {key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/settings/<key>', methods=['PUT'])
def update_setting(key: str):
    """Update a setting value"""
    try:
        data = request.get_json()

        if not data or 'value' not in data:
            return jsonify({
                'success': False,
                'error': 'value is required in request body'
            }), 400

        value = str(data['value'])
        description = data.get('description')

        # Validate cleanup_retention_days
        if key == 'cleanup_retention_days':
            try:
                retention_days = int(value)
                if retention_days < 30:
                    return jsonify({
                        'success': False,
                        'error': 'Ngày lưu trử phải ít nhất là 30 ngày'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'cleanup_retention_days must be a valid integer'
                }), 400

        # Validate cleanup_enabled
        if key == 'cleanup_enabled':
            if value.lower() not in ['true', 'false']:
                return jsonify({
                    'success': False,
                    'error': 'cleanup_enabled must be "true" or "false"'
                }), 400

        success = setting_repo.set(key, value, description)

        if success:
            app_logger.info(f"Setting {key} updated to {value}")
            return jsonify({
                'success': True,
                'message': f'Setting {key} updated successfully',
                'data': {
                    'key': key,
                    'value': value,
                    'description': description
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update setting'
            }), 500

    except Exception as e:
        app_logger.error(f"Error updating setting {key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/settings/cleanup/config', methods=['GET'])
def get_cleanup_config():
    """Get cleanup configuration with parsed values"""
    try:
        retention_setting = setting_repo.get('cleanup_retention_days')
        enabled_setting = setting_repo.get('cleanup_enabled')

        retention_days = int(retention_setting.value) if retention_setting else 365
        enabled = enabled_setting.value.lower() == 'true' if enabled_setting else True

        return jsonify({
            'success': True,
            'data': {
                'retention_days': retention_days,
                'enabled': enabled,
                'retention_description': retention_setting.description if retention_setting else None,
                'enabled_description': enabled_setting.description if enabled_setting else None
            }
        })

    except Exception as e:
        app_logger.error(f"Error getting cleanup config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/settings/cleanup/config', methods=['PUT'])
def update_cleanup_config():
    """Update cleanup configuration"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400

        updated = {}

        # Update retention_days if provided
        if 'retention_days' in data:
            retention_days = int(data['retention_days'])
            if retention_days < 30:
                return jsonify({
                    'success': False,
                    'error': 'Ngày lưu trử phải ít nhất là 30 ngày'
                }), 400

            setting_repo.set(
                'cleanup_retention_days',
                str(retention_days),
                'Number of days to retain attendance records before cleanup'
            )
            updated['retention_days'] = retention_days
            app_logger.info(f"Cleanup retention days updated to {retention_days}")

        # Update enabled if provided
        if 'enabled' in data:
            enabled = bool(data['enabled'])
            setting_repo.set(
                'cleanup_enabled',
                'true' if enabled else 'false',
                'Enable/disable automatic monthly cleanup of old attendance records'
            )
            updated['enabled'] = enabled
            app_logger.info(f"Cleanup enabled set to {enabled}")

        if not updated:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update (retention_days or enabled)'
            }), 400

        return jsonify({
            'success': True,
            'message': 'Cleanup configuration updated successfully',
            'data': updated
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid value: {str(e)}'
        }), 400
    except Exception as e:
        app_logger.error(f"Error updating cleanup config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

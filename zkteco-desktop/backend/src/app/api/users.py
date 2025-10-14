from flask import Blueprint, request, jsonify, Response
from app.services.device_service import get_zk_service
from app.schemas import create_user_schema, delete_user_schema, get_fingerprint_schema, delete_fingerprint_schema, validate_data
from flask import current_app
from app.models import User
from app.repositories import user_repo
from app.config.config_manager import config_manager
from app.device.connection_manager import connection_manager
import time
import requests
import json
from datetime import datetime
from app.services.external_api_service import external_api_service
from typing import Optional

PROFILE_COPY_FIELDS = ("full_name", "employee_code", "position", "department", "employee_object")
OPTIONAL_PROFILE_COPY_FIELDS = ("avatar_url", "external_user_id", "synced_at")

bp = Blueprint('user', __name__, url_prefix='/')
# zk_service = get_zk_service()  # Lazy load to avoid blocking

def get_service():
    return get_zk_service()

def _collect_profile_fields(source_user, include_optional: bool = False):
    if not source_user:
        return {}

    fields = PROFILE_COPY_FIELDS + OPTIONAL_PROFILE_COPY_FIELDS if include_optional else PROFILE_COPY_FIELDS
    profile = {}
    for field in fields:
        value = getattr(source_user, field, None)
        if value not in (None, ""):
            profile[field] = value
    return profile

def _derive_external_user_id(user_id: str) -> Optional[int]:
    if user_id is None:
        return None
    try:
        return int(str(user_id).strip())
    except (TypeError, ValueError):
        return None

def sync_users_from_device(device_id=None):
    """
    Sync users from device to database (only for pull devices)
    Returns tuple: (success, synced_count, error_message)
    """
    try:
        active_device = config_manager.get_active_device() if not device_id else config_manager.get_device(device_id)
        if not active_device:
            return False, 0, "No active device found"

        target_device_id = device_id or active_device['id']

        # Check device type - skip sync for push devices (they push data automatically)
        device_type = active_device.get('device_type', 'pull')
        if device_type == 'push':
            current_app.logger.info(f"Device {target_device_id} is push type, skipping user sync from device (push devices send data automatically)")
            # Return success with 0 synced users (not an error) because push devices work differently
            return True, 0, None

        current_app.logger.info(f"Syncing users from pull device {target_device_id}")

        # Configure device in connection manager if not already configured
        device_config = {
            'ip': active_device.get('ip'),
            'port': active_device.get('port'),
            'password': active_device.get('password'),
            'timeout': active_device.get('timeout'),
            'force_udp': active_device.get('force_udp'),
            'verbose': False,
            'retry_count': active_device.get('retry_count'),
            'retry_delay': active_device.get('retry_delay'),
            'ping_interval': active_device.get('ping_interval')
        }
        connection_manager.configure_device(target_device_id, device_config)

        # Try to connect to device
        zk_connection = connection_manager.ensure_device_connection(target_device_id)
        if not zk_connection or not zk_connection.is_connect:
            current_app.logger.warning(f"Cannot connect to device {target_device_id}")
            return False, 0, f"Cannot connect to device {active_device.get('name', target_device_id)}"
        
        # Get users from device
        current_app.logger.info("Getting users from device...")
        device_users = zk_connection.get_users()
        
        if not device_users:
            current_app.logger.info("No users found in device")
            return True, 0, None
        
        synced_count = 0
        updated_count = 0

        for device_user in device_users:
            try:
                # Get device serial_number for tracking
                device_serial = active_device.get('serial_number')
                if not device_serial:
                    # Fallback to device_info if serial_number column is empty
                    device_info = active_device.get('device_info', {})
                    device_serial = device_info.get('serial_number') if device_info else None

                # Check if user already exists in database
                existing_user = user_repo.get_by_user_id(str(device_user.user_id), target_device_id)

                source_user = user_repo.find_first_by_user_id(
                    str(device_user.user_id),
                    exclude_device_id=target_device_id,
                )
                profile_payload = _collect_profile_fields(source_user, include_optional=True)
                synced_at_copy = profile_payload.pop(
                    "synced_at",
                    getattr(source_user, "synced_at", None) if source_user else None,
                )

                if existing_user:
                    # Update existing user with latest info from device
                    updates = {
                        'name': device_user.name or existing_user.name,
                        'privilege': getattr(device_user, 'privilege', existing_user.privilege),
                        'group_id': getattr(device_user, 'group_id', existing_user.group_id),
                        'card': getattr(device_user, 'card', existing_user.card),
                        'password': getattr(device_user, 'password', existing_user.password),
                        'serial_number': device_serial,
                    }

                    # Pull profile fields from reference device
                    for field, value in profile_payload.items():
                        if getattr(existing_user, field) != value:
                            updates[field] = value

                    if source_user:
                        if not existing_user.is_synced:
                            updates['is_synced'] = True
                        if synced_at_copy and getattr(existing_user, 'synced_at', None) != synced_at_copy:
                            updates['synced_at'] = synced_at_copy

                    # Check if any field changed
                    has_changes = any(
                        getattr(existing_user, key) != value
                        for key, value in updates.items()
                    )

                    if has_changes:
                        user_repo.update(existing_user.id, updates)
                        updated_count += 1
                        current_app.logger.info(f"Updated user {device_user.user_id}: {device_user.name}")
                    else:
                        current_app.logger.debug(f"User {device_user.user_id} already up-to-date, skipping...")
                    continue

                # Logic to copy data from another device if user_id exists elsewhere
                if source_user:
                    current_app.logger.info(f"Found existing user with same ID on another device. Copying data from {source_user.device_id}.")

                is_synced_flag = True if source_user else False

                if not source_user:
                    fallback_external_id = _derive_external_user_id(device_user.user_id)
                    if fallback_external_id is not None:
                        profile_payload.setdefault('external_user_id', fallback_external_id)

                # Create new user in database
                user = User(
                    user_id=str(device_user.user_id),
                    name=device_user.name or f"User {device_user.user_id}",
                    device_id=target_device_id,
                    serial_number=device_serial,
                    privilege=getattr(device_user, 'privilege', 0),
                    group_id=getattr(device_user, 'group_id', 0),
                    card=getattr(device_user, 'card', 0),
                    password=getattr(device_user, 'password', ''),
                    is_synced=is_synced_flag,
                    synced_at=synced_at_copy,
                    **profile_payload
                )

                created_user = user_repo.create(user)
                if created_user:
                    synced_count += 1
                    current_app.logger.info(f"Created user {device_user.user_id}: {device_user.name}")

            except Exception as user_error:
                current_app.logger.error(f"Error syncing user {device_user.user_id}: {user_error}")
                continue
        
        current_app.logger.info(f"Sync completed: {synced_count} new users created, {updated_count} users updated")
        return True, synced_count, None
        
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ người dùng từ thiết bị: {str(e)}"
        current_app.logger.error(error_message)
        return False, 0, error_message

@bp.route('/user', methods=['POST'])
def create_user():
    data = request.json

    # Validate against the create user schema
    error = validate_data(data, create_user_schema.schema)
    if error:
        return jsonify({"error": error}), 400

    try:
        user_id = data.get('user_id')
        user_data = data.get('user_data')

        current_app.logger.info(f"Creating user with ID: {user_id} and Data: {user_data}")
    
        get_service().create_user(user_id, user_data)
        return jsonify({"message": "Thêm người dùng thành công"})
    except Exception as e:
        error_message = f"Lỗi khi tạo người dùng: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500

def serialize_user(user):
    return {
        "id": user.user_id,
        "name": user.name,
        "groupId": user.group_id
    }

def serialize_template(template):
    return {
        "id": template.uid,
        "fid": template.fid,
        "valid": template.valid,
        "template": template.template.decode('utf-8', errors='ignore'),
    }

@bp.route('/users', methods=['GET'])
def get_all_users():
    start_time = time.time()
    current_app.logger.info("[DEBUG] Starting get_all_users API call with database sync")
    
    try:
        # First try to sync users from device
        current_app.logger.info("[DEBUG] Attempting to sync users from device...")
        sync_start = time.time()
        
        sync_success, synced_count, sync_error = sync_users_from_device()
        sync_end = time.time()
        
        if sync_success:
            current_app.logger.info(f"[DEBUG] Device sync completed in {sync_end - sync_start:.2f} seconds, synced {synced_count} new users")
        else:
            current_app.logger.warning(f"[DEBUG] Device sync failed in {sync_end - sync_start:.2f} seconds: {sync_error}")
            current_app.logger.info("[DEBUG] Falling back to database users only")
        
        # Get users from database (whether sync worked or not)
        current_app.logger.info("[DEBUG] Retrieving users from database...")
        db_start = time.time()
        
        # Get active device to filter users
        active_device = config_manager.get_active_device()
        device_id = active_device['id'] if active_device else None
        
        db_users = user_repo.get_all(device_id=device_id)
        db_end = time.time()
        current_app.logger.info(f"[DEBUG] Database query completed in {db_end - db_start:.2f} seconds")
        
        if not db_users:
            current_app.logger.info("[DEBUG] No users found in database")
            message = "Không tìm thấy người dùng nào"
            if sync_error:
                message += f" (Đồng bộ với thiết bị thất bại: {sync_error})"
            return jsonify({"message": message, "data": [], "sync_status": {"success": sync_success, "synced_count": synced_count, "error": sync_error}})
        
        current_app.logger.info(f"[DEBUG] Found {len(db_users)} users in database, starting serialization")
        serialize_start = time.time()
        
        # Serialize database users to match frontend format
        serialized_users = []
        for user in db_users:
            # Handle datetime fields safely
            synced_at = None
            if user.synced_at:
                if hasattr(user.synced_at, 'isoformat'):
                    synced_at = user.synced_at.isoformat()
                else:
                    synced_at = str(user.synced_at)
            
            created_at = None
            if user.created_at:
                if hasattr(user.created_at, 'isoformat'):
                    created_at = user.created_at.isoformat()
                else:
                    created_at = str(user.created_at)
            
            serialized_users.append({
                "id": user.user_id,
                "name": user.name,
                "full_name": user.full_name,
                "groupId": user.group_id,
                "privilege": user.privilege,
                "card": user.card,
                "device_id": user.device_id,
                "is_synced": user.is_synced,
                "synced_at": synced_at,
                "created_at": created_at,
                "external_user_id": user.external_user_id,
                "avatar_url": user.avatar_url
            })
        
        serialize_end = time.time()
        current_app.logger.info(f"[DEBUG] Serialization completed in {serialize_end - serialize_start:.2f} seconds")
        
        total_time = time.time() - start_time
        current_app.logger.info(f"[DEBUG] Total API call completed in {total_time:.2f} seconds")
        
        return jsonify({
            "message": "Lấy danh sách người dùng thành công", 
            "data": serialized_users,
            "sync_status": {
                "success": sync_success, 
                "synced_count": synced_count, 
                "error": sync_error
            },
            "source": "database",
            "device_connected": sync_success
        })
        
    except Exception as e:
        error_message = f"Lỗi khi lấy danh sách người dùng: {str(e)}"
        current_app.logger.error(f"[DEBUG] Exception occurred: {error_message}")
        total_time = time.time() - start_time
        current_app.logger.error(f"[DEBUG] API call failed after {total_time:.2f} seconds")
        return jsonify({"message": error_message}), 500

@bp.route('/users/sync', methods=['POST'])
def sync_users():
    """Manual sync users from device endpoint"""
    try:
        device_id = request.json.get('device_id') if request.json else None
        
        current_app.logger.info(f"Manual sync users requested for device: {device_id or 'active device'}")
        
        sync_success, synced_count, sync_error = sync_users_from_device(device_id)
        
        if sync_success:
            return jsonify({
                "message": f"Đã đồng bộ {synced_count} người dùng từ thiết bị",
                "synced_count": synced_count,
                "success": True
            })
        else:
            return jsonify({
                "message": f"Không thể đồng bộ người dùng: {sync_error}",
                "synced_count": 0,
                "success": False,
                "error": sync_error
            }), 400
            
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ thủ công: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "message": error_message,
            "success": False,
            "error": error_message
        }), 500

@bp.route('/user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    data = {"user_id": int(user_id)}

    error = validate_data(data, delete_user_schema.schema)
    if error:
        return jsonify({"error": error}), 400
    
    try:
        current_app.logger.info(f"Deleting user with ID: {user_id}")
        get_service().delete_user(data["user_id"])
        return jsonify({"message": "Xóa người dùng thành công"})
    except Exception as e:
        error_message = f"Lỗi khi xóa người dùng: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500


@bp.route('/user/<user_id>/fingerprint', methods=['POST'])
def create_fingerprint(user_id):
    data = request.json
    temp_id = data.get('temp_id')
    
    try:
        current_app.logger.info(f"Creating fingerprint for user with ID: {user_id} and finger index: {temp_id}")
        get_service().enroll_user(int(user_id), int(temp_id))
        return jsonify({"message": "Tạo mẫu vân tay thành công"})
    except Exception as e:
        error_message = f"Lỗi khi tạo mẫu vân tay: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500


@bp.route('/user/<user_id>/fingerprint/<temp_id>', methods=['DELETE'])
def delete_fingerprint(user_id, temp_id):
    data = {"user_id": int(user_id), "temp_id": int(temp_id)}

    error = validate_data(data, delete_fingerprint_schema.schema)
    if error:
        return jsonify({"error": error}), 400

    try:
        current_app.logger.info(f"Deleting fingerprint for user with ID: {user_id} and finger index: {temp_id}")
        get_service().delete_user_template(data["user_id"], data["temp_id"])
        return jsonify({"message": "Xóa mẫu vân tay thành công"})
    except Exception as e:
        error_message = f"Lỗi khi xóa mẫu vân tay: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500


@bp.route('/user/<user_id>/fingerprint/<temp_id>', methods=['GET'])
def get_fingerprint(user_id, temp_id):
    data = {"user_id": int(user_id), "temp_id": int(temp_id)}

    error = validate_data(data, get_fingerprint_schema.schema)
    if error:
        return jsonify({"error": error}), 400

    try:
        current_app.logger.info(f"Getting fingerprint for user with ID: {user_id} and finger index: {temp_id}")
        template = get_service().get_user_template(data["user_id"], data["temp_id"])
        if not template:
            return jsonify({"message": "Không tìm thấy mẫu vân tay", "data": ""})
        # Serialize template
        serialized_template = serialize_template(template)
        current_app.logger.info(f"Fingerprint retrieved : {template.template}")
        return jsonify({"message": "Lấy mẫu vân tay thành công", "data": serialized_template})
    except Exception as e:
        error_message = f"Lỗi khi lấy mẫu vân tay: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500

@bp.route('/user/<user_id>/sync', methods=['POST'])
def sync_single_user(user_id):
    """Sync a single user to external API"""
    try:
        current_app.logger.info(f"Syncing single user with ID: {user_id}")

        # Get active device
        active_device = config_manager.get_active_device()
        if not active_device:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy thiết bị đang hoạt động"
            }), 400

        device_id = active_device['id']

        # Get user from database
        db_user = user_repo.get_by_user_id(user_id, device_id)
        if not db_user:
            return jsonify({
                "success": False,
                "message": f"Không tìm thấy người dùng {user_id} trong cơ sở dữ liệu"
            }), 404

        normalized_user_id = _derive_external_user_id(db_user.user_id)
        payload_user_id = (
            normalized_user_id if normalized_user_id is not None else db_user.user_id
        )

        # Prepare employee data
        employee = {
            "userId": payload_user_id,
            "name": db_user.name,
            "groupId": db_user.group_id
        }

        # Get device serial number
        device_info = active_device.get('device_info', {})
        serial_number = device_info.get('serial_number', device_id or 'unknown')

        # Make API request to sync employee
        sync_response = external_api_service.sync_employees([employee], serial_number)

        if sync_response.get('status') != 200:
            current_app.logger.error(f"API returned non-200 status: {sync_response.get('status')}, message: {sync_response.get('message')}")
            return jsonify({
                'success': False,
                'message': sync_response.get('message', 'Đồng bộ thất bại')
            }), 400

        # Fetch employee details
        users_array = [{
            "id": payload_user_id,
            "serial_number": db_user.serial_number or ""
        }]
        details_response = external_api_service.get_employees_by_user_ids(users_array)
        
        employee_details_data = {}
        if details_response.get("status") == 200:
            employee_details_list = details_response.get("data", [])
            for employee_detail in employee_details_list:
                time_clock_user_id = employee_detail.get("time_clock_user_id")
                normalized_lookup = _derive_external_user_id(time_clock_user_id)
                lookup_key = None
                if normalized_lookup is not None:
                    lookup_key = str(normalized_lookup)
                elif time_clock_user_id is not None:
                    lookup_key = str(time_clock_user_id).strip()

                if lookup_key:
                    employee_details_data[lookup_key] = {
                        "employee_id": employee_detail.get("employee_id"),
                        "employee_avatar": employee_detail.get("employee_avatar"),
                    }

        # Update user with sync status
        updates = {
            'is_synced': True,
            'synced_at': datetime.now()
        }

        # Add employee details if available
        user_lookup_key = (
            str(normalized_user_id)
            if normalized_user_id is not None
            else (str(db_user.user_id).strip() if db_user.user_id is not None else None)
        )
        if employee_details_data and user_lookup_key in employee_details_data:
            details = employee_details_data[user_lookup_key]
            updates['external_user_id'] = details.get('employee_id')
            updates['avatar_url'] = details.get('employee_avatar')

        user_repo.update(db_user.id, updates)

        current_app.logger.info(f"Successfully synced user {user_id} to external API")

        return jsonify({
            'success': True,
            'message': f'Đã đồng bộ người dùng {db_user.name} thành công',
            'user_id': user_id,
            'employee_details': employee_details_data.get(user_lookup_key) if (employee_details_data and user_lookup_key) else None
        })

    except requests.exceptions.RequestException as e:
        error_message = f"Lỗi HTTP khi đồng bộ người dùng: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "success": False,
            "message": error_message
        }), 500
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ người dùng: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "success": False,
            "message": error_message
        }), 500

@bp.route('/users/export', methods=['GET'])
def export_users():
    """Export all users for the active device to a JSON file."""
    try:
        active_device = config_manager.get_active_device()
        device_id = active_device['id'] if active_device else None

        db_users = user_repo.get_all(device_id=device_id)

        # Serialize users, excluding device_id
        users_to_export = []
        for user in db_users:
            users_to_export.append({
                "user_id": user.user_id,
                "name": user.name,
                "privilege": user.privilege,
                "group_id": user.group_id,
                "card": user.card,
                "password": user.password,
                "serial_number": user.serial_number, # Keep serial number for import matching
                # Exclude other fields like id, device_id, created_at, etc.
            })
        
        json_data = json.dumps(users_to_export, indent=4)

        return Response(
            json_data,
            mimetype='application/json',
            headers={"Content-Disposition": "attachment;filename=users_export.json"}
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting users: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/users/import', methods=['POST'])
def import_users():
    """Import users from a JSON file."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Get the exact_import flag from form data
        exact_import = request.form.get('exact_import', 'false').lower() == 'true'

        if file and file.filename.endswith('.json'):
            users_to_import = json.load(file)
            
            active_device = None
            if not exact_import:
                active_device = config_manager.get_active_device()
                if not active_device:
                    return jsonify({"error": "No active device configured for import."}), 400

            created_count = 0
            updated_count = 0
            failed_count = 0
            errors = []

            for user_data in users_to_import:
                try:
                    user_id = user_data.get('user_id')
                    if not user_id:
                        failed_count += 1
                        errors.append({"reason": "Missing user_id", "data": user_data})
                        continue

                    device_id = None
                    serial_number = user_data.get('serial_number')

                    if exact_import:
                        if not serial_number:
                            raise ValueError("Missing serial_number for exact import")
                        target_device = device_repo.get_by_serial_number(serial_number)
                        if not target_device:
                            raise ValueError(f"Device with serial_number '{serial_number}' not found")
                        device_id = target_device.id
                    else:
                        device_id = active_device['id']
                        # Use active device's serial if not present in data
                        if not serial_number:
                            serial_number = active_device.get('serial_number')

                    existing_user = user_repo.get_by_user_id(user_id, device_id)

                    if existing_user:
                        updates = {
                            'name': user_data.get('name', existing_user.name),
                            'privilege': user_data.get('privilege', existing_user.privilege),
                            'group_id': user_data.get('group_id', existing_user.group_id),
                            'card': user_data.get('card', existing_user.card),
                            'password': user_data.get('password', existing_user.password),
                            'serial_number': serial_number
                        }
                        user_repo.update(existing_user.id, updates)
                        updated_count += 1
                    else:
                        new_user = User(
                            user_id=user_id,
                            name=user_data.get('name'),
                            privilege=user_data.get('privilege', 0),
                            group_id=user_data.get('group_id', 0),
                            card=user_data.get('card', 0),
                            password=user_data.get('password', ''),
                            device_id=device_id,
                            serial_number=serial_number
                        )
                        user_repo.create(new_user)
                        created_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({"user_id": user_data.get('user_id'), "error": str(e)})

            return jsonify({
                "message": "Import completed",
                "created": created_count,
                "updated": updated_count,
                "failed": failed_count,
                "errors": errors
            })

        return jsonify({"error": "Invalid file type, please upload a .json file"}), 400

    except Exception as e:
        current_app.logger.error(f"Error importing users: {e}")
        return jsonify({"error": str(e)}), 500

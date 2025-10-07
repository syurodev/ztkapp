from flask import Blueprint, request, jsonify
from zkteco.services.zk_service import get_zk_service
from zkteco.validations import create_user_schema, delete_user_schema, get_fingerprint_schema, delete_fingerprint_schema, validate_data
from flask import current_app
from zkteco.database.models import User, user_repo
from zkteco.config.config_manager_sqlite import config_manager
from zkteco.services.connection_manager import connection_manager
import time
import requests
from datetime import datetime

bp = Blueprint('user', __name__, url_prefix='/')
# zk_service = get_zk_service()  # Lazy load to avoid blocking

def get_service():
    return get_zk_service()

def sync_users_from_device(device_id=None):
    """
    Sync users from device to database
    Returns tuple: (success, synced_count, error_message)
    """
    try:
        active_device = config_manager.get_active_device() if not device_id else config_manager.get_device(device_id)
        if not active_device:
            return False, 0, "No active device found"
        
        target_device_id = device_id or active_device['id']
        current_app.logger.info(f"Syncing users from device {target_device_id}")
        
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

                if existing_user:
                    # Update existing user with latest info from device
                    updates = {
                        'name': device_user.name or existing_user.name,
                        'privilege': getattr(device_user, 'privilege', existing_user.privilege),
                        'group_id': getattr(device_user, 'group_id', existing_user.group_id),
                        'card': getattr(device_user, 'card', existing_user.card),
                        'password': getattr(device_user, 'password', existing_user.password),
                        'serial_number': device_serial
                    }

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
                    is_synced=False  # Not synced to external API yet
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
        error_message = f"Error syncing users from device: {str(e)}"
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
        return jsonify({"message": "User added successfully"})
    except Exception as e:
        error_message = f"Error creating user: {str(e)}"
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
            message = "No users found"
            if sync_error:
                message += f" (Device sync failed: {sync_error})"
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
            "message": "Users retrieved successfully", 
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
        error_message = f"Error retrieving users: {str(e)}"
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
                "message": f"Successfully synced {synced_count} users from device",
                "synced_count": synced_count,
                "success": True
            })
        else:
            return jsonify({
                "message": f"Failed to sync users: {sync_error}",
                "synced_count": 0,
                "success": False,
                "error": sync_error
            }), 400
            
    except Exception as e:
        error_message = f"Error during manual sync: {str(e)}"
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
        return jsonify({"message": "User deleted successfully"})
    except Exception as e:
        error_message = f"Error deleting user: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"message": error_message}), 500


@bp.route('/user/<user_id>/fingerprint', methods=['POST'])
def create_fingerprint(user_id):
    data = request.json
    temp_id = data.get('temp_id')
    
    try:
        current_app.logger.info(f"Creating fingerprint for user with ID: {user_id} and finger index: {temp_id}")
        get_service().enroll_user(int(user_id), int(temp_id))
        return jsonify({"message": "Fingerprint created successfully"})
    except Exception as e:
        error_message = f"Error creating fingerprint: {str(e)}"
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
        return jsonify({"message": "Fingerprint deleted successfully"})
    except Exception as e:
        error_message = f"Error deleting fingerprint: {str(e)}"
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
            return jsonify({"message": "No templates found", "data": ""})
        # Serialize template
        serialized_template = serialize_template(template)
        current_app.logger.info(f"Fingerprint retrieved : {template.template}")
        return jsonify({"message": "Fingerprint retrieved successfully", "data": serialized_template})
    except Exception as e:
        error_message = f"Error retrieving fingerprint: {str(e)}"
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
                "message": "No active device found"
            }), 400

        device_id = active_device['id']

        # Get user from database
        db_user = user_repo.get_by_user_id(user_id, device_id)
        if not db_user:
            return jsonify({
                "success": False,
                "message": f"User {user_id} not found in database"
            }), 404

        # Get external API configuration
        external_api_domain = config_manager.get_external_api_url()
        if not external_api_domain:
            return jsonify({
                "success": False,
                "message": "API_GATEWAY_DOMAIN not configured"
            }), 400

        api_key = config_manager.get_external_api_key()
        if not api_key:
            return jsonify({
                "success": False,
                "message": "EXTERNAL_API_KEY not configured"
            }), 400

        # Prepare employee data
        employee = {
            "userId": db_user.user_id,
            "name": db_user.name,
            "groupId": db_user.group_id
        }

        # Get device serial number
        device_info = active_device.get('device_info', {})
        serial_number = device_info.get('serial_number', device_id or 'unknown')

        # Prepare sync data
        sync_data = {
            "timestamp": int(time.time()),
            "employees": [employee]
        }

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'x-device-sync': serial_number,
            'ProjectId': "1055"
        }

        # Make API request
        external_api_url = external_api_domain + '/time-clock-employees/sync'
        current_app.logger.info(f"Sending sync request to: {external_api_url}")
        current_app.logger.info(f"Sync data: {sync_data}")
        current_app.logger.info(f"Headers: {dict(headers)}")

        response = requests.post(
            external_api_url,
            json=sync_data,
            headers=headers,
            timeout=30
        )

        current_app.logger.info(f"Response status code: {response.status_code}")
        current_app.logger.info(f"Response text: {response.text}")

        data = response.json()

        if data.get('status') != 200:
            current_app.logger.error(f"API returned non-200 status: {data.get('status')}, message: {data.get('message')}")
            return jsonify({
                'success': False,
                'message': data.get('message', 'Sync failed')
            }), 400

        response.raise_for_status()

        # Fetch employee details
        employee_details = get_service()._fetch_employee_details([db_user.user_id], external_api_domain)

        # Update user with sync status
        updates = {
            'is_synced': True,
            'synced_at': datetime.now()
        }

        # Add employee details if available
        if employee_details and db_user.user_id in employee_details:
            details = employee_details[db_user.user_id]
            updates['external_user_id'] = details.get('employee_id')
            updates['avatar_url'] = details.get('employee_avatar')

        user_repo.update(db_user.id, updates)

        current_app.logger.info(f"Successfully synced user {user_id} to external API")

        return jsonify({
            'success': True,
            'message': f'User {db_user.name} synced successfully',
            'user_id': user_id,
            'employee_details': employee_details.get(db_user.user_id) if employee_details else None
        })

    except requests.exceptions.RequestException as e:
        error_message = f"HTTP error syncing user: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "success": False,
            "message": error_message
        }), 500
    except Exception as e:
        error_message = f"Error syncing user: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "success": False,
            "message": error_message
        }), 500

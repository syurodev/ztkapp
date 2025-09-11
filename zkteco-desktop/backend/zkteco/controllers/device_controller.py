from flask import Blueprint, jsonify, request
from zkteco.services.zk_service import ZkService, get_zk_service
from zk import ZK
from flask import current_app
from zkteco.config.config_manager_sqlite import config_manager

bp = Blueprint('device', __name__, url_prefix='/')

def get_service():
    return get_zk_service()


@bp.route('/device/capture', methods=['GET'])
def device_connect():
    try:
        ZkService(
            zk_class = ZK,
            ip = current_app.config.get('DEVICE_IP'),
            port = current_app.config.get('DEVICE_PORT'),
            verbose = current_app.config.get('DEBUG')
        )

        return jsonify({"message": "Device connected successfully"})
    except Exception as e:
        error_message = f"Error starting device capture: {str(e)}"
        return jsonify({"message": error_message}), 500

@bp.route('/config', methods=['POST'])
def update_config():
    """Legacy config update - maintains backward compatibility"""
    data = request.json

    # Save general config (non-device specific settings)
    general_config = {
        'EXTERNAL_API_DOMAIN': data.get('EXTERNAL_API_DOMAIN', '')
    }
    config_manager.save_config(general_config)

    return jsonify({"message": "Configuration updated successfully"})

@bp.route('/config', methods=['GET'])
def get_config():
    return jsonify(config_manager.get_config())


# Device Management Endpoints
@bp.route('/devices', methods=['GET'])
def get_all_devices():
    """Get all configured devices"""
    try:
        devices = config_manager.get_all_devices()
        active_device_id = config_manager.get_active_device()
        active_device_id = active_device_id['id'] if active_device_id else None

        return jsonify({
            "devices": devices,
            "active_device_id": active_device_id
        })
    except Exception as e:
        error_message = f"Error retrieving devices: {str(e)}"
        return jsonify({"error": error_message}), 500

@bp.route('/devices', methods=['POST'])
def add_device():
    """Add a new device"""
    data = request.json

    try:
        # Validate request data
        if not data:
            return jsonify({
                "error": "Request body is required",
                "error_type": "validation_error"
            }), 400
            
        # Validate required fields
        if not data.get('ip'):
            return jsonify({
                "error": "Device IP address is required",
                "error_type": "validation_error"
            }), 400
            
        if not data.get('name'):
            return jsonify({
                "error": "Device name is required", 
                "error_type": "validation_error"
            }), 400
            
        # Validate IP format
        import ipaddress
        try:
            ipaddress.ip_address(data.get('ip'))
        except ValueError:
            return jsonify({
                "error": "Invalid IP address format",
                "error_type": "validation_error"
            }), 400
            
        # Validate port range
        port = data.get('port', 4370)
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            return jsonify({
                "error": "Port must be a number between 1 and 65535",
                "error_type": "validation_error"
            }), 400

        # Test connection before adding
        current_app.logger.info(f"Testing connection to new device {data.get('name')} at {data.get('ip')}:{data.get('port', 4370)}")

        from zk import ZK
        test_zk = ZK(
            ip=data.get('ip'),
            port=int(data.get('port', 4370)),
            timeout=int(data.get('timeout', 10)),
            password=int(data.get('password', 0)),
            force_udp=bool(data.get('force_udp', False)),
            verbose=current_app.config.get('DEBUG', False)
        )

        # Try to connect with timeout handling
        try:
            test_zk.connect()
        except Exception as conn_error:
            try:
                test_zk.disconnect()
            except Exception:
                pass
            
            # Check for specific connection errors
            error_str = str(conn_error).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise TimeoutError(f"Connection timeout: {conn_error}")
            elif "refused" in error_str or "unreachable" in error_str:
                raise ConnectionError(f"Network unreachable: {conn_error}")
            else:
                raise ConnectionError(f"Connection failed: {conn_error}")

        if not test_zk.is_connect:
            raise ConnectionError("Device connection failed - unable to establish connection")

        # Get device info
        try:
            test_zk.disable_device()
            device_info = {
                'current_time': test_zk.get_time().strftime('%Y-%m-%d %H:%M:%S') if test_zk.get_time() else None,
                'firmware_version': test_zk.get_firmware_version(),
                'device_name': test_zk.get_device_name(),
                'serial_number': test_zk.get_serialnumber(),
                'mac_address': test_zk.get_mac(),
                'face_version': test_zk.get_face_version(),
                'fp_version': test_zk.get_fp_version(),
                'platform': test_zk.get_platform()
            }

            try:
                network_info = test_zk.get_network_params()
                device_info['network'] = {
                    'ip': network_info.get('ip'),
                    'netmask': network_info.get('mask'),
                    'gateway': network_info.get('gateway')
                }
            except Exception:
                device_info['network'] = None

        except Exception as device_info_error:
            current_app.logger.warning(f"Failed to get device info: {device_info_error}")
            device_info = {}
        finally:
            try:
                test_zk.enable_device()
                test_zk.disconnect()
            except Exception:
                pass

        # Add device info to data
        data['device_info'] = device_info
        data['serial_number'] = device_info.get('serial_number')

        # Add the device
        device_id = config_manager.add_device(data)

        current_app.logger.info(f"Device {data.get('name')} added successfully with ID: {device_id}")

        return jsonify({
            "message": "Device added successfully",
            "device_id": device_id,
            "device_info": device_info
        })

    except ValueError as e:
        # Handle specific validation errors (e.g. duplicate serial number)
        error_message = str(e)
        current_app.logger.warning(f"Device validation failed: {error_message}")
        return jsonify({
            "error": error_message,
            "error_type": "validation_error"
        }), 400
    
    except ConnectionError as e:
        # Handle connection-related errors
        error_message = f"Cannot connect to device: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({
            "error": error_message,
            "error_type": "connection_error"
        }), 400
        
    except TimeoutError as e:
        # Handle timeout errors
        error_message = "Device connection timed out. Please check IP address and network connectivity."
        current_app.logger.error(f"Device connection timeout: {str(e)}")
        return jsonify({
            "error": error_message,
            "error_type": "timeout_error"
        }), 400
        
    except Exception as e:
        # Handle all other unexpected errors
        error_message = f"Failed to add device: {str(e)}"
        current_app.logger.error(f"Unexpected error adding device: {error_message}")
        return jsonify({
            "error": error_message,
            "error_type": "server_error"
        }), 500

@bp.route('/devices/<device_id>', methods=['PUT'])
def update_device(device_id):
    """Update an existing device"""
    data = request.json

    try:
        # Check if device exists
        existing_device = config_manager.get_device(device_id)
        if not existing_device:
            return jsonify({"error": "Device not found"}), 404

        # If IP or port changed, test the connection
        if (data.get('ip') != existing_device.get('ip') or
            data.get('port') != existing_device.get('port')):

            current_app.logger.info(f"Testing connection to updated device {device_id}")

            from zk import ZK
            test_zk = ZK(
                ip=data.get('ip', existing_device.get('ip')),
                port=int(data.get('port', existing_device.get('port'))),
                timeout=int(data.get('timeout', existing_device.get('timeout'))),
                password=int(data.get('password', existing_device.get('password'))),
                force_udp=bool(data.get('force_udp', existing_device.get('force_udp'))),
                verbose=current_app.config.get('DEBUG', False)
            )

            test_zk.connect()

            if not test_zk.is_connect:
                return jsonify({"error": "Failed to connect to device with new settings"}), 400

            test_zk.disconnect()

        # Update the device
        success = config_manager.update_device(device_id, data)

        if not success:
            return jsonify({"error": "Device not found"}), 404

        # Reset connection for this device if it exists
        from zkteco.services.connection_manager import connection_manager
        connection_manager.reset_device_connection(device_id)

        return jsonify({"message": "Device updated successfully"})

    except Exception as e:
        error_message = f"Failed to update device: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 400

@bp.route('/devices/<device_id>', methods=['DELETE'])
def delete_device(device_id):
    """Delete a device"""
    try:
        success = config_manager.delete_device(device_id)

        if not success:
            return jsonify({"error": "Device not found"}), 404

        # Disconnect and clean up
        from zkteco.services.connection_manager import connection_manager
        connection_manager.disconnect_device(device_id)

        return jsonify({"message": "Device deleted successfully"})

    except Exception as e:
        error_message = f"Failed to delete device: {str(e)}"
        return jsonify({"error": error_message}), 500

@bp.route('/devices/<device_id>/activate', methods=['PUT'])
def activate_device(device_id):
    """Set a device as the active device"""
    try:
        success = config_manager.set_active_device(device_id)

        if not success:
            return jsonify({"error": "Device not found"}), 404

        return jsonify({"message": "Device activated successfully"})

    except Exception as e:
        error_message = f"Failed to activate device: {str(e)}"
        return jsonify({"error": error_message}), 500

@bp.route('/devices/<device_id>/test', methods=['POST'])
def test_device_connection(device_id):
    """Test connection to a specific device"""
    try:
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        from zk import ZK
        test_zk = ZK(
            ip=device.get('ip'),
            port=int(device.get('port')),
            timeout=int(device.get('timeout')),
            password=int(device.get('password')),
            force_udp=bool(device.get('force_udp')),
            verbose=current_app.config.get('DEBUG', False)
        )

        test_zk.connect()

        if not test_zk.is_connect:
            return jsonify({"success": False, "error": "Failed to connect to device"}), 400

        test_zk.disconnect()

        return jsonify({
            "success": True,
            "message": "Device connection successful"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }), 400

# Legacy device endpoints (uses active device)
@bp.route('/device/info', methods=['GET'])
def get_active_device_info():
    """Get info for active device"""
    try:
        device_info = get_service().get_device_info()
        return jsonify(device_info)
    except Exception as e:
        error_message = f"Error getting device info: {str(e)}"
        return jsonify({"error": error_message}), 500

@bp.route('/device/sync-employee', methods=['POST'])
def sync_employee():
    """Sync employees from active device"""
    try:
        sync_result = get_service().sync_employee()
        return jsonify(sync_result)
    except ValueError as e:
        error_message = f"Configuration error: {str(e)}"
        return jsonify({"error": error_message}), 400
    except Exception as e:
        error_message = f"Error syncing employees: {str(e)}"
        return jsonify({"error": error_message}), 500

# Device-specific endpoints
@bp.route('/devices/<device_id>/info', methods=['GET'])
def get_device_specific_info(device_id):
    """Get info for a specific device"""
    try:
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        from zkteco.services.zk_service import ZkService
        service = ZkService()
        device_info = service.get_device_info(device_id)
        return jsonify(device_info)
    except Exception as e:
        error_message = f"Error getting device info: {str(e)}"
        return jsonify({"error": error_message}), 500

@bp.route('/devices/<device_id>/sync-employee', methods=['POST'])
def sync_employee_from_device(device_id):
    """Sync employees from a specific device"""
    try:
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        from zkteco.services.zk_service import ZkService
        service = ZkService()
        sync_result = service.sync_employee(device_id)
        return jsonify(sync_result)
    except ValueError as e:
        error_message = f"Configuration error: {str(e)}"
        return jsonify({"error": error_message}), 400
    except Exception as e:
        error_message = f"Error syncing employees: {str(e)}"
        return jsonify({"error": error_message}), 500

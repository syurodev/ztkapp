from app.shared.logger import app_logger
import queue
import time
import requests
from flask import Blueprint, jsonify, request, Response, stream_with_context
from app.services.device_service import ZkService, get_zk_service
from zk import ZK
from flask import current_app
from app.config.config_manager import config_manager
from app.device.connection_manager import connection_manager
from app.events.event_stream import device_event_stream
from app.services.external_api_service import external_api_service

# Try importing live capture service with error handling
try:
    from app.services.live_capture_service import (
        start_multi_device_capture,
        stop_multi_device_capture,
        start_device_capture,
        stop_device_capture,
        get_capture_status,
        multi_device_manager,
    )

    LIVE_CAPTURE_AVAILABLE = True
    print("[OK] Live capture service imported successfully")
except ImportError as e:
    print(f"[ERROR] Failed to import live capture service: {e}")
    LIVE_CAPTURE_AVAILABLE = False
except Exception as e:
    print(f"[ERROR] Error importing live capture service: {e}")
    LIVE_CAPTURE_AVAILABLE = False

bp = Blueprint("device", __name__, url_prefix="/")


def get_service():
    return get_zk_service()


@bp.route("/device/capture", methods=["GET"])
def device_connect():
    try:
        ZkService(
            zk_class=ZK,
            ip=current_app.config.get("DEVICE_IP"),
            port=current_app.config.get("DEVICE_PORT"),
            verbose=current_app.config.get("DEBUG"),
        )

        return jsonify({"message": "Kết nối thiết bị thành công"})
    except Exception as e:
        error_message = f"Lỗi khi khởi động chế độ capture: {str(e)}"
        return jsonify({"message": error_message}), 500


@bp.route("/config", methods=["POST"])
def update_config():
    """Legacy config update - maintains backward compatibility"""
    data = request.json

    # Save general config (non-device specific settings)
    general_config = {
        "API_GATEWAY_DOMAIN": data.get("API_GATEWAY_DOMAIN"),
        "EXTERNAL_API_KEY": data.get("EXTERNAL_API_KEY", ""),
    }
    config_manager.save_config(general_config)

    return jsonify({"message": "Cập nhật cấu hình thành công"})


@bp.route("/config", methods=["GET"])
def get_config():
    return jsonify(config_manager.get_config())


@bp.route("/devices/events", methods=["GET"])
def stream_device_events():
    """Stream device ping events to the frontend via Server-Sent Events."""

    def event_generator():
        subscriber = device_event_stream.subscribe()
        # Immediately send a ready event so clients know the stream is active
        yield "event: ready\ndata: {}\n\n"

        try:
            while True:
                try:
                    payload = subscriber.get(timeout=25)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    # Heartbeat comment keeps connection alive when there is no data
                    yield f": keep-alive {int(time.time())}\n\n"
        except GeneratorExit:
            # Client disconnected; fall through to finally for cleanup
            pass
        finally:
            device_event_stream.unsubscribe(subscriber)

    response = Response(
        stream_with_context(event_generator()), mimetype="text/event-stream"
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


# Device Management Endpoints
@bp.route("/devices", methods=["GET"])
def get_all_devices():
    """Get all configured devices"""
    try:
        devices = config_manager.get_all_devices()
        active_device_id = config_manager.get_active_device()
        active_device_id = active_device_id["id"] if active_device_id else None

        return jsonify({"devices": devices, "active_device_id": active_device_id})
    except Exception as e:
        error_message = f"Error retrieving devices: {str(e)}"
        return jsonify({"error": error_message}), 500


@bp.route("/devices", methods=["POST"])
def add_device():
    """Add a new device"""
    data = request.json

    try:
        # Validate request data
        if not data:
            return jsonify(
                {"error": "Request body is required", "error_type": "validation_error"}
            ), 400

        # Validate required fields
        if not data.get("ip"):
            return jsonify(
                {
                    "error": "Device IP address is required",
                    "error_type": "validation_error",
                }
            ), 400

        if not data.get("name"):
            return jsonify(
                {"error": "Device name is required", "error_type": "validation_error"}
            ), 400

        # Validate IP format
        import ipaddress

        try:
            ipaddress.ip_address(data.get("ip"))
        except ValueError:
            return jsonify(
                {"error": "Invalid IP address format", "error_type": "validation_error"}
            ), 400

        # Validate port range
        port = data.get("port", 4370)
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            return jsonify(
                {
                    "error": "Port must be a number between 1 and 65535",
                    "error_type": "validation_error",
                }
            ), 400

        # Check device type - skip connection test for push devices
        device_type = data.get("device_type", "pull")
        device_info = {}

        if device_type == "pull":
            # Test connection before adding (only for pull devices)
            current_app.logger.info(
                f"Testing connection to new pull device {data.get('name')} at {data.get('ip')}:{data.get('port', 4370)}"
            )

            from zk import ZK

            test_zk = ZK(
                ip=data.get("ip"),
                port=int(data.get("port", 4370)),
                timeout=int(data.get("timeout", 10)),
                password=int(data.get("password", 0)),
                force_udp=bool(data.get("force_udp", False)),
                verbose=current_app.config.get("DEBUG", False),
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
                raise ConnectionError(
                    "Device connection failed - unable to establish connection"
                )

            # Get device info
            try:
                test_zk.disable_device()
                device_info = {
                    "current_time": test_zk.get_time().strftime("%Y-%m-%d %H:%M:%S")
                    if test_zk.get_time()
                    else None,
                    "firmware_version": test_zk.get_firmware_version(),
                    "device_name": test_zk.get_device_name(),
                    "serial_number": test_zk.get_serialnumber(),
                    "mac_address": test_zk.get_mac(),
                    "face_version": test_zk.get_face_version(),
                    "fp_version": test_zk.get_fp_version(),
                    "platform": test_zk.get_platform(),
                }

                try:
                    network_info = test_zk.get_network_params()
                    device_info["network"] = {
                        "ip": network_info.get("ip"),
                        "netmask": network_info.get("mask"),
                        "gateway": network_info.get("gateway"),
                    }
                except Exception:
                    device_info["network"] = None

            except Exception as device_info_error:
                current_app.logger.warning(
                    f"Failed to get device info: {device_info_error}"
                )
                device_info = {}
            finally:
                try:
                    test_zk.enable_device()
                    test_zk.disconnect()
                except Exception:
                    pass

            # Add device info to data
            data["device_info"] = device_info
            data["serial_number"] = device_info.get("serial_number")
        else:
            # Push device - skip connection test
            current_app.logger.info(
                f"Adding push device {data.get('name')} - skipping connection test"
            )
            device_info = {
                "device_type": "push",
                "note": "Push devices do not require connection test. Device will auto-register on first ping.",
            }
            data["device_info"] = device_info

        # Add the device
        device_id = config_manager.add_device(data)

        current_app.logger.info(
            f"Device {data.get('name')} added successfully with ID: {device_id}"
        )

        external_sync_result = None

        try:
            serial_number = data.get("serial_number") or device_info.get(
                "serial_number"
            )
            if serial_number:
                payload = {
                    "payload": [{"serial": serial_number, "name": data.get("name")}]
                }
                external_sync_result = external_api_service.sync_device(payload, serial_number)
                current_app.logger.info(
                    f"Synced new device {data.get('name')} to external API."
                )
            else:
                current_app.logger.warning(
                    "Serial number not available for new device; skipping external sync."
                )
        except requests.exceptions.RequestException as e:
            current_app.logger.error(
                f"Failed to sync new device {data.get('name')} to external API: {e}"
            )
        except Exception as e:
            current_app.logger.error(
                f"Unexpected error during external sync for new device {data.get('name')}: {e}"
            )

        response_payload = {
            "message": "Thêm thiết bị thành công",
            "device_id": device_id,
            "device_info": device_info,
        }

        if external_sync_result is not None:
            response_payload["external_sync"] = external_sync_result

        return jsonify(response_payload)

    except ValueError as e:
        # Handle specific validation errors (e.g. duplicate serial number)
        error_message = str(e)
        current_app.logger.warning(f"Device validation failed: {error_message}")
        return jsonify({"error": error_message, "error_type": "validation_error"}), 400

    except ConnectionError as e:
        # Handle connection-related errors
        error_message = f"Không thể kết nối tới thiết bị: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message, "error_type": "connection_error"}), 400

    except TimeoutError as e:
        # Handle timeout errors
        error_message = "Quá thời gian kết nối tới thiết bị. Vui lòng kiểm tra địa chỉ IP và kết nối mạng."
        current_app.logger.error(f"Device connection timeout: {str(e)}")
        return jsonify({"error": error_message, "error_type": "timeout_error"}), 400

    except Exception as e:
        # Handle all other unexpected errors
        error_message = f"Không thể thêm thiết bị: {str(e)}"
        current_app.logger.error(f"Unexpected error adding device: {error_message}")
        return jsonify({"error": error_message, "error_type": "server_error"}), 500


@bp.route("/devices/<device_id>", methods=["PUT"])
def update_device(device_id):
    """Update an existing device"""
    data = request.json

    try:
        # Check if device exists
        existing_device = config_manager.get_device(device_id)
        if not existing_device:
            return jsonify({"error": "Device not found"}), 404

        # Get device type (use existing or updated value)
        device_type = data.get(
            "device_type", existing_device.get("device_type", "pull")
        )

        # If IP or port changed, test the connection (only for pull devices)
        if data.get("ip") != existing_device.get("ip") or data.get(
            "port"
        ) != existing_device.get("port"):
            if device_type == "pull":
                current_app.logger.info(
                    f"Testing connection to updated pull device {device_id}"
                )

                from zk import ZK

                test_zk = ZK(
                    ip=data.get("ip", existing_device.get("ip")),
                    port=int(data.get("port", existing_device.get("port"))),
                    timeout=int(data.get("timeout", existing_device.get("timeout"))),
                    password=int(data.get("password", existing_device.get("password"))),
                    force_udp=bool(
                        data.get("force_udp", existing_device.get("force_udp"))
                    ),
                    verbose=current_app.config.get("DEBUG", False),
                )

                test_zk.connect()

                if not test_zk.is_connect:
                    return jsonify(
                        {"error": "Failed to connect to device with new settings"}
                    ), 400

                test_zk.disconnect()
            else:
                current_app.logger.info(
                    f"Skipping connection test for push device {device_id}"
                )

        # Update the device
        success = config_manager.update_device(device_id, data)

        if not success:
            return jsonify({"error": "Device not found"}), 404

        # Reset connection for this device if it exists
        from app.device.connection_manager import connection_manager

        connection_manager.reset_device_connection(device_id)

        external_sync_result = None

        try:
            updated_device = config_manager.get_device(device_id) or {}
            serial_number = data.get("serial_number") or updated_device.get(
                "serial_number"
            )
            device_name = data.get("name") or updated_device.get("name")

            if serial_number:
                payload = {
                    "payload": [{"serial": serial_number, "name": device_name}]
                }
                external_sync_result = external_api_service.sync_device(payload, serial_number)
                current_app.logger.info(
                    f"Synced updated device {device_id} to external API."
                )
            else:
                current_app.logger.warning(
                    f"Serial number not available for updated device {device_id}; skipping external sync."
                )
        except requests.exceptions.RequestException as e:
            current_app.logger.error(
                f"Failed to sync updated device {device_id} to external API: {e}"
            )
        except Exception as e:
            current_app.logger.error(
                f"Unexpected error during external sync for updated device {device_id}: {e}"
            )

        response_payload = {"message": "Cập nhật thiết bị thành công"}
        if external_sync_result is not None:
            response_payload["external_sync"] = external_sync_result

        return jsonify(response_payload)

    except Exception as e:
        error_message = f"Failed to update device: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 400


@bp.route("/devices/<device_id>", methods=["DELETE"])
def delete_device(device_id):
    """Delete a device"""
    try:
        current_app.logger.info(f"DELETE request received for device_id: {device_id}")

        # Check if device exists first
        existing_device = config_manager.get_device(device_id)
        if not existing_device:
            current_app.logger.warning(f"Device not found for deletion: {device_id}")
            return jsonify({"error": "Device not found"}), 404

        current_app.logger.info(
            f"Found device for deletion: {existing_device.get('name', 'Unknown')}"
        )

        # Delete the device
        current_app.logger.info(f"Attempting to delete device: {device_id}")
        success = config_manager.delete_device(device_id)
        current_app.logger.info(f"Delete operation result: {success}")

        if not success:
            current_app.logger.error(
                f"Delete operation returned False for device: {device_id}"
            )
            return jsonify({"error": "Device not found"}), 404

        # Disconnect and clean up
        try:
            current_app.logger.info(f"Cleaning up connections for device: {device_id}")
            from app.device.connection_manager import connection_manager

            connection_manager.disconnect_device(device_id)
            current_app.logger.info(
                f"Connection cleanup completed for device: {device_id}"
            )
        except Exception as cleanup_error:
            current_app.logger.warning(
                f"Connection cleanup failed for device {device_id}: {cleanup_error}"
            )
            # Continue anyway since device is already deleted

        current_app.logger.info(f"Device deleted successfully: {device_id}")
        return jsonify({"message": "Xóa thiết bị thành công"})

    except Exception as e:
        error_message = f"Failed to delete device {device_id}: {str(e)}"
        current_app.logger.error(
            error_message, exc_info=True
        )  # This will log the full stack trace
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/activate", methods=["PUT"])
def activate_device(device_id):
    """Set a device as the active device"""
    try:
        success = config_manager.set_active_device(device_id)

        if not success:
            return jsonify({"error": "Device not found"}), 404

        return jsonify({"message": "Kích hoạt thiết bị thành công"})

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

        # Check device type
        device_type = device.get('device_type', 'pull')

        if device_type == 'push':
            # Push devices don't require connection test
            return jsonify({
                "success": True,
                "message": "Thiết bị push không cần kiểm tra kết nối. Thiết bị sẽ tự đăng ký khi ping về máy chủ.",
                "device_type": "push",
                "note": "Connection test is not applicable for push devices"
            })

        # Pull device - test connection
        device_config = {
            'ip': device.get('ip'),
            'port': int(device.get('port', 4370) or 4370),
            'password': int(device.get('password', 0) or 0),
            'timeout': int(device.get('timeout', 180) or 180),
            'force_udp': bool(device.get('force_udp', False)),
            'verbose': current_app.config.get('DEBUG', False),
            'retry_count': int(device.get('retry_count', 3) or 3),
            'retry_delay': int(device.get('retry_delay', 2) or 2),
            'ping_interval': int(device.get('ping_interval', 10) or 10)
        }

        connection_manager.configure_device(device_id, device_config)

        try:
            connection_manager.ensure_device_connection(device_id)
        finally:
            connection_manager.disconnect_device(device_id)

        return jsonify({
            "success": True,
            "message": "Kiểm tra kết nối thiết bị thành công",
            "device_type": "pull"
        })

    except Exception as e:
        connection_manager.reset_device_connection(device_id)
        return jsonify({
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }), 400


@bp.route('/devices/sync-external', methods=['POST'])
def sync_devices_to_external_api():
    """
    Sync all configured devices to an external API.
    Sends a list of devices with their serial number and name.
    """
    try:
        # 1. Get all devices
        all_devices = config_manager.get_all_devices()
        if not all_devices:
            return jsonify({"message": "No devices configured to sync."}), 404

        # 2. Format the payload
        devices_list = [
            {
                "serial": device.get("serial_number"),
                "name": device.get("name")
            }
            for device in all_devices if device.get("serial_number")
        ]

        if not devices_list:
            return jsonify({"error": "No devices with serial numbers found to sync."}), 400

        # Wrap in payload object
        payload = {
            "payload": devices_list
        }

        # 3. Get external API config
        if not config_manager.get_external_api_url() or not config_manager.get_external_api_key():
            return jsonify({"error": "External API domain or key is not configured."}), 500

        # 4. Make the external API call
        response_data = external_api_service.sync_device(payload, serial_number=None)

        # 5. Return the response from the external API
        return jsonify(response_data)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error syncing devices to external API: {e}")
        if e.response is not None:
            try:
                error_json = e.response.json()
                return jsonify({"error": error_json.get("message", str(e))}), e.response.status_code
            except ValueError:
                return jsonify({"error": e.response.text}), e.response.status_code
        return jsonify({"error": str(e)}), 500


@bp.route("/branches", methods=["GET"])
def get_branches():
    """Get all branches from external API."""
    try:
        branches = external_api_service.get_branches()
        return jsonify(branches)
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred during get branches: {e}")
        return jsonify({"error": str(e)}), 500


# Legacy device endpoints (uses active device)
@bp.route("/device/info", methods=["GET"])
def get_active_device_info():
    """Get info for active device"""
    try:
        device_info = get_service().get_device_info()
        return jsonify(device_info)
    except Exception as e:
        error_message = f"Error getting device info: {str(e)}"
        return jsonify({"error": error_message}), 500


@bp.route("/device/sync-employee", methods=["POST"])
def sync_employee():
    """Sync employees from active device"""
    try:
        sync_result = get_service().sync_employee()
        return jsonify(sync_result)
    except ValueError as e:
        error_message = f"Lỗi cấu hình: {str(e)}"
        return jsonify({"error": error_message}), 400
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ nhân sự: {str(e)}"
        return jsonify({"error": error_message}), 500


# Device-specific endpoints
@bp.route("/devices/<device_id>/info", methods=["GET"])
def get_device_specific_info(device_id):
    """Get info for a specific device"""
    try:
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Không tìm thấy thiết bị"}), 404

        from app.services.device_service import ZkService

        service = ZkService()
        device_info = service.get_device_info(device_id)
        return jsonify(device_info)
    except Exception as e:
        error_message = f"Lỗi khi lấy thông tin thiết bị: {str(e)}"
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/sync-employee", methods=["POST"])
def sync_employee_from_device(device_id):
    """Sync employees from a specific device"""
    try:
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Không tìm thấy thiết bị"}), 404

        from app.services.device_service import ZkService

        service = ZkService()
        sync_result = service.sync_employee(device_id)
        return jsonify(sync_result)
    except ValueError as e:
        error_message = f"Lỗi cấu hình: {str(e)}"
        return jsonify({"error": error_message}), 400
    except Exception as e:
        error_message = f"Lỗi khi đồng bộ nhân sự: {str(e)}"
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/sync-users", methods=["POST"])
def sync_users_from_push_device(device_id):
    """Trigger user sync from push device by queuing DATA UPDATE USERINFO command"""
    try:
        # Get device info
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        # Check if device is push type
        device_type = device.get("device_type", "pull")
        if device_type != "push":
            return jsonify(
                {
                    "error": "This endpoint is only for push devices. Use /sync-employee for pull devices.",
                    "device_type": device_type,
                }
            ), 400

        # Get serial number
        serial_number = device.get("serial_number")
        if not serial_number:
            return jsonify(
                {
                    "error": "Push device serial number not found. Device may not have registered yet.",
                    "note": "Wait for device to ping the server first, then retry.",
                }
            ), 400

        # Queue command to push protocol service
        from app.services.push_protocol_service import push_protocol_service

        # SenseFace 4 devices may use different command formats
        # Try the most common variations based on device manual
        success = push_protocol_service.queue_command(serial_number, "INFO")

        if success:
            current_app.logger.info(
                f"Queued DATA UPDATE USERINFO command for push device {device.get('name')} "
                f"(SN: {serial_number})"
            )

            return jsonify(
                {
                    "message": "Đã gửi lệnh đồng bộ người dùng thành công",
                    "device_id": device_id,
                    "serial_number": serial_number,
                    "command": "DATA UPDATE USERINFO",
                    "note": "Device will receive command on next ping and upload user data",
                }
            )
        else:
            return jsonify({"error": "Failed to queue sync command"}), 500

    except Exception as e:
        error_message = f"Error syncing users from push device: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


# Multi-Device Live Capture Endpoints
@bp.route("/devices/capture/start-all", methods=["POST"])
def start_all_device_capture():
    """Start live capture for all active devices"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        start_multi_device_capture()

        # Get current status
        status = get_capture_status()

        return jsonify(
            {
                "message": "Đã bật thu dữ liệu realtime cho nhiều thiết bị",
                "status": status,
            }
        )
    except Exception as e:
        error_message = f"Error starting multi-device capture: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


@bp.route("/devices/capture/stop-all", methods=["POST"])
def stop_all_device_capture():
    """Stop live capture for all devices"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        stop_multi_device_capture()

        return jsonify({"message": "Đã tắt thu dữ liệu realtime cho nhiều thiết bị"})
    except Exception as e:
        error_message = f"Error stopping multi-device capture: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/capture/start", methods=["POST"])
def start_single_device_capture(device_id):
    """Start live capture for a specific device"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        # Check if device exists
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        # Check if device is active
        if not device.get("is_active", True):
            return jsonify({"error": "Device is not active"}), 400

        success = start_device_capture(device_id)

        if success:
            return jsonify(
                {
                    "message": f"Đã bật thu dữ liệu cho thiết bị {device_id}",
                    "device_id": device_id,
                }
            )
        else:
            return jsonify(
                {"error": f"Failed to start live capture for device {device_id}"}
            ), 500

    except Exception as e:
        error_message = f"Error starting capture for device {device_id}: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/capture/stop", methods=["POST"])
def stop_single_device_capture(device_id):
    """Stop live capture for a specific device"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        # Check if device exists
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        success = stop_device_capture(device_id)

        if success:
            return jsonify(
                {
                    "message": f"Đã tắt thu dữ liệu cho thiết bị {device_id}",
                    "device_id": device_id,
                }
            )
        else:
            return jsonify(
                {"error": f"Failed to stop live capture for device {device_id}"}
            ), 500

    except Exception as e:
        error_message = f"Error stopping capture for device {device_id}: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


@bp.route("/devices/capture/status", methods=["GET"])
def get_devices_capture_status():
    """Get live capture status for all devices"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        # Get basic capture status
        status = get_capture_status()

        # Get device health information
        from app.services.multi_device_live_capture import device_health_monitor

        health_stats = device_health_monitor.get_all_stats()

        # Combine with device information
        all_devices = config_manager.get_all_devices()
        device_status = []

        for device in all_devices:
            device_id = device.get("id")
            is_capturing = multi_device_manager.is_device_active(device_id)
            health_info = device_health_monitor.get_device_stats(device_id)
            is_healthy = device_health_monitor.is_device_healthy(device_id)

            device_status.append(
                {
                    "device_id": device_id,
                    "device_name": device.get("name", "Unknown"),
                    "is_active": device.get("is_active", True),
                    "is_capturing": is_capturing,
                    "is_healthy": is_healthy,
                    "health_stats": health_info,
                }
            )

        return jsonify({"overall_status": status, "devices": device_status})

    except Exception as e:
        error_message = f"Error getting capture status: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500


@bp.route("/devices/<device_id>/capture/status", methods=["GET"])
def get_single_device_capture_status(device_id):
    """Get live capture status for a specific device"""
    if not LIVE_CAPTURE_AVAILABLE:
        return jsonify({"error": "Live capture service is not available"}), 503

    try:
        # Check if device exists
        device = config_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404

        # Get device health information
        from app.services.multi_device_live_capture import device_health_monitor

        is_capturing = multi_device_manager.is_device_active(device_id)
        health_info = device_health_monitor.get_device_stats(device_id)
        is_healthy = device_health_monitor.is_device_healthy(device_id)

        return jsonify(
            {
                "device_id": device_id,
                "device_name": device.get("name", "Unknown"),
                "is_active": device.get("is_active", True),
                "is_capturing": is_capturing,
                "is_healthy": is_healthy,
                "health_stats": health_info,
            }
        )

    except Exception as e:
        error_message = f"Error getting capture status for device {device_id}: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({"error": error_message}), 500

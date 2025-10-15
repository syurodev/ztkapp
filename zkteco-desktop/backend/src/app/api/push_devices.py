"""
Push Protocol API Controller

This module provides Flask API endpoints for ZKTeco Push Protocol devices.
Push devices actively connect to these endpoints to send data and receive commands.

Endpoints:
- GET  /iclock/getrequest - Device ping for command checking
- GET  /iclock/cdata      - Device handshake
- POST /iclock/cdata      - Device data upload (ATTLOG, OPERLOG, BIODATA)
- POST /iclock/fdata      - Biometric file upload
- GET  /iclock/devicecmd  - Device command check (legacy)

API for manual operations:
- POST /api/push/devices/<serial>/command - Queue command for device
- GET  /api/push/devices/<serial>/status  - Get device status

References:
- ZKTeco PUSH Protocol Documentation
- push_protocol_service.py
"""

from flask import Blueprint, request, jsonify, Response, current_app
from typing import Dict, Any

from app.services.push_protocol_service import push_protocol_service
from app.shared.logger import app_logger


# ============================================================================
# BLUEPRINT SETUP
# ============================================================================

push_devices_bp = Blueprint('push_devices', __name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_query_params() -> Dict[str, Any]:
    """
    Get query parameters from request as dictionary.

    Returns:
        Dict of query parameters

    Example:
        ?SN=ABC123&options=all → {'SN': 'ABC123', 'options': 'all'}
    """
    return request.args.to_dict()


def _create_text_response(text: str) -> Response:
    """
    Create plain text response with proper headers.

    ZKTeco devices expect plain text responses with specific formatting.

    Args:
        text: Response text (should end with \\r\\n)

    Returns:
        Flask Response object with Content-Type: text/plain

    Note:
        All responses to device must end with \\r\\n
    """
    response = Response(text, mimetype='text/plain; charset=utf-8')
    return response


# ============================================================================
# PUSH PROTOCOL ENDPOINTS (Device-facing)
# ============================================================================

@push_devices_bp.route('/iclock/getrequest', methods=['GET'])
def device_ping():
    """
    Device ping endpoint - Check for pending commands.

    Device calls this endpoint periodically (e.g., every 30 seconds) to:
    1. Notify server it's online
    2. Check if there are any commands to execute

    Query Parameters:
        SN (str): Device serial number
        options (str, optional): Device options
        pushver (str, optional): Push protocol version
        language (int, optional): Language code

    Returns:
        Response: Plain text response
            - 'OK\\r\\n' if no commands
            - 'C:command\\r\\n' if command pending

    Example Request:
        GET /iclock/getrequest?SN=ABC123456&options=all&pushver=3.0

    Example Responses:
        OK\\r\\n
        C:DATA UPDATE USERINFO\\r\\n
    """
    try:
        query_params = _get_query_params()

        app_logger.debug(f"[PUSH API] Device ping: {query_params}")

        # Handle ping and get response (OK or command)
        response_text = push_protocol_service.handle_device_ping(query_params)

        return _create_text_response(response_text)

    except Exception as e:
        app_logger.error(f"Error in device_ping: {e}", exc_info=True)
        # Always return OK to prevent device from showing error
        return _create_text_response("OK\r\n")


@push_devices_bp.route('/iclock/cdata', methods=['GET'])
def device_handshake():
    """
    Device handshake endpoint - Initial connection establishment.

    Device calls this endpoint when:
    1. First connecting to server
    2. Periodically to maintain connection

    Query Parameters:
        SN (str): Device serial number
        options (str, optional): Device options

    Returns:
        Response: Plain text 'OK\\r\\n'

    Example Request:
        GET /iclock/cdata?SN=ABC123456&options=all

    Example Response:
        OK\\r\\n
    """
    try:
        query_params = _get_query_params()

        app_logger.debug(f"[PUSH API] Device handshake: {query_params}")

        # Handle handshake
        response_text = push_protocol_service.handle_handshake(query_params)

        return _create_text_response(response_text)

    except Exception as e:
        app_logger.error(f"Error in device_handshake: {e}", exc_info=True)
        return _create_text_response("OK\r\n")


@push_devices_bp.route('/iclock/cdata', methods=['POST'])
def device_data_upload():
    """
    Device data upload endpoint - Receive data from device.

    Device posts data to this endpoint with 'table' query parameter indicating data type.

    Query Parameters:
        SN (str): Device serial number
        table (str): Data table type
            - 'ATTLOG': Attendance records
            - 'OPERLOG': User information and operation logs
            - 'BIODATA': Biometric templates (face/fingerprint)
        Stamp (str, optional): Timestamp of data
        OpStamp (str, optional): Operation stamp

    Request Body:
        Raw text data in table-specific format

    Returns:
        Response: Plain text 'OK\\r\\n'

    Example Request (ATTLOG):
        POST /iclock/cdata?SN=ABC123&table=ATTLOG&Stamp=9999
        Content-Type: text/plain

        1001\t2025-01-09 15:30:00\t0\t1
        1002\t2025-01-09 15:31:00\t1\t15

    Example Request (OPERLOG):
        POST /iclock/cdata?SN=ABC123&table=OPERLOG
        Content-Type: text/plain

        USER PIN=1001 Name=John Doe Grp=1 Pri=0 Verify=1 TZ=0

    Example Request (BIODATA):
        POST /iclock/cdata?SN=ABC123&table=BIODATA
        Content-Type: text/plain

        Pin=1001&Tmp=<base64_encoded_template>
    """
    try:
        query_params = _get_query_params()
        table_type = query_params.get('table', 'UNKNOWN')

        # Get raw body data
        raw_data = request.get_data(as_text=True)

        app_logger.info(
            f"[PUSH API] Data upload: table={table_type}, "
            f"SN={query_params.get('SN')}, "
            f"data_length={len(raw_data)}"
        )

        # Log first 200 chars of data for debugging
        app_logger.debug(f"[PUSH API] Data preview: {raw_data[:200]}")

        # Route to appropriate handler based on table type
        if table_type == 'ATTLOG':
            # Attendance records
            records, saved_count = push_protocol_service.handle_attendance_data(
                raw_data, query_params
            )
            app_logger.info(
                f"[PUSH API] OK ATTLOG processed: {len(records)} records, {saved_count} saved"
            )

        elif table_type == 'OPERLOG':
            # User information
            users, saved_count = push_protocol_service.handle_user_data(
                raw_data, query_params
            )
            app_logger.info(
                f"[PUSH API] OK OPERLOG processed: {len(users)} users, {saved_count} saved"
            )

        elif table_type == 'BIODATA':
            # Biometric templates
            filepath = push_protocol_service.handle_biodata(
                raw_data, query_params
            )
            if filepath:
                app_logger.info(f"[PUSH API] OK BIODATA saved: {filepath}")
            else:
                app_logger.warning("[PUSH API] ⚠ BIODATA processing failed")

        else:
            # Unknown table type
            app_logger.warning(f"[PUSH API] Unknown table type: {table_type}")
            app_logger.debug(f"[PUSH API] Raw data: {raw_data[:500]}")

        # Always return OK to acknowledge receipt
        return _create_text_response("OK\r\n")

    except Exception as e:
        app_logger.error(f"Error in device_data_upload: {e}", exc_info=True)
        # Return OK to prevent device from retrying indefinitely
        return _create_text_response("OK\r\n")


@push_devices_bp.route('/iclock/fdata', methods=['POST'])
def device_file_upload():
    """
    Device file upload endpoint - Receive binary biometric files.

    Device posts raw binary files (face/fingerprint templates) to this endpoint.
    This is less common than BIODATA in cdata endpoint.

    Query Parameters:
        SN (str): Device serial number
        PIN (str, optional): User ID

    Request Body:
        Raw binary data

    Returns:
        Response: Plain text 'OK\\r\\n'

    Example Request:
        POST /iclock/fdata?SN=ABC123&PIN=1001
        Content-Type: application/octet-stream

        <binary data>
    """
    try:
        query_params = _get_query_params()

        # Get raw binary data
        file_data = request.get_data()

        app_logger.info(
            f"[PUSH API] File upload: SN={query_params.get('SN')}, "
            f"PIN={query_params.get('PIN')}, "
            f"size={len(file_data)} bytes"
        )

        # Handle file data
        filepath = push_protocol_service.handle_file_data(file_data, query_params)

        if filepath:
            app_logger.info(f"[PUSH API] OK File saved: {filepath}")
        else:
            app_logger.warning("[PUSH API] ⚠ File processing failed")

        return _create_text_response("OK\r\n")

    except Exception as e:
        app_logger.error(f"Error in device_file_upload: {e}", exc_info=True)
        return _create_text_response("OK\r\n")


@push_devices_bp.route('/iclock/devicecmd', methods=['GET'])
def device_command_check():
    """
    Device command check endpoint (legacy).

    Some older devices may use this endpoint instead of /iclock/getrequest.
    For most modern devices, commands are delivered via /iclock/getrequest.

    Query Parameters:
        SN (str): Device serial number

    Returns:
        Response: Plain text (empty string or command)

    Note:
        This endpoint is kept for backward compatibility.
        Prefer using /iclock/getrequest for command delivery.
    """
    try:
        query_params = _get_query_params()

        app_logger.debug(f"[PUSH API] Legacy device command check: {query_params}")

        # Return empty response (no commands via this endpoint)
        return _create_text_response("")

    except Exception as e:
        app_logger.error(f"Error in device_command_check: {e}", exc_info=True)
        return _create_text_response("")


# ============================================================================
# MANAGEMENT API ENDPOINTS (Web UI/Admin-facing)
# ============================================================================

@push_devices_bp.route('/api/push/devices/<serial_number>/command', methods=['POST'])
def queue_device_command(serial_number: str):
    """
    Queue a command to be sent to device on next ping.

    This is a management API for web UI to send commands to devices.

    Path Parameters:
        serial_number (str): Device serial number

    Request Body (JSON):
        {
            "command": "DATA UPDATE USERINFO"
        }

    Common Commands:
        - 'DATA UPDATE USERINFO': Request device to upload all users
        - 'DATA UPDATE FINGERTMP': Request device to upload fingerprints
        - 'DATA QUERY ATTLOG': Request device to upload attendance logs
        - 'CLEAR DATA': Clear device memory

    Returns:
        JSON: Success status and queued command

    Example Request:
        POST /api/push/devices/ABC123456/command
        Content-Type: application/json

        {
            "command": "DATA UPDATE USERINFO"
        }

    Example Response:
        {
            "success": true,
            "message": "Đã đưa lệnh vào hàng đợi thành công",
            "serial_number": "ABC123456",
            "command": "DATA UPDATE USERINFO"
        }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        command = data.get('command')

        if not command:
            return jsonify({
                "success": False,
                "error": "Missing 'command' field in request body"
            }), 400

        # Queue command
        success = push_protocol_service.queue_command(serial_number, command)

        if success:
            app_logger.info(
                f"[PUSH API] Command queued via API: "
                f"SN={serial_number}, command={command}"
            )

            return jsonify({
                "success": True,
                "message": "Đã đưa lệnh vào hàng đợi. Thiết bị sẽ nhận ở lần ping tiếp theo.",
                "serial_number": serial_number,
                "command": command
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to queue command"
            }), 500

    except Exception as e:
        app_logger.error(f"Error in queue_device_command: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@push_devices_bp.route('/api/push/devices/<serial_number>/upload-users', methods=['POST'])
def request_user_upload(serial_number: str):
    """
    Request device to upload all user information.

    This is a convenience endpoint that queues the 'DATA UPDATE USERINFO' command.

    Path Parameters:
        serial_number (str): Device serial number

    Returns:
        JSON: Success status

    Example Request:
        POST /api/push/devices/ABC123456/upload-users

    Example Response:
        {
            "success": true,
            "message": "Đã yêu cầu thiết bị gửi danh sách người dùng. Thiết bị sẽ tải lên ở lần ping tiếp theo.",
            "serial_number": "ABC123456"
        }
    """
    try:
        command = "DATA UPDATE USERINFO"

        success = push_protocol_service.queue_command(serial_number, command)

        if success:
            app_logger.info(
                f"[PUSH API] User upload requested for device {serial_number}"
            )

            return jsonify({
                "success": True,
                "message": "Đã yêu cầu thiết bị gửi danh sách người dùng. Thiết bị sẽ tải lên ở lần ping tiếp theo.",
                "serial_number": serial_number,
                "command": command
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to queue command"
            }), 500

    except Exception as e:
        app_logger.error(f"Error in request_user_upload: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@push_devices_bp.route('/api/push/devices/<serial_number>/upload-attendance', methods=['POST'])
def request_attendance_upload(serial_number: str):
    """
    Request device to upload attendance logs.

    This is a convenience endpoint that queues the 'DATA QUERY ATTLOG' command.

    Path Parameters:
        serial_number (str): Device serial number

    Returns:
        JSON: Success status

    Example Request:
        POST /api/push/devices/ABC123456/upload-attendance

    Example Response:
        {
            "success": true,
            "message": "Đã yêu cầu thiết bị gửi dữ liệu chấm công. Thiết bị sẽ tải lên ở lần ping tiếp theo.",
            "serial_number": "ABC123456"
        }
    """
    try:
        command = "DATA QUERY ATTLOG"

        success = push_protocol_service.queue_command(serial_number, command)

        if success:
            app_logger.info(
                f"[PUSH API] Attendance upload requested for device {serial_number}"
            )

            return jsonify({
                "success": True,
                "message": "Đã yêu cầu thiết bị gửi dữ liệu chấm công. Thiết bị sẽ tải lên ở lần ping tiếp theo.",
                "serial_number": serial_number,
                "command": command
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to queue command"
            }), 500

    except Exception as e:
        app_logger.error(f"Error in request_attendance_upload: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@push_devices_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors for push protocol endpoints"""
    app_logger.warning(f"[PUSH API] 404 Not Found: {request.url}")

    # For device endpoints, return OK to prevent errors
    if request.path.startswith('/iclock/'):
        return _create_text_response("OK\r\n")

    # For API endpoints, return JSON error
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404


@push_devices_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors for push protocol endpoints"""
    app_logger.error(f"[PUSH API] 500 Internal Error: {error}", exc_info=True)

    # For device endpoints, return OK to prevent errors
    if request.path.startswith('/iclock/'):
        return _create_text_response("OK\r\n")

    # For API endpoints, return JSON error
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500

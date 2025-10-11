import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.device import Device
from app.database.connection import db_manager

class DeviceRepository:
    """Device database operations"""

    def create(self, device: Device) -> Device:
        """Create new device"""
        device_info_json = json.dumps(device.device_info) if device.device_info else None

        query = '''
            INSERT INTO devices (
                id, name, ip, port, password, timeout, retry_count,
                retry_delay, ping_interval, force_udp, is_active, device_type, device_info, serial_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        db_manager.execute_query(query, (
            device.id, device.name, device.ip, device.port, device.password,
            device.timeout, device.retry_count, device.retry_delay, device.ping_interval,
            device.force_udp, device.is_active, device.device_type, device_info_json, device.serial_number
        ))

        return self.get_by_id(device.id)

    def get_by_id(self, device_id: str) -> Optional[Device]:
        """Get device by ID"""
        row = db_manager.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        return self._row_to_device(row) if row else None

    def get_all(self) -> List[Device]:
        """Get all devices"""
        rows = db_manager.fetch_all("SELECT * FROM devices ORDER BY created_at DESC")
        return [self._row_to_device(row) for row in rows]

    def update(self, device_id: str, updates: Dict[str, Any]) -> bool:
        """Update device"""
        if 'device_info' in updates and updates['device_info']:
            updates['device_info'] = json.dumps(updates['device_info'])

        updates['updated_at'] = datetime.now()

        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        query = f"UPDATE devices SET {set_clause} WHERE id = ?"

        cursor = db_manager.execute_query(query, (*updates.values(), device_id))
        return cursor.rowcount > 0

    def delete(self, device_id: str) -> bool:
        """Delete device"""
        from app.shared.logger import app_logger

        try:
            app_logger.info(f"DeviceRepository: Starting delete for device_id: {device_id}")

            # Check if device exists first
            existing = db_manager.fetch_one("SELECT id, name FROM devices WHERE id = ?", (device_id,))
            if existing:
                app_logger.info(f"DeviceRepository: Found device to delete: {existing[1]} ({existing[0]})")
            else:
                app_logger.warning(f"DeviceRepository: Device not found for deletion: {device_id}")
                return False

            app_logger.info(f"DeviceRepository: Executing DELETE query for device_id: {device_id}")

            # Execute DELETE and get rowcount within context
            with db_manager.get_cursor() as cursor:
                cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
                rowcount = cursor.rowcount
                success = rowcount > 0
                app_logger.info(f"DeviceRepository: DELETE query affected {rowcount} rows, success: {success}")

            return success

        except Exception as e:
            app_logger.error(f"DeviceRepository: Error deleting device {device_id}: {e}", exc_info=True)
            raise

    def get_by_serial_number(self, serial_number: str) -> Optional[Device]:
        """Get device by serial number"""
        row = db_manager.fetch_one("SELECT * FROM devices WHERE serial_number = ?", (serial_number,))
        return self._row_to_device(row) if row else None

    def _row_to_device(self, row) -> Device:
        """Convert database row to Device object"""
        device_info = json.loads(row['device_info']) if row['device_info'] else {}

        # Handle serial_number safely for SQLite Row object
        try:
            serial_number = row['serial_number'] if 'serial_number' in row.keys() else None
        except (KeyError, IndexError):
            serial_number = None

        # Handle device_type safely, default to 'pull' for backward compatibility
        try:
            device_type = row['device_type'] if 'device_type' in row.keys() else 'pull'
        except (KeyError, IndexError):
            device_type = 'pull'

        return Device(
            id=row['id'],
            name=row['name'],
            ip=row['ip'],
            port=row['port'],
            password=row['password'],
            timeout=row['timeout'],
            retry_count=row['retry_count'],
            retry_delay=row['retry_delay'],
            ping_interval=row['ping_interval'],
            force_udp=bool(row['force_udp']),
            is_active=bool(row['is_active']),
            device_type=device_type,
            device_info=device_info,
            serial_number=serial_number,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

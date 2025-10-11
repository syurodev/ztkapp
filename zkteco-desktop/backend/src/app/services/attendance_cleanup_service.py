"""
Attendance Cleanup Service

Automatically removes old attendance records that have been synced or skipped
to keep the database size manageable and improve performance.
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from app.database.connection import db_manager
from app.shared.logger import app_logger
from app.models.attendance import SyncStatus


class AttendanceCleanupService:
    """Service for cleaning up old attendance records"""

    def __init__(self):
        self.logger = app_logger

    def cleanup_old_attendance(self, retention_days: int = 365) -> Dict[str, Any]:
        """
        Delete attendance records older than retention period.

        Only deletes records with sync_status = 'synced' or 'skipped'.
        NEVER deletes 'pending' records to prevent data loss.

        Args:
            retention_days: Number of days to retain data (default: 365 = 1 year)

        Returns:
            Dictionary containing cleanup results
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

            self.logger.info(f"Starting attendance cleanup: removing records older than {retention_days} days")
            self.logger.info(f"Cutoff date: {cutoff_str}")

            # First, get count of records to be deleted
            count_query = """
                SELECT COUNT(*) as count
                FROM attendance_logs
                WHERE timestamp < ?
                AND (sync_status = ? OR sync_status = ?)
            """
            count_result = db_manager.fetch_one(
                count_query,
                (cutoff_str, SyncStatus.SYNCED, SyncStatus.SKIPPED)
            )
            records_to_delete = count_result['count'] if count_result else 0

            if records_to_delete == 0:
                self.logger.info("No old records found to cleanup")
                return {
                    'success': True,
                    'deleted_count': 0,
                    'retention_days': retention_days,
                    'cutoff_date': cutoff_str,
                    'message': 'No records to cleanup'
                }

            # Get statistics before deletion
            stats_before = self._get_cleanup_stats(cutoff_str)

            # Delete old synced and skipped records
            delete_query = """
                DELETE FROM attendance_logs
                WHERE timestamp < ?
                AND (sync_status = ? OR sync_status = ?)
            """

            cursor = db_manager.execute_query(
                delete_query,
                (cutoff_str, SyncStatus.SYNCED, SyncStatus.SKIPPED)
            )

            deleted_count = cursor.rowcount

            # Get statistics after deletion
            stats_after = self._get_total_stats()

            self.logger.info(f"Cleanup completed: deleted {deleted_count} old attendance records")
            self.logger.info(f"Remaining records: {stats_after['total_records']}")

            return {
                'success': True,
                'deleted_count': deleted_count,
                'retention_days': retention_days,
                'cutoff_date': cutoff_str,
                'stats_before': stats_before,
                'stats_after': stats_after,
                'message': f'Successfully deleted {deleted_count} old records'
            }

        except Exception as e:
            self.logger.error(f"Error during attendance cleanup: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Cleanup failed'
            }

    def _get_cleanup_stats(self, cutoff_date: str) -> Dict[str, Any]:
        """Get statistics about records to be cleaned up"""
        try:
            # Count records that will be deleted
            query = """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as synced_count,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as skipped_count
                FROM attendance_logs
                WHERE timestamp < ?
                AND (sync_status = ? OR sync_status = ?)
            """
            result = db_manager.fetch_one(
                query,
                (SyncStatus.SYNCED, SyncStatus.SKIPPED, cutoff_date,
                 SyncStatus.SYNCED, SyncStatus.SKIPPED)
            )

            return {
                'records_to_delete': result['total'] if result else 0,
                'synced': result['synced_count'] if result else 0,
                'skipped': result['skipped_count'] if result else 0
            }
        except Exception as e:
            self.logger.error(f"Error getting cleanup stats: {e}")
            return {
                'records_to_delete': 0,
                'synced': 0,
                'skipped': 0
            }

    def _get_total_stats(self) -> Dict[str, Any]:
        """Get total database statistics"""
        try:
            query = """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as synced_count,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as skipped_count,
                    SUM(CASE WHEN sync_status = ? THEN 1 ELSE 0 END) as error_count
                FROM attendance_logs
            """
            result = db_manager.fetch_one(
                query,
                (SyncStatus.PENDING, SyncStatus.SYNCED, SyncStatus.SKIPPED, SyncStatus.ERROR)
            )

            return {
                'total_records': result['total'] if result else 0,
                'pending': result['pending_count'] if result else 0,
                'synced': result['synced_count'] if result else 0,
                'skipped': result['skipped_count'] if result else 0,
                'error': result['error_count'] if result else 0
            }
        except Exception as e:
            self.logger.error(f"Error getting total stats: {e}")
            return {
                'total_records': 0,
                'pending': 0,
                'synced': 0,
                'skipped': 0,
                'error': 0
            }

    def get_cleanup_preview(self, retention_days: int = 365) -> Dict[str, Any]:
        """
        Preview what would be deleted without actually deleting.
        Useful for checking before running cleanup.

        Args:
            retention_days: Number of days to retain data

        Returns:
            Dictionary containing preview information
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

            stats = self._get_cleanup_stats(cutoff_str)
            total_stats = self._get_total_stats()

            # Get oldest and newest record dates
            oldest_query = "SELECT MIN(timestamp) as oldest FROM attendance_logs"
            newest_query = "SELECT MAX(timestamp) as newest FROM attendance_logs"

            oldest = db_manager.fetch_one(oldest_query)
            newest = db_manager.fetch_one(newest_query)

            return {
                'success': True,
                'retention_days': retention_days,
                'cutoff_date': cutoff_str,
                'records_to_delete': stats['records_to_delete'],
                'records_to_keep': total_stats['total_records'] - stats['records_to_delete'],
                'breakdown': {
                    'synced': stats['synced'],
                    'skipped': stats['skipped']
                },
                'current_stats': total_stats,
                'oldest_record': oldest['oldest'] if oldest else None,
                'newest_record': newest['newest'] if newest else None
            }

        except Exception as e:
            self.logger.error(f"Error getting cleanup preview: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global service instance
attendance_cleanup_service = AttendanceCleanupService()

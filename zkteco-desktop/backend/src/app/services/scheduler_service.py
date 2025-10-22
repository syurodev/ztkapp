import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from app.shared.logger import app_logger
from app.services.attendance_sync_service import attendance_sync_service
from app.services.attendance_cleanup_service import attendance_cleanup_service
from app.services.door_access_sync_service import door_access_sync_service
from app.config.config_manager import config_manager
from app.services.live_capture_service import ensure_pull_devices_capturing


class SchedulerService:
    """Service for managing scheduled tasks"""

    def __init__(self):
        self.scheduler = None
        self.logger = app_logger
        self.is_running = False

    def start(self):
        """Start the scheduler"""
        if self.scheduler and self.is_running:
            self.logger.warning("Scheduler is already running")
            return

        try:
            self.scheduler = BackgroundScheduler()

            # Add event listeners for job monitoring
            self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)

            # Add daily attendance sync job
            self._add_daily_attendance_sync_job()

            # Add frequent first checkin sync job
            self._add_first_checkin_sync_job()

            # Add periodic user sync job (every 30 seconds)
            self._add_periodic_user_sync_job()

            # Add live capture health check job
            self._add_live_capture_health_job()

            # Add monthly attendance cleanup job (runs on 1st day of month at 2 AM)
            self._add_monthly_cleanup_job()

            # Add daily door access sync job (runs at 23:59 every day)
            self._add_daily_door_access_sync_job()

            # Start the scheduler
            self.scheduler.start()
            self.is_running = True

            self.logger.info("Scheduler service started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler and self.is_running:
            try:
                self.scheduler.shutdown(wait=False)
                self.is_running = False
                self.logger.info("Scheduler service stopped")
            except Exception as e:
                self.logger.error(f"Error stopping scheduler: {e}")

    def _add_daily_attendance_sync_job(self):
        """Add daily attendance sync job to scheduler"""
        try:
            # Schedule job to run at 23:59 every day
            trigger = CronTrigger(hour=23, minute=59)

            self.scheduler.add_job(
                func=self._run_daily_attendance_sync,
                trigger=trigger,
                id="daily_attendance_sync",
                name="Daily Attendance Sync",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=300,  # 5 minutes grace period
            )

            self.logger.info("Daily attendance sync job scheduled for 23:59 every day")

        except Exception as e:
            self.logger.error(f"Failed to add daily attendance sync job: {e}")
            raise

    def _add_daily_door_access_sync_job(self):
        """Add daily door access sync job to scheduler"""
        try:
            # Schedule job to run at 23:59 every day
            trigger = CronTrigger(hour=23, minute=59)

            self.scheduler.add_job(
                func=self._run_daily_door_access_sync,
                trigger=trigger,
                id="daily_door_access_sync",
                name="Daily Door Access Sync",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=300,  # 5 minutes grace period
            )

            self.logger.info("Daily door access sync job scheduled for 23:59 every day")

        except Exception as e:
            self.logger.error(f"Failed to add daily door access sync job: {e}")
            raise

    def _add_first_checkin_sync_job(self):
        """Add high-frequency job to sync first check-ins every 30 seconds"""
        try:
            trigger = IntervalTrigger(seconds=30)

            self.scheduler.add_job(
                func=self._run_first_checkin_sync,
                trigger=trigger,
                id="first_checkin_sync",
                name="First Checkin Sync (30s interval)",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=15,
            )

            self.logger.info(
                "OK First checkin sync job scheduled to run every 30 seconds"
            )

        except Exception as e:
            self.logger.error(f"Failed to add first checkin sync job: {e}")
            raise

    def _add_periodic_user_sync_job(self):
        """Add periodic user sync job to scheduler (every 30 seconds)"""
        try:
            # Schedule job to run every 5 minutes
            trigger = IntervalTrigger(seconds=30)

            self.scheduler.add_job(
                func=self._run_periodic_user_sync,
                trigger=trigger,
                id="periodic_user_sync",
                name="Periodic User Sync from External API",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=60,  # 1 minute grace period
            )

            self.logger.info(
                "OK Periodic user sync job scheduled to run every 5 minutes"
            )

        except Exception as e:
            self.logger.error(f"Failed to add periodic user sync job: {e}")
            raise

    def _add_live_capture_health_job(self):
        """Add job that keeps pull-device live capture threads alive."""
        try:
            interval_seconds = int(os.getenv("LIVE_CAPTURE_HEALTH_INTERVAL", "45"))
            trigger = IntervalTrigger(seconds=interval_seconds)

            self.scheduler.add_job(
                func=self._run_live_capture_health_check,
                trigger=trigger,
                id="live_capture_health_check",
                name="Live Capture Health Check",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=interval_seconds,
            )

            self.logger.info(
                "Live capture health check scheduled every %s seconds",
                interval_seconds,
            )

        except Exception as e:
            self.logger.error(f"Failed to add live capture health job: {e}")
            raise

    def _add_monthly_cleanup_job(self):
        """Add monthly cleanup job to remove old synced/skipped attendance records"""
        try:
            # Schedule job to run on 1st day of every month at 2 AM
            trigger = CronTrigger(day=1, hour=2, minute=0)

            self.scheduler.add_job(
                func=self._run_monthly_cleanup,
                trigger=trigger,
                id="monthly_attendance_cleanup",
                name="Monthly Attendance Cleanup (Remove old synced/skipped records)",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=3600,  # 1 hour grace period
            )

            self.logger.info(
                "OK Monthly attendance cleanup job scheduled for 1st day of month at 2:00 AM"
            )

        except Exception as e:
            self.logger.error(f"Failed to add monthly cleanup job: {e}")
            raise

    def _run_periodic_user_sync(self):
        """Execute periodic user sync job (works for all device types)

        This job fetches employee details from external API and updates local user records.
        Works for both pull and push devices as it only updates the database,
        not device-specific operations.
        """
        try:
            from app.services.device_service import get_zk_service

            zk_service = get_zk_service()
            result = zk_service.sync_all_users_from_external_api()

            if result.get("success"):
                updated_count = result.get("updated_count", 0)
                if updated_count > 0:
                    self.logger.info(
                        f"[CRON] Periodic User Sync: Updated {updated_count} users"
                    )
            else:
                error_msg = result.get("error") or result.get(
                    "message", "Unknown error"
                )
                self.logger.warning(f"[CRON] Periodic User Sync failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"[CRON] Periodic User Sync error: {e}")

    def _run_first_checkin_sync(self):
        """Execute frequent first-checkin sync job (works for both pull and push devices)"""
        try:
            # Sync first checkins only
            attendance_result = attendance_sync_service.sync_first_checkins()

            if attendance_result.get("success"):
                synced = attendance_result.get("synced_records", 0)
                if synced > 0:
                    self.logger.info(
                        f"[CRON] First Checkin: Synced {synced} attendance records"
                    )
            else:
                self.logger.warning(
                    f"[CRON] First Checkin attendance sync error: {attendance_result.get('error', 'unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"[CRON] First Checkin error: {e}")

    def _fetch_attendance_from_all_devices(self):
        """Fetch attendance logs from all active pull devices before sync"""
        try:
            # Get all active devices
            active_devices = config_manager.get_devices_by_status(is_active=True)

            if not active_devices:
                self.logger.warning("No active devices found for attendance fetch")
                return

            # Filter to only pull devices (push devices send data automatically)
            pull_devices = [
                d for d in active_devices if d.get("device_type", "pull") == "pull"
            ]
            push_count = len(active_devices) - len(pull_devices)

            if push_count > 0:
                self.logger.info(
                    f"Skipping {push_count} push device(s) - they push data automatically"
                )

            if not pull_devices:
                self.logger.info("No pull devices found for attendance fetch")
                return

            self.logger.info(
                f"Fetching attendance logs from {len(pull_devices)} active pull device(s)"
            )

            total_fetched = 0
            successful_devices = 0

            for device in pull_devices:
                device_id = device.get("id")
                device_name = device.get("name", device_id)

                try:
                    self.logger.info(
                        f"Fetching attendance from device: {device_name} ({device_id})"
                    )

                    # Import here to avoid circular import
                    from app.services.device_service import get_zk_service

                    zk_service = get_zk_service(device_id)

                    # Fetch attendance logs from device
                    result = zk_service.get_attendance()

                    if result and "sync_stats" in result:
                        new_records = result["sync_stats"].get("new_records_saved", 0)
                        total_fetched += new_records
                        self.logger.info(
                            f"Device {device_name}: fetched {new_records} new attendance records"
                        )
                    else:
                        self.logger.info(
                            f"Device {device_name}: no new records or unexpected response format"
                        )

                    successful_devices += 1

                except Exception as device_error:
                    self.logger.error(
                        f"Error fetching attendance from device {device_name} ({device_id}): {device_error}"
                    )
                    # Continue with next device
                    continue

            self.logger.info(
                f"Attendance fetch completed: {total_fetched} total new records from "
                f"{successful_devices}/{len(pull_devices)} pull devices"
            )

        except Exception as e:
            self.logger.error(f"Error in _fetch_attendance_from_all_devices: {e}")
            # Don't raise - let sync continue even if fetch fails

    def _run_monthly_cleanup(self):
        """Execute monthly cleanup job to remove old synced/skipped attendance records"""
        try:
            # Get retention days from app settings (default: 365 days = 1 year)
            try:
                from app.repositories.setting_repository import setting_repo

                retention_setting = setting_repo.get("cleanup_retention_days")
                retention_days = (
                    int(retention_setting.value) if retention_setting else 365
                )
            except Exception:
                retention_days = 365  # Default to 1 year

            # Run cleanup
            result = attendance_cleanup_service.cleanup_old_attendance(retention_days)

            if result["success"]:
                deleted_count = result.get("deleted_count", 0)
                if deleted_count > 0:
                    self.logger.info(
                        f"[CRON] Monthly Cleanup: Deleted {deleted_count} old records (retention: {retention_days} days)"
                    )
            else:
                self.logger.error(
                    f"[CRON] Monthly Cleanup failed: {result.get('error')}"
                )

        except Exception as e:
            self.logger.error(f"[CRON] Monthly Cleanup error: {e}")

    def _run_live_capture_health_check(self):
        """Ensure live capture remains active for pull devices."""
        try:
            summary = ensure_pull_devices_capturing()

            restarted = summary.get("auto_started", 0)
            if restarted:
                self.logger.info(
                    "[CRON] Live capture health check restarted %s device(s)",
                    restarted,
                )

            for message in summary.get("errors", []):
                self.logger.warning("[CRON] Live capture health warning: %s", message)

        except Exception as e:
            self.logger.error(f"[CRON] Live capture health check error: {e}")

    def _run_daily_attendance_sync(self):
        """Execute daily attendance sync job with multi-day support (works for both pull and push devices)"""
        try:
            # Step 1: Fetch attendance from pull devices
            self._fetch_attendance_from_all_devices()

            # Step 2: Sync to external API
            result = attendance_sync_service.sync_attendance_daily(
                ignore_error_limit=True
            )

            if result["success"]:
                total_count = result.get("count", 0)
                total_dates = result.get("total_dates", 0)

                if total_dates > 0:
                    dates_processed = result.get("dates_processed", [])
                    self.logger.info(
                        f"[CRON] Daily Attendance: Synced {total_count} records across {total_dates} dates: {dates_processed}"
                    )
            else:
                self.logger.error(
                    f"[CRON] Daily Attendance failed: {result.get('error')}"
                )

        except Exception as e:
            self.logger.error(f"[CRON] Daily Attendance error: {e}")
            raise

    def _run_daily_door_access_sync(self):
        """Execute daily door access sync job"""
        try:
            target_date = datetime.now().strftime("%Y-%m-%d")
            result = door_access_sync_service.sync_daily_door_access(target_date)

            if result.get("success"):
                synced_count = result.get("synced_count", 0)
                total_logs = result.get("total_logs", 0)

                if synced_count > 0:
                    self.logger.info(
                        f"[CRON] Door Access: Synced {synced_count} records ({total_logs} logs) for {target_date}"
                    )
            else:
                error_msg = result.get("error", "unknown error")
                self.logger.error(f"[CRON] Door Access failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"[CRON] Door Access error: {e}")

    def _job_executed_listener(self, event):
        """Handle successful job execution events"""
        # Only log at debug level to reduce noise
        self.logger.debug(f"Job '{event.job_id}' executed successfully")

    def _job_error_listener(self, event):
        """Handle job error events"""
        self.logger.error(f"Job '{event.job_id}' crashed: {event.exception}")

    def get_job_status(self, job_id: str = "daily_attendance_sync"):
        """Get status of a specific job"""
        if not self.scheduler:
            return {"running": False, "error": "Scheduler not initialized"}

        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    "running": self.is_running,
                    "job_id": job.id,
                    "job_name": job.name,
                    "next_run_time": str(job.next_run_time)
                    if job.next_run_time
                    else None,
                    "trigger": str(job.trigger),
                }
            else:
                return {"running": False, "error": f"Job {job_id} not found"}

        except Exception as e:
            return {"running": False, "error": str(e)}

    def get_all_jobs(self):
        """Get status of all scheduled jobs"""
        if not self.scheduler:
            return {"running": False, "jobs": []}

        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": str(job.next_run_time)
                        if job.next_run_time
                        else None,
                        "trigger": str(job.trigger),
                    }
                )

            return {"running": self.is_running, "jobs": jobs, "total_jobs": len(jobs)}

        except Exception as e:
            self.logger.error(f"Error getting job list: {e}")
            return {"running": False, "error": str(e)}

    def trigger_job_manually(self, job_id: str = "daily_attendance_sync"):
        """Manually trigger a scheduled job"""
        if not self.scheduler or not self.is_running:
            return {"success": False, "error": "Scheduler not running"}

        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                return {"success": False, "error": f"Job {job_id} not found"}

            # Execute the job manually
            if job_id == "daily_attendance_sync":
                result = attendance_sync_service.sync_attendance_daily()
                return {
                    "success": True,
                    "message": f"Job {job_id} executed manually",
                    "result": result,
                }
            elif job_id == "periodic_user_sync":
                from app.services.device_service import get_zk_service

                zk_service = get_zk_service()
                result = zk_service.sync_all_users_from_external_api()
                return {
                    "success": True,
                    "message": f"Job {job_id} executed manually",
                    "result": result,
                }
            elif job_id == "monthly_attendance_cleanup":
                # Get retention days from settings
                try:
                    from app.repositories.setting_repository import setting_repo

                    retention_setting = setting_repo.get("cleanup_retention_days")
                    retention_days = (
                        int(retention_setting.value) if retention_setting else 365
                    )
                except Exception:
                    retention_days = 365

                result = attendance_cleanup_service.cleanup_old_attendance(
                    retention_days
                )
                return {
                    "success": True,
                    "message": f"Job {job_id} executed manually",
                    "result": result,
                }
            else:
                # For other jobs, just run them
                job.func()
                return {"success": True, "message": f"Job {job_id} executed manually"}

        except Exception as e:
            self.logger.error(f"Error manually triggering job {job_id}: {e}")
            return {"success": False, "error": str(e)}


# Global scheduler instance
scheduler_service = SchedulerService()

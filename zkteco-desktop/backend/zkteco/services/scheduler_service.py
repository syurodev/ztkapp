import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from zkteco.logger import app_logger
from zkteco.services.attendance_sync_service import attendance_sync_service
from zkteco.config.config_manager_sqlite import config_manager


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
                id='daily_attendance_sync',
                name='Daily Attendance Sync',
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=300  # 5 minutes grace period
            )

            self.logger.info("Daily attendance sync job scheduled for 23:59 every day")

        except Exception as e:
            self.logger.error(f"Failed to add daily attendance sync job: {e}")
            raise

    def _fetch_attendance_from_all_devices(self):
        """Fetch attendance logs from all active devices before sync"""
        try:
            # Get all active devices
            active_devices = config_manager.get_devices_by_status(is_active=True)

            if not active_devices:
                self.logger.warning("No active devices found for attendance fetch")
                return

            self.logger.info(f"Fetching attendance logs from {len(active_devices)} active devices")

            total_fetched = 0
            successful_devices = 0

            for device in active_devices:
                device_id = device.get('id')
                device_name = device.get('name', device_id)

                try:
                    self.logger.info(f"Fetching attendance from device: {device_name} ({device_id})")

                    # Import here to avoid circular import
                    from zkteco.services.zk_service import get_zk_service
                    zk_service = get_zk_service()

                    # Fetch attendance logs from device
                    result = zk_service.get_attendance(device_id)

                    if result and 'sync_stats' in result:
                        new_records = result['sync_stats'].get('new_records_saved', 0)
                        total_fetched += new_records
                        self.logger.info(f"Device {device_name}: fetched {new_records} new attendance records")
                    else:
                        self.logger.info(f"Device {device_name}: no new records or unexpected response format")

                    successful_devices += 1

                except Exception as device_error:
                    self.logger.error(f"Error fetching attendance from device {device_name} ({device_id}): {device_error}")
                    # Continue with next device
                    continue

            self.logger.info(
                f"Attendance fetch completed: {total_fetched} total new records from "
                f"{successful_devices}/{len(active_devices)} devices"
            )

        except Exception as e:
            self.logger.error(f"Error in _fetch_attendance_from_all_devices: {e}")
            # Don't raise - let sync continue even if fetch fails

    def _run_daily_attendance_sync(self):
        """Execute daily attendance sync job with multi-day support"""
        job_start_time = datetime.now()
        self.logger.info(f"Starting scheduled daily attendance sync at {job_start_time}")

        try:
            # Step 1: Fetch attendance logs from all active devices to get latest data
            self.logger.info("Step 1: Fetching attendance logs from all active devices")
            self._fetch_attendance_from_all_devices()

            # Step 2: Run the attendance sync for all pending dates (includes today and any missed days)
            self.logger.info("Step 2: Syncing attendance data to external API")
            result = attendance_sync_service.sync_attendance_daily()

            if result['success']:
                dates_processed = result.get('dates_processed', [])
                total_count = result.get('count', 0)
                total_dates = result.get('total_dates', 0)

                if total_dates > 0:
                    self.logger.info(
                        f"Scheduled attendance sync completed successfully: "
                        f"{total_count} records synced across {total_dates} dates: {dates_processed}"
                    )
                else:
                    self.logger.info("No pending attendance records found for sync")
            else:
                self.logger.error(
                    f"Scheduled attendance sync failed: {result.get('error')}"
                )

        except Exception as e:
            self.logger.error(f"Error in scheduled daily attendance sync: {e}")
            raise

        finally:
            duration = datetime.now() - job_start_time
            self.logger.info(f"Daily attendance sync job completed in {duration}")

    def _job_executed_listener(self, event):
        """Handle successful job execution events"""
        self.logger.info(
            f"Job '{event.job_id}' executed successfully at {event.scheduled_run_time}"
        )

    def _job_error_listener(self, event):
        """Handle job error events"""
        self.logger.error(
            f"Job '{event.job_id}' crashed at {event.scheduled_run_time}: {event.exception}"
        )

    def get_job_status(self, job_id: str = 'daily_attendance_sync'):
        """Get status of a specific job"""
        if not self.scheduler:
            return {'running': False, 'error': 'Scheduler not initialized'}

        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    'running': self.is_running,
                    'job_id': job.id,
                    'job_name': job.name,
                    'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                    'trigger': str(job.trigger)
                }
            else:
                return {'running': False, 'error': f'Job {job_id} not found'}

        except Exception as e:
            return {'running': False, 'error': str(e)}

    def get_all_jobs(self):
        """Get status of all scheduled jobs"""
        if not self.scheduler:
            return {'running': False, 'jobs': []}

        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })

            return {
                'running': self.is_running,
                'jobs': jobs,
                'total_jobs': len(jobs)
            }

        except Exception as e:
            self.logger.error(f"Error getting job list: {e}")
            return {'running': False, 'error': str(e)}

    def trigger_job_manually(self, job_id: str = 'daily_attendance_sync'):
        """Manually trigger a scheduled job"""
        if not self.scheduler or not self.is_running:
            return {'success': False, 'error': 'Scheduler not running'}

        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}

            # Execute the job manually
            if job_id == 'daily_attendance_sync':
                result = attendance_sync_service.sync_attendance_daily()
                return {
                    'success': True,
                    'message': f'Job {job_id} executed manually',
                    'result': result
                }
            else:
                # For other jobs, just run them
                job.func()
                return {
                    'success': True,
                    'message': f'Job {job_id} executed manually'
                }

        except Exception as e:
            self.logger.error(f"Error manually triggering job {job_id}: {e}")
            return {'success': False, 'error': str(e)}


# Global scheduler instance
scheduler_service = SchedulerService()
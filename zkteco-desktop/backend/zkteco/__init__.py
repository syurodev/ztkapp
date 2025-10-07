from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
import os
import logging
import sentry_sdk
import atexit
from logging.handlers import RotatingFileHandler
# from zkteco.services.zk_service import get_zk_service  # Lazy load to avoid blocking
from zkteco.controllers.user_controller import bp as user_blueprint
from zkteco.controllers.device_controller import bp as device_blueprint
from zkteco.controllers.attendance_controller import bp as attendance_blueprint
from zkteco.controllers.event_controller import bp as event_blueprint
from zkteco.logger import create_log_handler
from zkteco.services.scheduler_service import scheduler_service
from zkteco.services.live_capture_service import (
    start_multi_device_capture,
    stop_multi_device_capture,
)


class EndpointFilter(logging.Filter):
    """Suppress noisy request logs for specific endpoints."""

    def __init__(self, *paths):
        super().__init__()
        self.paths = paths

    def filter(self, record):
        message = record.getMessage()
        return not any(path in message for path in self.paths)

load_dotenv()

def create_app():
    init_sentry()
    # create and configure the app
    app = Flask(__name__)

    # Enable CORS for all origins including Tauri
    CORS(app, 
         origins=["*"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=True)

    app.config.from_object("zkteco.config.settings")

    handler = create_log_handler()

    # Add the handler to the app's logger
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # Remove health check noise from werkzeug request logs
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(EndpointFilter('/service/status', '/devices/events'))

    # Register the blueprints
    app.register_blueprint(user_blueprint)
    app.register_blueprint(device_blueprint)
    app.register_blueprint(attendance_blueprint)
    app.register_blueprint(event_blueprint)

    # Initialize and start the scheduler
    # When Flask reloader is disabled, WERKZEUG_RUN_MAIN is not set.
    # When reloader is enabled, only the reloader child (== "true") should start the scheduler.
    run_main_flag = os.environ.get('WERKZEUG_RUN_MAIN')
    if run_main_flag == 'true' or run_main_flag is None:
        try:
            scheduler_service.start()
            app.logger.info("Scheduler service started successfully")

            try:
                start_multi_device_capture()
                app.logger.info("Live capture auto-started for active devices")
            except Exception as live_capture_error:
                app.logger.error(
                    f"Failed to auto-start live capture: {live_capture_error}"
                )

            # Register cleanup function to stop services when app shuts down
            def cleanup_services():
                scheduler_service.stop()
                stop_multi_device_capture()

            atexit.register(cleanup_services)

        except Exception as e:
            app.logger.error(f"Failed to start scheduler service: {e}")
    else:
        app.logger.info("Skipping scheduler start in reloader process")

    return app


def init_sentry():
    sentry_sdk.init(
        dsn="https://5f9be5c667e175dcb31118d107c5551b@o4504142684422144.ingest.sentry.io/4506604971819008",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

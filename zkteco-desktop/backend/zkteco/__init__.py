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

    # Register the blueprints
    app.register_blueprint(user_blueprint)
    app.register_blueprint(device_blueprint)
    app.register_blueprint(attendance_blueprint)
    app.register_blueprint(event_blueprint)

    # Initialize and start the scheduler
    try:
        scheduler_service.start()
        app.logger.info("Scheduler service started successfully")

        # Register cleanup function to stop scheduler when app shuts down
        def cleanup_scheduler():
            scheduler_service.stop()

        atexit.register(cleanup_scheduler)

    except Exception as e:
        app.logger.error(f"Failed to start scheduler service: {e}")

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

#!/usr/bin/env python3
"""
ZKTeco Service - Standalone service wrapper for the ZKTeco API
"""

import os
import sys
import signal
import threading
import time
import logging
from dotenv import load_dotenv
from flask import Flask, jsonify
from zkteco import create_app
from zkteco.logger import get_user_log_dir
import psutil

# Load environment variables
load_dotenv()

class ZKTecoService:
    def __init__(self):
        self.app = None
        self.server_thread = None
        self.running = False
        self.setup_logging()

    def setup_logging(self):
        """Setup service logging"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        # Get user-writable log directory
        log_dir = get_user_log_dir()
        log_file_path = os.path.join(log_dir, 'zkteco-service.log')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ZKTecoService')
        self.log_file_path = log_file_path  # Store for use in service endpoints

    def create_service_app(self):
        """Create Flask app with additional service endpoints"""
        app = create_app()

        @app.route('/service/status', methods=['GET'])
        def service_status():
            """Get service status"""
            try:
                pid = os.getpid()
                process = psutil.Process(pid)

                return jsonify({
                    'status': 'running',
                    'pid': pid,
                    'memory_usage': process.memory_info().rss / 1024 / 1024,  # MB
                    'cpu_percent': process.cpu_percent(),
                    'uptime': time.time() - process.create_time(),
                    'threads': process.num_threads()
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/service/stop', methods=['POST'])
        def service_stop():
            """Stop the service"""
            def shutdown_server():
                time.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)

            threading.Thread(target=shutdown_server).start()
            return jsonify({'message': 'Service stopping...'})

        @app.route('/service/restart', methods=['POST'])
        def service_restart():
            """Restart the service"""
            def restart_server():
                time.sleep(1)
                os.execv(sys.executable, ['python'] + sys.argv)

            threading.Thread(target=restart_server).start()
            return jsonify({'message': 'Service restarting...'})

        @app.route('/service/logs', methods=['GET'])
        def service_logs():
            """Get recent service logs"""
            try:
                with open(self.log_file_path, 'r') as f:
                    lines = f.readlines()
                    # Return last 100 lines
                    recent_logs = lines[-100:] if len(lines) > 100 else lines
                    return jsonify({'logs': recent_logs})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        return app

    def start(self):
        """Start the service"""
        self.logger.info("Starting ZKTeco Service...")
        self.app = self.create_service_app()
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        try:
            host = os.getenv('HOST', '0.0.0.0')
            port = int(os.getenv('PORT', 5001))

            self.logger.info(f"Service starting on {host}:{port}")
            self.app.run(host=host, port=port, debug=False, use_reloader=False)

        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            sys.exit(1)

    def stop(self):
        """Stop the service"""
        self.logger.info("Stopping ZKTeco Service...")
        self.running = False
        sys.exit(0)

    def signal_handler(self, signum, frame):
        """Handle system signals"""
        self.logger.info(f"Received signal {signum}")
        self.stop()


def main():
    """Main entry point"""
    try:
        service = ZKTecoService()
        service.start()
    except Exception as e:
        # Print to stderr for debugging
        print(f"Failed to start ZKTeco service: {e}", file=sys.stderr)
        
        # Try to log the error if possible
        try:
            import traceback
            from zkteco.logger import get_user_log_dir
            log_dir = get_user_log_dir()
            error_log_path = os.path.join(log_dir, 'startup_error.log')
            with open(error_log_path, 'a') as f:
                f.write(f"\n--- Startup Error at {time.ctime()} ---\n")
                f.write(f"Error: {e}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
                f.write("--- End Error ---\n\n")
        except Exception:
            pass  # If we can't log, just continue
        
        # Exit with error code
        sys.exit(1)


if __name__ == "__main__":
    main()

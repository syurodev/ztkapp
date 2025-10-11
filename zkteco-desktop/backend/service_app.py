#!/usr/bin/env python3
"""
ZKTeco Service - Standalone service wrapper for the ZKTeco API
"""

import os
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import signal
import threading
import time
import logging
from dotenv import load_dotenv
from flask import Flask, jsonify
from app import create_app
from app.shared.logger import get_user_log_dir
import psutil
import requests
import socket

# Load environment variables
load_dotenv()

class ZKTecoService:
    def __init__(self):
        self.app = None
        self.server_thread = None
        self.running = False
        self.public_ip = None  # Cache public IP in memory
        self.local_ip = None  # Cache local IP in memory
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

    def fetch_local_ip(self):
        """Fetch local IP address (assigned by router) and cache in memory"""
        try:
            self.logger.info("Fetching local IP address...")
            # Create a socket connection to an external address (doesn't actually send data)
            # This forces the OS to choose the correct network interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Google DNS
            self.local_ip = s.getsockname()[0]
            s.close()
            self.logger.info(f"Local IP fetched successfully: {self.local_ip}")
        except Exception as e:
            self.logger.warning(f"Could not fetch local IP: {e}")
            self.local_ip = '127.0.0.1'

    def fetch_public_ip(self):
        """Fetch public IP once at startup and cache in memory until backend restarts"""
        try:
            self.logger.info("Fetching public IP address...")
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            response.raise_for_status()
            self.public_ip = response.json().get('ip', 'N/A')
            self.logger.info(f"Public IP fetched successfully: {self.public_ip}")
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Could not fetch public IP (network error): {e}")
            self.public_ip = 'N/A'
        except Exception as e:
            self.logger.warning(f"Could not fetch public IP: {e}")
            self.public_ip = 'N/A'

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
                    'threads': process.num_threads(),
                    'public_ip': self.public_ip,  # Cached public IP
                    'local_ip': self.local_ip  # Cached local IP
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

        # Fetch network IPs once at startup (cached in memory for this process lifecycle)
        self.fetch_local_ip()
        self.fetch_public_ip()

        self.app = self.create_service_app()
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        try:
            host = os.getenv('HOST', '0.0.0.0')
            port = int(os.getenv('PORT', 57575))

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
    """Main entry point with Windows terminal persistence"""
    import platform
    
    try:
        service = ZKTecoService()
        service.start()
    except KeyboardInterrupt:
        print("\n⏹️  Service stopped by user")
    except Exception as e:
        print(f"\n❌ Service crashed: {e}")
        
        # Print full traceback for debugging
        import traceback
        print("\n" + "="*50)
        print("ERROR DETAILS:")
        print("="*50)
        traceback.print_exc()
        print("="*50)
        
        # Try to log the error if possible
        try:
            from app.shared.logger import get_user_log_dir
            log_dir = get_user_log_dir()
            error_log_path = os.path.join(log_dir, 'startup_error.log')
            with open(error_log_path, 'a') as f:
                f.write(f"\n--- Startup Error at {time.ctime()} ---\n")
                f.write(f"Error: {e}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
                f.write("--- End Error ---\n\n")
            print(f"\n📋 Error logged to: {error_log_path}")
        except Exception:
            print("📋 Could not save error log")
        
        # Keep terminal open on Windows when running as executable
        if platform.system() == "Windows" and getattr(sys, 'frozen', False):
            input("\nPress Enter to close...")
        
        # Exit with error code
        sys.exit(1)


if __name__ == "__main__":
    main()

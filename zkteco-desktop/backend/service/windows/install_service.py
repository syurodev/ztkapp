"""
Windows Service installer for ZKTeco API
"""

import os
import sys
import time
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import subprocess
from pathlib import Path


class ZKTecoWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ZKTecoService"
    _svc_display_name_ = "ZKTeco RESTful API Service"
    _svc_description_ = "ZKTeco device management REST API service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        if self.process:
            self.process.terminate()

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        # Get the service directory
        service_dir = Path(__file__).parent.parent
        python_exe = service_dir / "venv" / "Scripts" / "python.exe"
        service_script = service_dir / "service_app.py"
        
        # Start the service process
        try:
            self.process = subprocess.Popen([
                str(python_exe),
                str(service_script)
            ], cwd=str(service_dir))
            
            # Wait for stop signal
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Service error: {e}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ZKTecoWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ZKTecoWindowsService)
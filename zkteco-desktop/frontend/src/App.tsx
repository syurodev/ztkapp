import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { Toaster } from "sonner";
import "./App.css";
import { AppInitializer } from "./components/features/AppInitializer";
import { Attendance } from "./components/features/Attendance";
import { DeviceManagement } from "./components/features/DeviceManagement";
import { LiveAttendance } from "./components/features/LiveAttendance";
import { ServiceStatus } from "./components/features/ServiceStatus";
import { Settings } from "./components/features/Settings";
import { UserManagement } from "./components/features/UserManagement";
import { AppLayout } from "./components/layout/AppLayout";
import { DeviceProvider } from "./contexts/DeviceContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { TrayProvider } from "./contexts/TrayContext";

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <TrayProvider>
        <DeviceProvider>
          <AppInitializer>
            <Router>
              <AppLayout>
                <Routes>
                  <Route path="/" element={<ServiceStatus />} />
                  <Route path="/devices" element={<DeviceManagement />} />
                  <Route path="/users" element={<UserManagement />} />
                  <Route path="/attendance" element={<Attendance />} />
                  <Route path="/live-attendance" element={<LiveAttendance />} />
                  <Route
                    path="/fingerprints"
                    element={
                      <div className="p-8 text-center text-muted-foreground">
                        Fingerprint Management - Coming Soon
                      </div>
                    }
                  />
                  <Route path="/settings" element={<Settings />} />
                  <Route
                    path="/logs"
                    element={
                      <div className="p-8 text-center text-muted-foreground">
                        Logs Viewer - Coming Soon
                      </div>
                    }
                  />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppLayout>
              <Toaster position="top-right" />
            </Router>
          </AppInitializer>
        </DeviceProvider>
      </TrayProvider>
    </ThemeProvider>
  );
}

export default App;

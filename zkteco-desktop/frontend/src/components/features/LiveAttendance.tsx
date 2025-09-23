import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDevice } from "@/contexts/DeviceContext";
import { liveAPI, LiveAttendanceRecord } from "@/lib/api";
import { ATTENDANCE_METHOD_MAP, PUNCH_ACTION_MAP } from "@/types/constant";
import { Activity, Monitor, Wifi, WifiOff, Play, Square, Users, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

const MAX_RECORDS = 50;

export function LiveAttendance() {
  const {
    devices,
    activeDevice,
    captureStatus,
    isCaptureLoading,
    startAllCapture,
    stopAllCapture,
    startDeviceCapture,
    stopDeviceCapture,
    isDeviceCapturing,
    getDeviceCaptureStatus
  } = useDevice();

  const [liveAttendance, setLiveAttendance] = useState<LiveAttendanceRecord[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedDeviceFilter, setSelectedDeviceFilter] = useState<string>("all");

  useEffect(() => {
    if (devices.length === 0) {
      setLiveAttendance([]);
      setIsConnected(false);
      return;
    }

    const handleMessage = (newRecord: LiveAttendanceRecord) => {
      setLiveAttendance((prev) => [newRecord, ...prev].slice(0, MAX_RECORDS));
    };

    const handleError = () => {
      setIsConnected(false);
    };

    const handleOpen = () => {
      setIsConnected(true);
    };

    // Connect with device filter
    const cleanup = liveAPI.connect(handleMessage, handleError, handleOpen, selectedDeviceFilter);

    return () => {
      cleanup();
    };
  }, [devices, selectedDeviceFilter]);

  // Helper functions for device management
  const handleStartAllCapture = async () => {
    try {
      await startAllCapture();
    } catch (error) {
      console.error("Failed to start all capture:", error);
    }
  };

  const handleStopAllCapture = async () => {
    try {
      await stopAllCapture();
    } catch (error) {
      console.error("Failed to stop all capture:", error);
    }
  };

  const handleToggleDeviceCapture = async (deviceId: string) => {
    try {
      const isCapturing = isDeviceCapturing(deviceId);
      if (isCapturing) {
        await stopDeviceCapture(deviceId);
      } else {
        await startDeviceCapture(deviceId);
      }
    } catch (error) {
      console.error(`Failed to toggle capture for device ${deviceId}:`, error);
    }
  };

  // Get filtered attendance records
  const filteredAttendance = selectedDeviceFilter === "all"
    ? liveAttendance
    : liveAttendance.filter(record => record.device_id === selectedDeviceFilter);

  // Get device name helper
  const getDeviceName = (deviceId: string) => {
    const device = devices.find(d => d.id === deviceId);
    return device?.name || deviceId;
  };

  const ConnectionIcon = isConnected ? Wifi : WifiOff;
  const connectionColor = isConnected ? "text-green-500" : "text-red-500";

  return (
    <div className="space-y-6">
      {/* No Devices Alert */}
      {devices.length === 0 && (
        <Alert>
          <Monitor className="h-4 w-4" />
          <AlertDescription>
            No devices configured. Go to Device Management to add devices for live attendance monitoring.
          </AlertDescription>
        </Alert>
      )}

      {/* Multi-Device Capture Control Panel */}
      {devices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Live Capture Control
              <Badge variant="secondary" className="ml-auto">
                {captureStatus?.overall_status.active_captures || 0} / {devices.length} Active
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Global Controls */}
              <div className="flex gap-2">
                <Button
                  onClick={handleStartAllCapture}
                  disabled={isCaptureLoading}
                  size="sm"
                  className="flex items-center gap-2"
                >
                  <Play className="h-4 w-4" />
                  Start All Devices
                </Button>
                <Button
                  onClick={handleStopAllCapture}
                  disabled={isCaptureLoading}
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-2"
                >
                  <Square className="h-4 w-4" />
                  Stop All Devices
                </Button>
              </div>

              {/* Individual Device Controls */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {devices.map((device) => {
                  const isCapturing = isDeviceCapturing(device.id);
                  const deviceStatus = getDeviceCaptureStatus(device.id);
                  const isHealthy = deviceStatus?.is_healthy !== false;

                  return (
                    <div key={device.id} className="border rounded-lg p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{device.name}</span>
                        <div className="flex items-center gap-1">
                          <Badge
                            variant={isCapturing ? "default" : "secondary"}
                            className="text-xs"
                          >
                            {isCapturing ? "Active" : "Inactive"}
                          </Badge>
                          {!isHealthy && (
                            <Badge variant="destructive" className="text-xs">
                              Unhealthy
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {device.ip}:{device.port}
                      </div>
                      <Button
                        onClick={() => handleToggleDeviceCapture(device.id)}
                        disabled={isCaptureLoading}
                        size="sm"
                        variant={isCapturing ? "outline" : "default"}
                        className="w-full flex items-center gap-1"
                      >
                        {isCapturing ? (
                          <>
                            <Square className="h-3 w-3" />
                            Stop
                          </>
                        ) : (
                          <>
                            <Play className="h-3 w-3" />
                            Start
                          </>
                        )}
                      </Button>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Attendance Feed */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-6 w-6" />
            Live Attendance Feed
            {devices.length > 0 && (
              <span
                title={isConnected ? "Connected" : "Disconnected"}
                className="ml-auto"
              >
                <ConnectionIcon className={`h-5 w-5 ${connectionColor}`} />
              </span>
            )}
          </CardTitle>
          {devices.length > 1 && (
            <div className="flex items-center gap-2 pt-2">
              <span className="text-sm text-muted-foreground">Filter by device:</span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    {selectedDeviceFilter === "all" ? "All Devices" : getDeviceName(selectedDeviceFilter)}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={() => setSelectedDeviceFilter("all")}>
                    All Devices
                  </DropdownMenuItem>
                  {devices.map((device) => (
                    <DropdownMenuItem
                      key={device.id}
                      onClick={() => setSelectedDeviceFilter(device.id)}
                    >
                      {device.name}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {devices.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Monitor className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No devices configured</p>
                <p className="text-sm text-muted-foreground">
                  Add devices to view live attendance feed
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Device</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAttendance.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-48 text-center text-muted-foreground"
                    >
                      {isConnected
                        ? "Waiting for attendance events..."
                        : "Connecting to live feed..."}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAttendance.map((record, index) => (
                    <TableRow
                      key={`${record.user_id}-${record.timestamp}-${index}`}
                    >
                      <TableCell className="font-medium">
                        {record.user_id}
                      </TableCell>
                      <TableCell>{record.name}</TableCell>
                      <TableCell>{record.timestamp}</TableCell>
                      <TableCell>
                        {ATTENDANCE_METHOD_MAP[record.method] || "Unknown"}
                      </TableCell>
                      <TableCell>
                        {PUNCH_ACTION_MAP[record.action] || "Unknown"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {getDeviceName(record.device_id)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

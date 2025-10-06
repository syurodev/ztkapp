import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDevice } from "@/contexts/DeviceContext";
import { attendanceAPI, liveAPI, LiveAttendanceRecord } from "@/lib/api";
import { buildAvatarUrl, cn, getResourceDomain } from "@/lib/utils";
import { ATTENDANCE_METHOD_MAP, PUNCH_ACTION_MAP } from "@/types/constant";
import { format } from "date-fns";
import {
  Activity,
  ArrowLeftFromLine,
  ArrowRightToLine,
  Fingerprint,
  IdCard,
  Monitor,
  Play,
  Settings,
  Square,
  User,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";

const MAX_RECORDS = 50;

export function LiveAttendance() {
  const {
    devices,
    captureStatus,
    isCaptureLoading,
    startAllCapture,
    stopAllCapture,
    startDeviceCapture,
    stopDeviceCapture,
    isDeviceCapturing,
    getDeviceCaptureStatus,
  } = useDevice();

  const [liveAttendance, setLiveAttendance] = useState<LiveAttendanceRecord[]>(
    []
  );
  const [isConnected, setIsConnected] = useState(false);
  const [selectedDeviceFilter, setSelectedDeviceFilter] =
    useState<string>("all");
  const [actionFilter, setActionFilter] = useState<"all" | 0 | 1>("all");
  const [resourceDomain, setResourceDomain] = useState<string>("");
  const [_, setIsInitialLoading] = useState(false);

  // Load resource domain on mount
  useEffect(() => {
    getResourceDomain().then(setResourceDomain);
  }, []);

  useEffect(() => {
    const mergeRecords = (
      incoming: LiveAttendanceRecord[],
      existing: LiveAttendanceRecord[]
    ) => {
      const combined = [...incoming, ...existing];
      const seen = new Set<string>();
      const unique: LiveAttendanceRecord[] = [];

      for (const record of combined) {
        const key = `${record.user_id}-${record.device_id}-${record.timestamp}-${record.action}`;
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(record);
        }
      }

      return unique
        .sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        )
        .slice(0, MAX_RECORDS);
    };

    const mapToLiveRecord = (record: any): LiveAttendanceRecord => ({
      id: record.id,
      user_id: record.user_id,
      name: record.name || "Unknown User",
      avatar_url: record.avatar_url || null,
      timestamp: record.timestamp,
      method: record.method,
      action: record.action,
      device_id: record.device_id,
      is_synced: record.is_synced ?? false,
    });

    if (devices.length === 0) {
      setLiveAttendance([]);
      setIsConnected(false);
      return;
    }

    let isMounted = true;

    const loadInitialAttendance = async () => {
      setIsInitialLoading(true);
      try {
        const dateStr = format(new Date(), "yyyy-MM-dd");
        const response = await attendanceAPI.getAttendance({
          limit: MAX_RECORDS,
          device_id:
            selectedDeviceFilter === "all" ? undefined : selectedDeviceFilter,
          date: dateStr,
        });

        const initialRecords: LiveAttendanceRecord[] = Array.isArray(
          response?.data
        )
          ? response.data
              .map(mapToLiveRecord)
              .filter((record: any) => !!record.timestamp)
          : [];

        if (!isMounted) return;

        if (initialRecords.length > 0) {
          setLiveAttendance((prev) => mergeRecords(initialRecords, prev));
        }
      } catch (error) {
        console.error("Failed to load initial live attendance records:", error);
      } finally {
        if (isMounted) {
          setIsInitialLoading(false);
        }
      }
    };

    const handleMessage = (newRecord: LiveAttendanceRecord) => {
      setLiveAttendance((prev) => mergeRecords([newRecord], prev));
    };

    const handleError = () => {
      setIsConnected(false);
    };

    const handleOpen = () => {
      setIsConnected(true);
    };

    loadInitialAttendance();

    // Connect with device filter
    const cleanup = liveAPI.connect(
      handleMessage,
      handleError,
      handleOpen,
      selectedDeviceFilter
    );

    return () => {
      isMounted = false;
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

  // Filter attendance: only show first checkin and last checkout per user per day
  const filterFirstLastAttendance = (records: LiveAttendanceRecord[]) => {
    // Group by user_id and date
    const grouped = new Map<string, LiveAttendanceRecord[]>();

    records.forEach((record) => {
      const date = record.timestamp.split(" ")[0]; // Get date part (YYYY-MM-DD)
      const key = `${record.user_id}-${date}`;

      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)!.push(record);
    });

    // For each group, keep only first checkin (action=0) and last checkout (action=1)
    const filtered: LiveAttendanceRecord[] = [];

    grouped.forEach((userDayRecords) => {
      // Sort by timestamp ascending
      const sorted = [...userDayRecords].sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      // Find first checkin (action = 0)
      const firstCheckin = sorted.find((r) => r.action === 0);
      if (firstCheckin) {
        filtered.push(firstCheckin);
      }

      // Find last checkout (action = 1)
      const checkouts = sorted.filter((r) => r.action === 1);
      const lastCheckout =
        checkouts.length > 0 ? checkouts[checkouts.length - 1] : null;
      if (lastCheckout) {
        filtered.push(lastCheckout);
      }
    });

    // Sort final result by timestamp descending (newest first)
    return filtered.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  };

  // Get filtered attendance records
  const deviceFiltered =
    selectedDeviceFilter === "all"
      ? liveAttendance
      : liveAttendance.filter(
          (record) => record.device_id === selectedDeviceFilter
        );

  // Apply first/last filter
  let filteredAttendance = filterFirstLastAttendance(deviceFiltered);

  // Apply action filter
  if (actionFilter !== "all") {
    filteredAttendance = filteredAttendance.filter(
      (record) => record.action === actionFilter
    );
  }

  // Get device name helper
  const getDeviceName = (deviceId: string) => {
    const device = devices.find((d) => d.id === deviceId);
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
            No devices configured. Go to Device Management to add devices for
            live attendance monitoring.
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
                {captureStatus?.overall_status.active_captures || 0} /{" "}
                {devices.length} Active
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
                    <div
                      key={device.id}
                      className="border rounded-lg p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">
                          {device.name}
                        </span>
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
          <div className="flex items-center gap-4 pt-2 flex-wrap">
            {/* Action Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Filter:</span>
              <div className="flex gap-1">
                <Button
                  variant={actionFilter === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter("all")}
                >
                  Tất cả
                </Button>
                <Button
                  variant={actionFilter === 0 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter(0)}
                >
                  Check-in
                </Button>
                <Button
                  variant={actionFilter === 1 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter(1)}
                >
                  Check-out
                </Button>
              </div>
            </div>

            {/* Device Filter */}
            {devices.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Device:</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      {selectedDeviceFilter === "all"
                        ? "All Devices"
                        : getDeviceName(selectedDeviceFilter)}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem
                      onClick={() => setSelectedDeviceFilter("all")}
                    >
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
          </div>
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
          ) : filteredAttendance.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4 animate-pulse" />
                <p className="text-muted-foreground">
                  {isConnected
                    ? "Waiting for attendance events..."
                    : "Connecting to live feed..."}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-h-[600px] overflow-y-auto p-2 ">
              {filteredAttendance.map((record, index) => {
                const isLatest = index === 0;
                const actionIcon =
                  record.action === 0 ? (
                    <ArrowRightToLine className="h-5 w-5" />
                  ) : (
                    <ArrowLeftFromLine className="h-5 w-5" />
                  );
                const actionColor =
                  record.action === 0
                    ? "border-teal-500 dark:border-teal-500"
                    : "border-sky-500 dark:border-sky-500";
                const methodIcon =
                  record.method === 1 ? (
                    <Fingerprint className="h-3 w-3" />
                  ) : record.method === 4 ? (
                    <IdCard className="h-3 w-3" />
                  ) : null;

                if (isLatest) {
                  // Latest record - Full width highlight card
                  return (
                    <Card
                      key={`${record.user_id}-${record.timestamp}-${index}`}
                    >
                      <CardContent className="flex items-center gap-6 p-6 rounded-xl transition-all animate-in slide-in-from-top-2">
                        {/* Avatar */}
                        <Avatar
                          className={cn(
                            "size-32 flex-shrink-0 border-2",
                            actionColor
                          )}
                        >
                          <AvatarImage
                            src={buildAvatarUrl(
                              record.avatar_url,
                              resourceDomain
                            )}
                            alt={record.name}
                          />
                          <AvatarFallback className="text-3xl font-bold">
                            {record.name ? (
                              record.name
                                .split(" ")
                                .map((n) => n[0])
                                .join("")
                                .toUpperCase()
                                .slice(0, 2)
                            ) : (
                              <User className="h-16 w-16" />
                            )}
                          </AvatarFallback>
                        </Avatar>

                        {/* Info */}
                        <div className="flex-1 min-w-0 space-y-3">
                          <div className="font-bold text-3xl truncate flex items-center gap-4">
                            {record.name}
                            <Badge
                              variant={"outline"}
                              className={`gap-2 ${actionColor} `}
                            >
                              {actionIcon}
                              {PUNCH_ACTION_MAP[record.action] || "Unknown"}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 flex-wrap">
                            <div className="font-mono font-bold text-2xl">
                              {record.timestamp.split(" ")[1]}
                            </div>
                            {methodIcon && (
                              <Badge
                                variant="outline"
                                className="gap-1 text-sm px-3 py-1"
                              >
                                {methodIcon}
                                {ATTENDANCE_METHOD_MAP[record.method] ||
                                  "Unknown"}
                              </Badge>
                            )}
                            {devices.length > 1 && (
                              <Badge
                                variant="secondary"
                                className="text-sm px-3 py-1"
                              >
                                {getDeviceName(record.device_id)}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                }

                // Other records - Grid layout
                return null;
              })}

              {/* Grid for other records */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ">
                {filteredAttendance.slice(1).map((record, index) => {
                  const actualIndex = index + 1;
                  const actionIcon =
                    record.action === 0 ? (
                      <ArrowRightToLine className="h-4 w-4" />
                    ) : (
                      <ArrowLeftFromLine className="h-4 w-4" />
                    );
                  const actionColor =
                    record.action === 0
                      ? "border-teal-500 dark:border-teal-500"
                      : "border-sky-500 dark:border-sky-500";
                  const methodIcon =
                    record.method === 1 ? (
                      <Fingerprint className="h-3 w-3" />
                    ) : record.method === 4 ? (
                      <IdCard className="h-3 w-3" />
                    ) : null;

                  return (
                    <Card
                      key={`${record.user_id}-${record.timestamp}-${actualIndex}`}
                    >
                      <CardContent className="flex items-center gap-4">
                        {/* Avatar */}
                        <Avatar
                          className={cn(
                            "h-16 w-16 flex-shrink-0 border-2",
                            actionColor
                          )}
                        >
                          <AvatarImage
                            src={buildAvatarUrl(
                              record.avatar_url,
                              resourceDomain
                            )}
                            alt={record.name}
                          />
                          <AvatarFallback className="text-sm">
                            {record.name ? (
                              record.name
                                .split(" ")
                                .map((n) => n[0])
                                .join("")
                                .toUpperCase()
                                .slice(0, 2)
                            ) : (
                              <User className="h-8 w-8" />
                            )}
                          </AvatarFallback>
                        </Avatar>

                        {/* Info */}
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="font-semibold truncate flex items-center gap-4">
                            {record.name}
                            <Badge
                              variant={"outline"}
                              className={`gap-1 ${actionColor}`}
                            >
                              {actionIcon}
                              {PUNCH_ACTION_MAP[record.action] || "Unknown"}
                            </Badge>
                          </div>

                          <div className="font-mono text-xs text-muted-foreground">
                            {record.timestamp.split(" ")[1]}
                          </div>
                          <div className="flex items-center gap-1 flex-wrap">
                            {methodIcon && (
                              <Badge
                                variant="outline"
                                className="gap-1 text-xs"
                              >
                                {methodIcon}
                                {ATTENDANCE_METHOD_MAP[record.method] ||
                                  "Unknown"}
                              </Badge>
                            )}
                            {devices.length > 1 && (
                              <Badge variant="secondary" className="text-xs">
                                {getDeviceName(record.device_id)}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

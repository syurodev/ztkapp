import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  User,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";

const MAX_RECORDS = 50;

export function LiveAttendance() {
  const { devices, activeDevice, activeDeviceId } = useDevice();

  const [liveAttendance, setLiveAttendance] = useState<LiveAttendanceRecord[]>(
    [],
  );
  const [isConnected, setIsConnected] = useState(false);
  const [showAllDevices, setShowAllDevices] = useState(false);
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
      existing: LiveAttendanceRecord[],
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
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        )
        .slice(0, MAX_RECORDS);
    };

    const mapToLiveRecord = (record: any): LiveAttendanceRecord => ({
      id: record.id,
      user_id: record.user_id,
      name: record.name || "Người dùng không xác định",
      avatar_url: record.avatar_url || null,
      timestamp: record.timestamp,
      method: record.method,
      action: record.action,
      device_id: record.device_id,
      is_synced: record.is_synced ?? false,
      // New employee fields
      full_name: record.full_name,
      employee_code: record.employee_code,
      position: record.position,
      department: record.department,
      notes: record.notes,
      employee_object: record.employee_object,
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
          device_id: showAllDevices ? undefined : (activeDeviceId as string),
          date: dateStr,
        });

        const initialRecords: LiveAttendanceRecord[] = Array.isArray(
          response?.data,
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

    // Connect to all devices - backend always listens to all
    const cleanup = liveAPI.connect(handleMessage, handleError, handleOpen);

    return () => {
      isMounted = false;
      cleanup();
    };
  }, [devices, activeDeviceId, showAllDevices]);

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
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
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
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
  };

  // Get filtered attendance records
  const deviceFiltered = showAllDevices
    ? liveAttendance
    : liveAttendance.filter((record) => record.device_id === activeDeviceId);

  // Apply first/last filter
  let filteredAttendance = filterFirstLastAttendance(deviceFiltered);

  // Apply action filter
  if (actionFilter !== "all") {
    filteredAttendance = filteredAttendance.filter(
      (record) => record.action === actionFilter,
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
            Chưa cấu hình thiết bị. Vào Quản lý thiết bị để thêm thiết bị phục
            vụ theo dõi realtime.
          </AlertDescription>
        </Alert>
      )}

      {/* Live Attendance Feed - Optimized Header */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            {/* Title */}
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Chấm công Realtime
              {devices.length > 0 && (
                <ConnectionIcon className={`h-4 w-4 ${connectionColor}`} />
              )}
            </CardTitle>

            {/* Compact Filters */}
            <div className="flex items-center gap-2">
              {/* Action Filter - Compact */}
              <div className="flex gap-1">
                <Button
                  variant={actionFilter === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter("all")}
                  className="h-8 px-3 text-xs"
                >
                  Tất cả
                </Button>
                <Button
                  variant={actionFilter === 0 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter(0)}
                  className="h-8 px-3 text-xs"
                >
                  Vào ca
                </Button>
                <Button
                  variant={actionFilter === 1 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActionFilter(1)}
                  className="h-8 px-3 text-xs"
                >
                  Ra ca
                </Button>
              </div>

              {/* Device Filter - Toggle between Active Device / All Devices */}
              {devices.length > 1 && activeDevice && (
                <Button
                  variant={showAllDevices ? "outline" : "default"}
                  size="sm"
                  onClick={() => setShowAllDevices(!showAllDevices)}
                  className="h-8 px-3 text-xs flex items-center gap-1"
                >
                  <Monitor className="h-3 w-3" />
                  {showAllDevices ? "Tất cả thiết bị" : activeDevice.name}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {devices.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Monitor className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">Chưa có thiết bị nào</p>
                <p className="text-sm text-muted-foreground">
                  Thêm thiết bị để xem dữ liệu chấm công realtime
                </p>
              </div>
            </div>
          ) : filteredAttendance.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4 animate-pulse" />
                <p className="text-muted-foreground">
                  {isConnected
                    ? "Đang chờ dữ liệu chấm công..."
                    : "Đang kết nối luồng realtime..."}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Latest Attendance - Large Display with Avatar (2/3 ratio rectangle) */}
              {filteredAttendance.length > 0 &&
                (() => {
                  const latestRecord = filteredAttendance[0];
                  const displayName =
                    latestRecord.full_name || latestRecord.name;
                  const actionIcon =
                    latestRecord.action === 0 ? (
                      <ArrowRightToLine className="h-6 w-6" />
                    ) : (
                      <ArrowLeftFromLine className="h-6 w-6" />
                    );
                  const actionColor =
                    latestRecord.action === 0
                      ? "border-teal-500 dark:border-teal-500 bg-teal-50 dark:bg-teal-950"
                      : "border-sky-500 dark:border-sky-500 bg-sky-50 dark:bg-sky-950";
                  const methodIcon =
                    latestRecord.method === 1 ? (
                      <Fingerprint className="h-4 w-4" />
                    ) : latestRecord.method === 4 ? (
                      <IdCard className="h-4 w-4" />
                    ) : null;

                  return (
                    <Card className="border-2 shadow-lg">
                      <CardContent className="p-6">
                        <div className="flex gap-6">
                          {/* Avatar - Rectangle with 2/3 ratio (width:height) */}
                          <div className="flex-shrink-0 w-64">
                            <Avatar
                              className={cn(
                                "w-64 h-96 rounded-2xl border-4 shadow-xl",
                                actionColor,
                              )}
                            >
                              <AvatarImage
                                src={buildAvatarUrl(
                                  latestRecord.avatar_url,
                                  resourceDomain,
                                )}
                                alt={displayName}
                                className="object-cover"
                              />
                              <AvatarFallback className="text-6xl font-bold rounded-lg">
                                {displayName ? (
                                  displayName
                                    .split(" ")
                                    .map((n) => n[0])
                                    .join("")
                                    .toUpperCase()
                                    .slice(0, 2)
                                ) : (
                                  <User className="h-32 w-32" />
                                )}
                              </AvatarFallback>
                            </Avatar>
                          </div>

                          {/* Information Panel */}
                          <div className="flex-1 space-y-4">
                            {/* Full name from external system */}
                            <div className="space-y-1">
                              <div className="text-sm text-muted-foreground font-medium">
                                Tên hệ thống
                              </div>
                              <div className="text-4xl font-semibold">
                                {latestRecord.full_name || "-"}
                              </div>
                            </div>

                            {/* Time */}
                            <div className="space-y-1">
                              <div className="text-sm text-muted-foreground font-medium">
                                Thời gian
                              </div>
                              <div className="font-mono font-bold text-3xl text-primary">
                                {latestRecord.timestamp.split(" ")[1]}
                              </div>
                            </div>

                            {/* Employee Information Grid */}
                            <div className="grid grid-cols-2 gap-4 pt-2">
                              {/* User ID on device */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  ID người dùng trên máy
                                </div>
                                <div className="text-lg font-semibold font-mono">
                                  {latestRecord.user_id}
                                </div>
                              </div>

                              {/* Employee Code */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  Mã nhân viên
                                </div>
                                <div className="text-lg font-semibold">
                                  {latestRecord.employee_code || "-"}
                                </div>
                              </div>

                              {/* Name on device */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  Tên trên máy
                                </div>
                                <div className="text-lg font-semibold">
                                  {latestRecord.name}
                                </div>
                              </div>

                              {/* Position */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  Vị trí
                                </div>
                                <div className="text-lg font-semibold">
                                  {latestRecord.position || "-"}
                                </div>
                              </div>

                              {/* Department */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  Phòng ban
                                </div>
                                <div className="text-lg font-semibold">
                                  {latestRecord.department || "-"}
                                </div>
                              </div>

                              {/* Employee Object */}
                              <div className="space-y-1">
                                <div className="text-sm text-muted-foreground font-medium">
                                  Đối tượng
                                </div>
                                <div className="text-lg font-semibold">
                                  {latestRecord.employee_object || "-"}
                                </div>
                              </div>
                            </div>

                            {/* Method and Device badges */}
                            <div className="flex items-center gap-3 flex-wrap pt-2">
                              {/* Action Badge */}
                              <Badge
                                variant="outline"
                                className={`gap-2 text-sm px-3 py-1.5 ${actionColor}`}
                              >
                                {actionIcon}
                                {PUNCH_ACTION_MAP[latestRecord.action] ||
                                  "Không xác định"}
                              </Badge>
                              {methodIcon && (
                                <Badge
                                  variant="outline"
                                  className="gap-2 text-sm px-3 py-1.5"
                                >
                                  {methodIcon}
                                  {ATTENDANCE_METHOD_MAP[latestRecord.method] ||
                                    "Không xác định"}
                                </Badge>
                              )}
                              {devices.length > 1 && (
                                <Badge
                                  variant="secondary"
                                  className="text-sm px-3 py-1.5"
                                >
                                  <Monitor className="h-3 w-3 mr-1" />
                                  {getDeviceName(latestRecord.device_id)}
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })()}

              {/* History Table - Previous Actions */}
              {filteredAttendance.length > 1 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Lịch sử chấm công</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-32">Thời gian</TableHead>
                          <TableHead>Tên</TableHead>
                          <TableHead className="w-32">Mã NV</TableHead>
                          <TableHead className="w-32">ID máy</TableHead>
                          <TableHead className="w-32">Phòng ban</TableHead>
                          <TableHead className="w-24">Vị trí</TableHead>
                          <TableHead className="w-28">Hành động</TableHead>
                          <TableHead className="w-28">Phương thức</TableHead>
                          {devices.length > 1 && (
                            <TableHead className="w-32">Thiết bị</TableHead>
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredAttendance.slice(1).map((record, index) => {
                          const displayName = record.full_name || record.name;
                          const actionIcon =
                            record.action === 0 ? (
                              <ArrowRightToLine className="h-4 w-4" />
                            ) : (
                              <ArrowLeftFromLine className="h-4 w-4" />
                            );
                          const actionColor =
                            record.action === 0
                              ? "text-teal-600 dark:text-teal-400"
                              : "text-sky-600 dark:text-sky-400";
                          const methodIcon =
                            record.method === 1 ? (
                              <Fingerprint className="h-4 w-4" />
                            ) : record.method === 4 ? (
                              <IdCard className="h-4 w-4" />
                            ) : null;

                          return (
                            <TableRow
                              key={`${record.user_id}-${record.timestamp}-${index}`}
                            >
                              <TableCell className="font-mono text-sm">
                                {record.timestamp.split(" ")[1]}
                              </TableCell>
                              <TableCell className="font-medium flex gap-2 items-center">
                                <Avatar className={cn(actionColor)}>
                                  <AvatarImage
                                    src={buildAvatarUrl(
                                      record.avatar_url,
                                      resourceDomain,
                                    )}
                                    alt={displayName}
                                    className="object-cover"
                                  />
                                  <AvatarFallback>
                                    {displayName ? (
                                      displayName
                                        .split(" ")
                                        .map((n) => n[0])
                                        .join("")
                                        .toUpperCase()
                                        .slice(0, 2)
                                    ) : (
                                      <User className="h-32 w-32" />
                                    )}
                                  </AvatarFallback>
                                </Avatar>
                                {displayName}
                              </TableCell>
                              <TableCell className="font-mono">
                                {record.employee_code || "-"}
                              </TableCell>
                              <TableCell className="font-mono">
                                {record.user_id}
                              </TableCell>
                              <TableCell>{record.department || "-"}</TableCell>
                              <TableCell>{record.position || "-"}</TableCell>
                              <TableCell>
                                <div
                                  className={`flex items-center gap-1 ${actionColor}`}
                                >
                                  {actionIcon}
                                  <span className="text-sm font-medium">
                                    {PUNCH_ACTION_MAP[record.action] || "N/A"}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-1">
                                  {methodIcon}
                                  <span className="text-sm">
                                    {ATTENDANCE_METHOD_MAP[record.method] ||
                                      "N/A"}
                                  </span>
                                </div>
                              </TableCell>
                              {devices.length > 1 && (
                                <TableCell>
                                  <Badge
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    {getDeviceName(record.device_id)}
                                  </Badge>
                                </TableCell>
                              )}
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

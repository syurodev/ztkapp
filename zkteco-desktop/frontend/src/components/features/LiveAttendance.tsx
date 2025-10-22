import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
import {
  buildAvatarUrl,
  cn,
  getResourceDomain,
  RESOURCE_DOMAIN_EVENT,
} from "@/lib/utils";
import { format, isValid, parseISO } from "date-fns";
import { Activity, Monitor, User, Wifi, WifiOff } from "lucide-react";
import { ReactNode, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const MAX_RECORDS = 50;
const MotionTableRow = motion(TableRow);

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
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  const getShiftLabel = (action: number) =>
    action === 0 ? "Thời gian vào ca" : "Thời gian ra ca";

  const extractTimestampParts = (timestamp?: string) => {
    if (!timestamp) {
      return { time: "-", date: "-" };
    }
    const [datePart, timePart] = timestamp.split(" ");
    let formattedDate = datePart || "-";
    if (datePart) {
      try {
        const parsed = parseISO(datePart);
        if (isValid(parsed)) {
          formattedDate = format(parsed, "dd/MM/yyyy");
        }
      } catch (error) {
        // Ignore parse errors and retain original value
      }
    }
    return {
      time: timePart || timestamp,
      date: formattedDate,
    };
  };

  const formatGender = (value?: string | null) => {
    if (!value) return "-";
    const normalized = value.toString().trim().toLowerCase();
    if (["male", "nam", "m"].includes(normalized)) {
      return "Nam";
    }
    if (["female", "nu", "nữ", "f"].includes(normalized)) {
      return "Nữ";
    }
    if (
      ["other", "khac", "khác", "unspecified", "unknown"].includes(normalized)
    ) {
      return "Khác";
    }
    return value;
  };

  const formatHireDate = (value?: string | null) => {
    if (!value) return "-";
    try {
      const parsed = parseISO(value);
      if (isValid(parsed)) {
        return format(parsed, "dd/MM/yyyy");
      }
      const fallback = new Date(value);
      if (!Number.isNaN(fallback.getTime())) {
        return format(fallback, "dd/MM/yyyy");
      }
    } catch (error) {
      // Ignore parse errors and fall back to raw value
    }
    return value;
  };

  const DetailItem = ({
    label,
    value,
    highlight = false,
  }: {
    label: string;
    value: ReactNode;
    highlight?: boolean;
  }) => (
    <div className="space-y-1">
      <div className="text-sm text-muted-foreground font-medium">{label}</div>
      <div
        className={
          highlight ? "text-4xl font-semibold" : "text-lg font-semibold"
        }
      >
        {value}
      </div>
    </div>
  );

  // Load resource domain on mount and subscribe to updates
  useEffect(() => {
    const refreshResourceDomain = () => {
      void getResourceDomain().then(setResourceDomain);
    };

    refreshResourceDomain();

    if (typeof window === "undefined") {
      return;
    }

    const handleResourceDomainChange = (event: Event) => {
      const detail = (event as CustomEvent<{ resourceDomain?: string }>).detail;

      if (
        detail &&
        typeof detail.resourceDomain === "string" &&
        detail.resourceDomain !== ""
      ) {
        setResourceDomain(detail.resourceDomain);
      } else {
        refreshResourceDomain();
      }
    };

    window.addEventListener(RESOURCE_DOMAIN_EVENT, handleResourceDomainChange);

    return () => {
      window.removeEventListener(
        RESOURCE_DOMAIN_EVENT,
        handleResourceDomainChange,
      );
    };
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
      gender: record.gender,
      hire_date: record.hire_date,
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

    let retryDelay = 2000;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (!isMounted) {
        return;
      }
      clearReconnectTimer();
      reconnectTimerRef.current = setTimeout(() => {
        if (!isMounted) {
          return;
        }
        startStreaming();
      }, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30000);
    };

    const handleError = () => {
      if (!isMounted) {
        return;
      }
      setIsConnected(false);
      cleanupRef.current?.();
      cleanupRef.current = null;
      scheduleReconnect();
    };

    const handleOpen = () => {
      setIsConnected(true);
      retryDelay = 2000;
      clearReconnectTimer();
    };

    const startStreaming = () => {
      cleanupRef.current?.();
      cleanupRef.current = liveAPI.connect(
        handleMessage,
        handleError,
        handleOpen,
      );
    };

    loadInitialAttendance();
    startStreaming();

    return () => {
      isMounted = false;
      clearReconnectTimer();
      cleanupRef.current?.();
      cleanupRef.current = null;
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

  const ConnectionIcon = isConnected ? Wifi : WifiOff;
  const connectionColor = isConnected ? "text-green-500" : "text-red-500";

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
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
              Chấm công
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
                  Thêm thiết bị để xem dữ liệu chấm công
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
                  const actionColor =
                    latestRecord.action === 0
                      ? "border-teal-500 dark:border-teal-500 bg-teal-50 dark:bg-teal-950"
                      : "border-sky-500 dark:border-sky-500 bg-sky-50 dark:bg-sky-950";
                  const shiftInfo = extractTimestampParts(
                    latestRecord.timestamp,
                  );
                  const shiftDisplay =
                    shiftInfo.date && shiftInfo.date !== "-"
                      ? `${shiftInfo.time} • ${shiftInfo.date}`
                      : shiftInfo.time;

                  return (
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={`${latestRecord.user_id}-${latestRecord.timestamp}-${latestRecord.action}`}
                        initial={{ opacity: 0, y: 24, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -24, scale: 0.98 }}
                        transition={{ duration: 0.3, ease: "easeOut" }}
                        layout
                      >
                        <Card className="border-2 shadow-lg">
                          <CardContent className="p-6">
                            <div className="flex gap-6">
                              <motion.div
                                className="flex-shrink-0 w-72"
                                layout
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ duration: 0.2 }}
                              >
                                <Avatar
                                  className={cn(
                                    "w-72 h-[432px] rounded-2xl border-4 shadow-xl",
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
                              </motion.div>
                              <motion.div
                                className="flex-1 space-y-4"
                                layout
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.25, ease: "easeOut" }}
                              >
                                <DetailItem
                                  label="Mã nhân viên"
                                  value={latestRecord.employee_code || "-"}
                                />
                                <DetailItem
                                  label="Tên nhân viên"
                                  value={
                                    latestRecord.full_name ||
                                    latestRecord.name ||
                                    "-"
                                  }
                                  highlight
                                />
                                <div className="grid grid-cols-2 gap-4 pt-2">
                                  <DetailItem
                                    label="Phòng ban"
                                    value={latestRecord.department || "-"}
                                  />
                                  <DetailItem
                                    label="Chức danh"
                                    value={latestRecord.position || "-"}
                                  />
                                  <DetailItem
                                    label="Giới tính"
                                    value={formatGender(latestRecord.gender)}
                                  />
                                  <DetailItem
                                    label="Ngày vào làm việc"
                                    value={formatHireDate(
                                      latestRecord.hire_date,
                                    )}
                                  />
                                </div>
                                <DetailItem
                                  label={getShiftLabel(latestRecord.action)}
                                  value={shiftDisplay}
                                  highlight
                                />
                              </motion.div>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </AnimatePresence>
                  );
                })()}

              {/* History Table - Previous Actions */}
              {filteredAttendance.length > 1 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Nhật ký chấm công</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-32">Mã nhân viên</TableHead>
                          <TableHead>Tên nhân viên</TableHead>
                          <TableHead className="w-32">Phòng ban</TableHead>
                          <TableHead className="w-32">Chức danh</TableHead>
                          <TableHead className="w-24">Giới tính</TableHead>
                          <TableHead className="w-32">Ngày vào làm</TableHead>
                          <TableHead className="w-40">Thời gian</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <AnimatePresence initial={false}>
                          {filteredAttendance.slice(1).map((record, index) => {
                            const displayName =
                              record.full_name || record.name || "-";
                            const shiftInfo = extractTimestampParts(
                              record.timestamp,
                            );
                            const shiftPrefix =
                              record.action === 0 ? "Vào ca" : "Ra ca";

                            return (
                              <MotionTableRow
                                key={`${record.user_id}-${record.timestamp}-${index}`}
                                layout
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                transition={{ duration: 0.2, ease: "easeOut" }}
                              >
                                <TableCell className="font-mono">
                                  {record.employee_code || "-"}
                                </TableCell>
                                <TableCell className="font-medium">
                                  {displayName}
                                </TableCell>
                                <TableCell>
                                  {record.department || "-"}
                                </TableCell>
                                <TableCell>{record.position || "-"}</TableCell>
                                <TableCell>
                                  {formatGender(record.gender)}
                                </TableCell>
                                <TableCell>
                                  {formatHireDate(record.hire_date)}
                                </TableCell>
                                <TableCell className="font-mono text-sm">
                                  {`${shiftPrefix}: ${shiftInfo.time}`}
                                </TableCell>
                              </MotionTableRow>
                            );
                          })}
                        </AnimatePresence>
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

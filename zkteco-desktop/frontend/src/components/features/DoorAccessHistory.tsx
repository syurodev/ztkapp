import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  Door,
  DoorAccessLog,
  doorAPI,
  devicesAPI,
  Device,
  api,
} from "@/lib/api";
import {
  format,
  isWithinInterval,
  parseISO,
  startOfDay,
  endOfDay,
} from "date-fns";
import {
  Calendar as CalendarIcon,
  DoorOpen,
  History,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DateRange } from "react-day-picker";
import { toast } from "sonner";

const LOG_FETCH_LIMIT = 200;
const ACTION_LABELS: Record<string, string> = {
  unlock: "Mở cửa",
};

const STATUS_STYLES: Record<string, string> = {
  success: "bg-emerald-500 text-white",
  failed: "bg-destructive text-destructive-foreground",
  error: "bg-destructive text-destructive-foreground",
};

const formatDateRangeLabel = (range: DateRange | undefined) => {
  if (!range?.from && !range?.to) {
    return "Lọc theo ngày";
  }

  if (range.from && !range.to) {
    return format(range.from, "dd/MM/yyyy");
  }

  if (range.from && range.to) {
    return `${format(range.from, "dd/MM/yyyy")} - ${format(range.to, "dd/MM/yyyy")}`;
  }

  return "Lọc theo ngày";
};

export function DoorAccessHistory() {
  const [doors, setDoors] = useState<Door[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDoorId, setSelectedDoorId] = useState<string | undefined>();
  const [logs, setLogs] = useState<DoorAccessLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange | undefined>();
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);

  const selectedDevice = useMemo(() => {
    if (!selectedDoorId || selectedDoorId === "all") return null;
    const door = doors.find((d) => d.id.toString() === selectedDoorId);
    if (!door || !door.device_id) return null;
    return devices.find((d) => d.id === door.device_id) || null;
  }, [selectedDoorId, doors, devices]);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [doorsResponse, devicesResponse] = await Promise.all([
          doorAPI.getAllDoors(),
          devicesAPI.getAllDevices(),
        ]);

        if (doorsResponse.success) {
          setDoors(doorsResponse.data);
          if (doorsResponse.data.length > 0) {
            setSelectedDoorId(
              (prev) => prev ?? doorsResponse.data[0].id.toString(),
            );
          }
        } else {
          toast.error(
            (doorsResponse as any)?.message || "Không thể tải danh sách cửa",
          );
        }

        // The device API response is structured differently
        const deviceList = devicesResponse?.devices || [];
        setDevices(deviceList);
      } catch (error) {
        console.error("Error loading initial data:", error);
        toast.error("Không thể tải dữ liệu ban đầu");
      }
    };

    loadInitialData();
  }, []);

  const handleSyncFromAttendance = async () => {
    if (!selectedDoorId || selectedDoorId === "all") {
      toast.warning("Vui lòng chọn một cửa cụ thể để đồng bộ.");
      return;
    }
    setSyncLoading(true);
    try {
      const response = await api.post(
        `/doors/${selectedDoorId}/sync-from-attendance`,
      );
      if (response.data.success) {
        toast.success(response.data.message);
        fetchLogs(); // Refresh the logs view
      }
    } catch (error) {
      console.error("Sync from attendance failed:", error);
      toast.error("Không thể đồng bộ từ máy chấm công.");
    } finally {
      setSyncLoading(false);
    }
  };

  const fetchLogs = useCallback(async () => {
    if (!selectedDoorId) {
      setLogs([]);
      return;
    }

    setIsLoading(true);
    try {
      let response:
        | { success: boolean; data: DoorAccessLog[]; message?: string }
        | undefined;

      if (selectedDoorId === "all") {
        response = await doorAPI.getAllAccessLogs(
          undefined,
          LOG_FETCH_LIMIT,
          0,
        );
      } else {
        response = await doorAPI.getDoorAccessLogs(
          Number(selectedDoorId),
          LOG_FETCH_LIMIT,
          0,
        );
      }

      if (response?.success) {
        setLogs(response.data);
      } else {
        toast.error(response?.message || "Không thể tải nhật ký cửa");
        setLogs([]);
      }
    } catch (error) {
      console.error("Error loading door access logs:", error);
      toast.error("Không thể tải nhật ký cửa");
      setLogs([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDoorId]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const filteredLogs = useMemo(() => {
    if (!dateRange?.from && !dateRange?.to) {
      return logs;
    }

    if (!dateRange?.from) {
      return logs;
    }

    const rangeStart = startOfDay(dateRange.from);
    const rangeEnd = endOfDay(dateRange.to ?? dateRange.from);

    return logs.filter((log) => {
      try {
        const timestamp = parseISO(log.timestamp);
        return isWithinInterval(timestamp, {
          start: rangeStart,
          end: rangeEnd,
        });
      } catch (error) {
        console.error("Failed to parse log timestamp", error);
        return false;
      }
    });
  }, [logs, dateRange]);

  const doorNameMap = useMemo(() => {
    return doors.reduce<Record<string, string>>((acc, door) => {
      acc[door.id.toString()] = door.name;
      return acc;
    }, {});
  }, [doors]);

  const currentDoorLabel =
    selectedDoorId && selectedDoorId !== "all"
      ? (doorNameMap[selectedDoorId] ?? `Cửa #${selectedDoorId}`)
      : "Tất cả cửa";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1.5">
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Lịch sử mở cửa
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Theo dõi các lần mở cửa và trạng thái thực thi theo từng thiết bị.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Select
              value={selectedDoorId}
              onValueChange={(value) => setSelectedDoorId(value)}
            >
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="Chọn cửa cần xem" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả cửa</SelectItem>
                {doors.map((door) => (
                  <SelectItem key={door.id} value={door.id.toString()}>
                    {door.name}
                    {door.location ? ` — ${door.location}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Popover open={isCalendarOpen} onOpenChange={setIsCalendarOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="w-[220px] justify-start gap-2"
                >
                  <CalendarIcon className="h-4 w-4" />
                  {formatDateRangeLabel(dateRange)}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar
                  mode="range"
                  selected={dateRange}
                  onSelect={(range) => setDateRange(range)}
                  numberOfMonths={2}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDateRange(undefined)}
              disabled={!dateRange?.from && !dateRange?.to}
            >
              <Search className="h-4 w-4" />
              Xóa lọc
            </Button>
            {selectedDevice?.device_type === "pull" && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleSyncFromAttendance}
                disabled={syncLoading}
              >
                {syncLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <History className="h-4 w-4" />
                )}
                <span className="ml-2">Lấy lịch sử từ máy</span>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchLogs}
              disabled={isLoading || !selectedDoorId}
            >
              {" "}
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{currentDoorLabel}</Badge>
            <Badge variant="outline">
              {filteredLogs.length} / {logs.length} bản ghi
            </Badge>
            {dateRange?.from && (
              <Badge variant="outline">
                Khoảng: {formatDateRangeLabel(dateRange)}
              </Badge>
            )}
          </div>

          {!selectedDoorId ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted-foreground">
              <DoorOpen className="h-10 w-10" />
              <div>
                <p className="font-medium text-foreground">
                  Vui lòng chọn một cửa để xem lịch sử.
                </p>
                <p className="text-sm">
                  Chọn cửa ở phía trên hoặc dùng mục &ldquo;Tất cả cửa&rdquo;.
                </p>
              </div>
            </div>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
              <Loader2 className="h-10 w-10 animate-spin" />
              Đang tải lịch sử mở cửa...
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
              <History className="h-10 w-10" />
              <div className="text-center">
                <p className="font-medium text-foreground">
                  Không có bản ghi phù hợp.
                </p>
                <p className="text-sm">
                  {logs.length === 0
                    ? "Chưa ghi nhận lần mở cửa nào cho lựa chọn hiện tại."
                    : "Thử điều chỉnh lại bộ lọc ngày để xem thêm bản ghi."}
                </p>
              </div>
            </div>
          ) : (
            <ScrollArea className="h-[500px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thời gian</TableHead>
                    <TableHead>Cửa</TableHead>
                    <TableHead>Người thực hiện</TableHead>
                    <TableHead>Hành động</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Ghi chú</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log) => {
                    const actionLabel = ACTION_LABELS[log.action] ?? log.action;
                    const statusClass =
                      STATUS_STYLES[log.status] ??
                      "bg-secondary text-secondary-foreground";

                    return (
                      <TableRow key={log.id}>
                        <TableCell className="whitespace-nowrap font-medium">
                          {format(
                            parseISO(log.timestamp),
                            "dd/MM/yyyy HH:mm:ss",
                          )}
                        </TableCell>
                        <TableCell>
                          {doorNameMap[log.door_id.toString()] ??
                            `Cửa #${log.door_id}`}
                        </TableCell>
                        <TableCell>
                          {log.user_name
                            ? log.user_name
                            : log.user_id
                              ? `User #${log.user_id}`
                              : "Không xác định"}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{actionLabel}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={cn("capitalize", statusClass)}>
                            {log.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[280px] truncate">
                          {log.notes || "—"}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

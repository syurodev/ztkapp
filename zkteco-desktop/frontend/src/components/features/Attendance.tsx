import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDevice } from "@/contexts/DeviceContext";
import { attendanceAPI } from "@/lib/api";
import {
  buildAvatarUrl,
  getResourceDomain,
  RESOURCE_DOMAIN_EVENT,
} from "@/lib/utils";
import { ATTENDANCE_METHOD_MAP, PUNCH_ACTION_MAP } from "@/types/constant";
import { format } from "date-fns";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Calendar as CalendarIcon,
  CheckCircle2,
  Clock,
  Download,
  History,
  List,
  Loader2,
  Monitor,
  RefreshCw,
  Send,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "../ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { AttendanceHistoryView } from "./AttendanceHistoryView";

interface AttendanceRecord {
  user_id: string;
  name: string;
  full_name: string;
  avatar_url?: string | null;
  timestamp: string;
  method: number;
  action: number;
  error_message: string | null;
  id: number;
  is_synced?: boolean; // legacy flag from older versions
  is_pushed?: boolean; // new push status flag
  sync_status?: string; // new field: 'pending', 'synced', 'skipped'
}

const PAGE_SIZE = 20;
const MotionTableRow = motion(TableRow);

const getSyncStatusBadge = (record: AttendanceRecord) => {
  // Use explicit sync_status if available, fallback to is_pushed (then is_synced for legacy data)
  const fallbackSynced =
    record.is_pushed !== undefined ? record.is_pushed : false;

  const syncStatus =
    record.is_pushed || (fallbackSynced ? "synced" : "pending");

  switch (syncStatus) {
    case true:
      return (
        <Badge
          variant="default"
          className="bg-green-100 text-green-800 border-green-300"
        >
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Đã đồng bộ
        </Badge>
      );
    default:
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 border-yellow-300"
        >
          <Clock className="h-3 w-3 mr-1" />
          Đang chờ
        </Badge>
      );
  }
};

export function Attendance() {
  const { activeDevice } = useDevice();
  const [viewMode, setViewMode] = useState<"table" | "history">("table");
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [historyData, setHistoryData] = useState<AttendanceRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isDailySyncing, setIsDailySyncing] = useState(false);
  const [showDailySyncDialog, setShowDailySyncDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [pageInputValue, setPageInputValue] = useState("");
  const [resourceDomain, setResourceDomain] = useState<string>("");
  const [dateRange, setDateRange] = useState<{
    from: Date | undefined;
    to: Date | undefined;
  }>({ from: new Date(), to: new Date() }); // Mặc định là hôm nay

  // Load resource domain on mount and listen for updates
  useEffect(() => {
    const refreshResourceDomain = () => {
      void getResourceDomain().then(setResourceDomain);
    };

    refreshResourceDomain();

    if (typeof window === "undefined") {
      return;
    }

    const handleResourceDomainChange = (event: Event): void => {
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
    // Tải dữ liệu khi activeDevice, viewMode hoặc dateRange thay đổi
    // và đảm bảo rằng chúng ta không tải lại lịch sử khi đang ở chế độ bảng và ngược lại
    if (!activeDevice) {
      setAttendance([]);
      setHistoryData([]);
      setError(null);
      return;
    }

    if (viewMode === "table") {
      loadAttendance();
    } else {
      // viewMode === "history"
      loadHistory();
    }
  }, [activeDevice, viewMode, dateRange]); // Sử dụng dateRange thay vì selectedDate

  const loadAttendance = async (page: number = 1) => {
    if (!activeDevice) return;

    const isFirstLoad = page === 1;
    if (isFirstLoad) {
      setIsLoading(true);
      setCurrentPage(1); // Đặt lại trang về 1 khi tải lần đầu
    } else {
      setIsPageLoading(true);
    }

    setError(null);
    try {
      const offset = (page - 1) * PAGE_SIZE;

      // Nếu from và to giống nhau, dùng param 'date' (single date)
      // Nếu khác nhau, dùng start_date và end_date
      const isSameDay =
        dateRange.from &&
        dateRange.to &&
        format(dateRange.from, "yyyy-MM-dd") ===
          format(dateRange.to, "yyyy-MM-dd");

      const requestParams: any = {
        limit: PAGE_SIZE,
        offset: offset,
        device_id: activeDevice.id,
      };

      if (isSameDay) {
        // Single date
        requestParams.date = format(dateRange.from!, "yyyy-MM-dd");
      } else {
        // Date range
        if (dateRange.from) {
          requestParams.start_date = format(dateRange.from, "yyyy-MM-dd");
        }
        if (dateRange.to) {
          requestParams.end_date = format(dateRange.to, "yyyy-MM-dd");
        }
      }

      const response = await attendanceAPI.getAttendance(requestParams);

      const data: AttendanceRecord[] = response.data || [];
      setAttendance(data);
      setTotalCount(response.pagination?.total_count || 0);
      setCurrentPage(page);
    } catch (err) {
      setError("Không thể tải dữ liệu chấm công từ cơ sở dữ liệu.");
      console.error("Error loading attendance:", err);
      toast.error("Lỗi", {
        description: "Không thể lấy dữ liệu chấm công từ cơ sở dữ liệu cục bộ.",
      });
    } finally {
      setIsLoading(false);
      setIsPageLoading(false);
    }
  };

  const loadHistory = async () => {
    if (!activeDevice) return;

    setIsHistoryLoading(true);
    setError(null);
    try {
      // Sử dụng from date cho history
      const dateStr =
        dateRange.from &&
        dateRange.to &&
        format(dateRange.from, "yyyy-MM-dd") ===
          format(dateRange.to, "yyyy-MM-dd")
          ? format(dateRange.from, "yyyy-MM-dd")
          : dateRange.from
            ? format(dateRange.from, "yyyy-MM-dd")
            : undefined;

      const response = await attendanceAPI.getHistory({
        date: dateStr,
        device_id: activeDevice.id,
      });

      if (response.success) {
        setHistoryData(response.data);
      } else {
        setError("Không thể tải lịch sử chấm công");
      }
    } catch (err) {
      console.error("Error fetching attendance history:", err);
      setError("Không thể tải lịch sử chấm công");
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const handleSync = async () => {
    if (!activeDevice) return;

    setIsSyncing(true);
    setError(null);
    toast.info("Đang đồng bộ...", {
      description:
        "Đang lấy dữ liệu chấm công từ thiết bị. Vui lòng chờ trong giây lát.",
    });
    try {
      const response = await attendanceAPI.syncAttendance();
      toast.success("Đồng bộ hoàn tất", {
        description: `Đã đồng bộ thêm ${
          response.sync_stats?.new || 0
        } bản ghi mới.`,
      });
      await loadAttendance(); // Refresh data from DB after sync
    } catch (err) {
      setError("Không thể đồng bộ dữ liệu chấm công từ thiết bị.");
      console.error("Error syncing attendance:", err);
      toast.error("Đồng bộ thất bại", {
        description: "Không thể lấy dữ liệu chấm công từ thiết bị.",
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const handlePageInputChange = (value: string) => {
    const maxLength = totalPages.toString().length;
    const numbersOnly = value.replace(/[^0-9]/g, "");

    if (numbersOnly.length <= maxLength) {
      setPageInputValue(numbersOnly);
    }
  };

  const handlePageJump = () => {
    const pageNumber = parseInt(pageInputValue.trim());

    if (isNaN(pageNumber) || pageNumber < 1) {
      toast.error("Lỗi", {
        description: "Vui lòng nhập số trang hợp lệ.",
      });
      return;
    }

    if (pageNumber > totalPages) {
      toast.error("Lỗi", {
        description: `Trang phải nằm trong khoảng từ 1 đến ${totalPages.toLocaleString()}.`,
      });
      return;
    }

    if (pageNumber === currentPage) {
      setPageInputValue("");
      return;
    }

    loadAttendance(pageNumber);
    setPageInputValue("");
  };

  const handleDailySyncConfirm = async () => {
    if (!activeDevice) return;

    setIsDailySyncing(true);
    setShowDailySyncDialog(false);
    setError(null);

    // Sử dụng dateRange thay vì selectedDate
    const dateStr =
      dateRange.from &&
      dateRange.to &&
      format(dateRange.from, "yyyy-MM-dd") ===
        format(dateRange.to, "yyyy-MM-dd")
        ? format(dateRange.from, "yyyy-MM-dd")
        : undefined;

    const targetDateLabel = dateStr || "tất cả ngày đang chờ";

    toast.info("Đang đồng bộ...", {
      description: `Đang gửi dữ liệu chấm công cho ${targetDateLabel}.`,
    });

    try {
      const response = await attendanceAPI.syncDailyAttendance({
        date: dateStr,
        device_id: activeDevice.id,
      });

      if (response.success) {
        toast.success("Đồng bộ thành công!", {
          description: response.message
            ? response.message
            : `Đã gửi dữ liệu chấm công cho ${targetDateLabel}.`,
        });
        await loadAttendance();
      } else {
        toast.error("Đồng bộ thất bại", {
          description: response.error || "Không thể gửi dữ liệu chấm công.",
        });
      }
    } catch (err) {
      setError("Không thể đồng bộ dữ liệu chấm công trong ngày.");
      console.error("Error syncing daily attendance:", err);
      toast.error("Lỗi đồng bộ", {
        description:
          "Không thể gửi dữ liệu chấm công cho ngày hôm nay. Vui lòng thử lại.",
      });
    } finally {
      setIsDailySyncing(false);
    }
  };

  // const handleExportExcel = async () => {
  //   if (!activeDevice) return;

  //   setIsExporting(true);
  //   setError(null);

  //   const startDateStr = dateRange.from
  //     ? format(dateRange.from, "yyyy-MM-dd")
  //     : undefined;
  //   const endDateStr = dateRange.to
  //     ? format(dateRange.to, "yyyy-MM-dd")
  //     : undefined;

  //   const rangeLabel =
  //     startDateStr && endDateStr
  //       ? `từ ${format(dateRange.from!, "dd/MM/yyyy")} đến ${format(dateRange.to!, "dd/MM/yyyy")}`
  //       : startDateStr
  //         ? `từ ${format(dateRange.from!, "dd/MM/yyyy")}`
  //         : endDateStr
  //           ? `đến ${format(dateRange.to!, "dd/MM/yyyy")}`
  //           : "tất cả";

  //   toast.info("Đang xuất Excel...", {
  //     description: `Đang xuất dữ liệu chấm công ${rangeLabel}.`,
  //   });

  //   try {
  //     await attendanceAPI.exportExcel({
  //       start_date: startDateStr,
  //       end_date: endDateStr,
  //       device_id: activeDevice.id,
  //     });

  //     toast.success("Xuất Excel thành công!", {
  //       description: `Đã xuất dữ liệu chấm công ${rangeLabel}.`,
  //     });
  //   } catch (err) {
  //     console.error("Error exporting attendance to Excel:", err);
  //     toast.error("Xuất Excel thất bại", {
  //       description: "Không thể xuất dữ liệu chấm công. Vui lòng thử lại.",
  //     });
  //   } finally {
  //     setIsExporting(false);
  //   }
  // };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const paginatedAttendance = attendance; // No client-side slicing needed as API handles pagination

  // Label for dialog
  const dialogTargetLabel =
    dateRange.from &&
    dateRange.to &&
    format(dateRange.from, "yyyy-MM-dd") === format(dateRange.to, "yyyy-MM-dd")
      ? format(dateRange.from, "dd/MM/yyyy")
      : dateRange.from && dateRange.to
        ? `từ ${format(dateRange.from, "dd/MM/yyyy")} đến ${format(dateRange.to, "dd/MM/yyyy")}`
        : "tất cả ngày đang chờ";

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      {!activeDevice && (
        <Alert>
          <Monitor className="h-4 w-4" />
          <AlertDescription>
            Vui lòng chọn thiết bị để xem dữ liệu chấm công. Truy cập mục Quản
            lý thiết bị để cấu hình thiết bị.
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-6 w-6" />
              Nhật ký chấm công
            </CardTitle>
            <div className="flex gap-2">
              <Button
                variant={viewMode === "table" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("table")}
                disabled={!activeDevice && viewMode === "history"} // Không cho phép chuyển sang lịch sử nếu không có thiết bị
              >
                <List className="h-4 w-4 mr-2" />
                Bảng
              </Button>
              <Button
                variant={viewMode === "history" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("history")}
                disabled={!activeDevice && viewMode === "table"} // Không cho phép chuyển sang bảng nếu không có thiết bị
              >
                <History className="h-4 w-4 mr-2" />
                Lịch sử
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {viewMode === "history" ? (
            <AttendanceHistoryView
              data={historyData}
              dateRange={dateRange}
              onDateRangeChange={setDateRange}
              onRefresh={loadHistory}
              isLoading={isHistoryLoading}
              error={error}
            />
          ) : (
            // Logic cho chế độ xem 'table'
            <>
              {activeDevice ? (
                // Hiển thị các điều khiển và bảng khi có activeDevice
                <>
                  {/* Hàng chọn khoảng thời gian và xuất Excel */}
                  <div className="flex items-center gap-4 pb-4 border-b">
                    <div className="flex items-center gap-2 flex-1">
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button variant="outline" className="gap-2">
                            <CalendarIcon className="h-4 w-4" />
                            {dateRange.from ? (
                              dateRange.to &&
                              format(dateRange.from, "yyyy-MM-dd") !==
                                format(dateRange.to, "yyyy-MM-dd") ? (
                                <>
                                  {format(dateRange.from, "dd/MM/yyyy")} -{" "}
                                  {format(dateRange.to, "dd/MM/yyyy")}
                                </>
                              ) : (
                                format(dateRange.from, "dd/MM/yyyy")
                              )
                            ) : (
                              "Chọn khoảng thời gian"
                            )}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="range"
                            selected={{
                              from: dateRange.from,
                              to: dateRange.to,
                            }}
                            onSelect={(range) =>
                              setDateRange({
                                from: range?.from,
                                to: range?.to,
                              })
                            }
                            numberOfMonths={2}
                            initialFocus
                          />
                        </PopoverContent>
                      </Popover>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const today = new Date();
                          setDateRange({ from: today, to: today });
                        }}
                      >
                        Hôm nay
                      </Button>
                      {(dateRange.from || dateRange.to) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setDateRange({ from: undefined, to: undefined })
                          }
                        >
                          Xóa
                        </Button>
                      )}
                    </div>
                    <Badge variant="secondary">
                      {totalCount.toLocaleString()} bản ghi
                    </Badge>
                    {/*<Button
                      variant="default"
                      size="sm"
                      onClick={handleExportExcel}
                      disabled={isExporting || isLoading}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      {isExporting ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                      )}
                      Xuất Excel
                    </Button>*/}

                    {/* Only show sync button for pull devices, push devices send data automatically */}
                    {activeDevice.device_type === "pull" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={isSyncing || isLoading || isDailySyncing}
                      >
                        {isSyncing ? (
                          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="mr-2 h-4 w-4" />
                        )}
                        Lấy dữ liệu từ {activeDevice.name}
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setShowDailySyncDialog(true);
                      }}
                      disabled={isLoading || isSyncing || isDailySyncing}
                    >
                      {isDailySyncing ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="mr-2 h-4 w-4" />
                      )}
                      Đồng bộ chấm công trong ngày
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => loadAttendance()}
                      disabled={
                        isLoading ||
                        isSyncing ||
                        isPageLoading ||
                        isDailySyncing
                      }
                    >
                      {(isLoading && !isSyncing) || isPageLoading ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Làm mới
                    </Button>
                  </div>

                  {/* Hiển thị bảng hoặc thông báo */}
                  {isLoading && attendance.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8">
                      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
                      <p className="text-muted-foreground">
                        Đang tải dữ liệu chấm công...
                      </p>
                    </div>
                  ) : error ? (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  ) : attendance.length === 0 ? (
                    <div className="text-center py-8">
                      <p className="text-muted-foreground">
                        Không tìm thấy dữ liệu chấm công cho khoảng thời gian đã
                        chọn.
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Hãy đồng bộ với thiết bị để lấy dữ liệu hoặc chọn khoảng
                        thời gian khác.
                      </p>
                    </div>
                  ) : (
                    <>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>ID</TableHead>
                            <TableHead>Họ tên</TableHead>
                            <TableHead>Thời điểm</TableHead>
                            <TableHead>Phương thức</TableHead>
                            <TableHead>Hành động</TableHead>
                            <TableHead>Trạng thái đồng bộ</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          <AnimatePresence initial={false}>
                            {paginatedAttendance.map((record) => {
                              const initials = record.name
                                .split(" ")
                                .map((n) => n[0])
                                .join("")
                                .toUpperCase()
                                .slice(0, 2);
                              return (
                                <MotionTableRow
                                  key={record.id}
                                  layout
                                  initial={{ opacity: 0, y: 12 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  exit={{ opacity: 0, y: -12 }}
                                  transition={{
                                    duration: 0.2,
                                    ease: "easeOut",
                                  }}
                                >
                                  <TableCell>{record.user_id}</TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-2">
                                      <Avatar className="h-8 w-8">
                                        {record.avatar_url && (
                                          <AvatarImage
                                            src={buildAvatarUrl(
                                              record.avatar_url,
                                              resourceDomain,
                                            )}
                                            alt={
                                              record.full_name ?? record.name
                                            }
                                          />
                                        )}
                                        <AvatarFallback className="text-xs">
                                          {initials}
                                        </AvatarFallback>
                                      </Avatar>
                                      {record.full_name ?? record.name}
                                    </div>
                                  </TableCell>
                                  <TableCell>
                                    {format(
                                      new Date(record.timestamp),
                                      "yyyy-MM-dd HH:mm",
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {ATTENDANCE_METHOD_MAP[record.method] ||
                                      "Không xác định"}
                                  </TableCell>
                                  <TableCell>
                                    {PUNCH_ACTION_MAP[record.action] ||
                                      "Không xác định"}
                                  </TableCell>
                                  <TableCell>
                                    <Tooltip>
                                      <TooltipTrigger>
                                        {getSyncStatusBadge(record)}
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        <p>
                                          {record.error_message
                                            ? record.error_message
                                            : ""}
                                        </p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TableCell>
                                </MotionTableRow>
                              );
                            })}
                          </AnimatePresence>
                        </TableBody>
                      </Table>
                      {totalPages > 1 && (
                        <div className="flex items-center justify-center pt-4">
                          <Pagination>
                            <PaginationContent>
                              <PaginationItem>
                                <PaginationPrevious
                                  onClick={(e) => {
                                    e.preventDefault();
                                    if (currentPage > 1) {
                                      loadAttendance(currentPage - 1);
                                    }
                                  }}
                                  aria-disabled={
                                    currentPage === 1 || isPageLoading
                                  }
                                  className={
                                    currentPage === 1 || isPageLoading
                                      ? "pointer-events-none opacity-50"
                                      : undefined
                                  }
                                />
                              </PaginationItem>
                              <PaginationItem>
                                <div className="flex items-center gap-2 text-sm">
                                  <span>Đi tới trang:</span>
                                  <Input
                                    type="text"
                                    value={pageInputValue}
                                    onChange={(e) =>
                                      handlePageInputChange(e.target.value)
                                    }
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") {
                                        e.preventDefault();
                                        handlePageJump();
                                      } else if (e.key === "Escape") {
                                        setPageInputValue("");
                                      }
                                    }}
                                    placeholder={currentPage.toString()}
                                    className="w-20 h-8 text-center"
                                    disabled={isPageLoading || isLoading}
                                    title={`Nhập số trang (1-${totalPages.toLocaleString()})`}
                                  />
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handlePageJump}
                                    disabled={
                                      isPageLoading ||
                                      isLoading ||
                                      !pageInputValue.trim()
                                    }
                                    className="h-8 px-3"
                                  >
                                    Đi
                                  </Button>
                                </div>
                              </PaginationItem>
                              <PaginationItem>
                                <span className="text-sm font-medium flex items-center gap-2">
                                  {isPageLoading && (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                  )}
                                  Trang {currentPage} / {totalPages}
                                </span>
                              </PaginationItem>
                              <PaginationItem>
                                <PaginationNext
                                  onClick={(e) => {
                                    e.preventDefault();
                                    if (currentPage < totalPages) {
                                      loadAttendance(currentPage + 1);
                                    }
                                  }}
                                  aria-disabled={
                                    currentPage === totalPages || isPageLoading
                                  }
                                  className={
                                    currentPage === totalPages || isPageLoading
                                      ? "pointer-events-none opacity-50"
                                      : undefined
                                  }
                                />
                              </PaginationItem>
                            </PaginationContent>
                          </Pagination>
                        </div>
                      )}
                    </>
                  )}
                </>
              ) : (
                // Hiển thị thông báo khi không có activeDevice trong chế độ bảng
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <Monitor className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">Chưa chọn thiết bị</p>
                    <p className="text-sm text-muted-foreground">
                      Chọn thiết bị để xem dữ liệu chấm công
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Daily Sync Confirmation Dialog */}
      <Dialog open={showDailySyncDialog} onOpenChange={setShowDailySyncDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Xác nhận đồng bộ chấm công trong ngày
            </DialogTitle>
            <DialogDescription className="space-y-2">
              <p>
                Bạn có chắc chắn muốn gửi dữ liệu chấm công cho{" "}
                {dialogTargetLabel}?
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-yellow-800">
                    <p className="font-medium">Lưu ý quan trọng:</p>
                    <p>
                      Sau khi đồng bộ, dữ liệu chấm công (nếu có) sẽ được chốt
                      theo logic sau:
                    </p>
                    <ul className="mt-1 list-disc list-inside ml-2 space-y-1">
                      <li>
                        <strong>Check-in đầu tiên:</strong> Lần vào ca đầu tiên
                        trong ngày
                      </li>
                      <li>
                        <strong>Check-out cuối cùng:</strong> Lần ra ca cuối
                        cùng trong ngày
                      </li>
                    </ul>
                    <p className="mt-2">
                      Dữ liệu sẽ được gửi lên hệ thống ngoài và không thể hoàn
                      tác.
                    </p>
                  </div>
                </div>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDailySyncDialog(false)}
              disabled={isDailySyncing}
            >
              Hủy
            </Button>
            <Button
              onClick={handleDailySyncConfirm}
              disabled={isDailySyncing}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isDailySyncing ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Đang gửi...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Xác nhận gửi
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

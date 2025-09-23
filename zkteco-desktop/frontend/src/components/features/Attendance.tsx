import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
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
import { ATTENDANCE_METHOD_MAP, PUNCH_ACTION_MAP } from "@/types/constant";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  Monitor,
  RefreshCw,
  Send,
  Calendar,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "../ui/badge";

interface AttendanceRecord {
  user_id: string;
  name: string;
  timestamp: string;
  method: number;
  action: number;
  id: number;
  is_synced: boolean; // kept for backward compatibility
  sync_status?: string; // new field: 'pending', 'synced', 'skipped'
}

const PAGE_SIZE = 20;

const getSyncStatusBadge = (record: AttendanceRecord) => {
  // Use new sync_status if available, fallback to is_synced for backward compatibility
  const syncStatus = record.sync_status || (record.is_synced ? 'synced' : 'pending');

  switch (syncStatus) {
    case 'synced':
      return (
        <Badge
          variant="default"
          className="bg-green-100 text-green-800 border-green-300"
        >
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Synced
        </Badge>
      );
    case 'skipped':
      return (
        <Badge
          variant="secondary"
          className="bg-gray-100 text-gray-800 border-gray-300"
        >
          <Monitor className="h-3 w-3 mr-1" />
          Skipped
        </Badge>
      );
    case 'pending':
    default:
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 border-yellow-300"
        >
          <Clock className="h-3 w-3 mr-1" />
          Pending
        </Badge>
      );
  }
};

export function Attendance() {
  const { activeDevice } = useDevice();
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isDailySyncing, setIsDailySyncing] = useState(false);
  const [showDailySyncDialog, setShowDailySyncDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [pageInputValue, setPageInputValue] = useState("");

  useEffect(() => {
    if (activeDevice) {
      loadAttendance();
    } else {
      setAttendance([]);
      setError(null);
    }
  }, [activeDevice]);

  const loadAttendance = async (page: number = 1) => {
    if (!activeDevice) return;

    const isFirstLoad = page === 1;
    if (isFirstLoad) {
      setIsLoading(true);
      setCurrentPage(1);
    } else {
      setIsPageLoading(true);
    }

    setError(null);
    try {
      const offset = (page - 1) * PAGE_SIZE;
      const response = await attendanceAPI.getAttendance({
        limit: PAGE_SIZE,
        offset: offset,
        device_id: activeDevice.id,
      });

      const data: AttendanceRecord[] = response.data || [];
      setAttendance(data);
      setTotalCount(response.pagination?.total_count || 0);
      setCurrentPage(page);
    } catch (err) {
      setError("Failed to load attendance records from the database.");
      console.error("Error loading attendance:", err);
      toast.error("Error", {
        description: "Could not fetch attendance logs from the local database.",
      });
    } finally {
      setIsLoading(false);
      setIsPageLoading(false);
    }
  };

  const handleSync = async () => {
    if (!activeDevice) return;

    setIsSyncing(true);
    setError(null);
    toast.info("Syncing...", {
      description:
        "Fetching attendance logs from the device. This may take a moment.",
    });
    try {
      const response = await attendanceAPI.syncAttendance();
      toast.success("Sync Complete", {
        description: `Synced ${response.sync_stats?.new || 0} new records.`,
      });
      await loadAttendance(); // Refresh data from DB after sync
    } catch (err) {
      setError("Failed to sync attendance records from the device.");
      console.error("Error syncing attendance:", err);
      toast.error("Sync Failed", {
        description: "Could not fetch attendance logs from the device.",
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const handlePageInputChange = (value: string) => {
    // Only allow numbers and limit length based on totalPages digits
    const maxLength = totalPages.toString().length;
    const numbersOnly = value.replace(/[^0-9]/g, "");

    if (numbersOnly.length <= maxLength) {
      setPageInputValue(numbersOnly);
    }
  };

  const handlePageJump = () => {
    const pageNumber = parseInt(pageInputValue.trim());

    // Validation
    if (isNaN(pageNumber) || pageNumber < 1) {
      toast.error("Error", {
        description: "Please enter a valid page number.",
      });
      return;
    }

    if (pageNumber > totalPages) {
      toast.error("Error", {
        description: `Page must be between 1 and ${totalPages.toLocaleString()}.`,
      });
      return;
    }

    if (pageNumber === currentPage) {
      setPageInputValue(""); // Clear input if same page
      return;
    }

    // Navigate to page
    loadAttendance(pageNumber);
    setPageInputValue(""); // Clear input after successful navigation
  };

  const handleDailySyncConfirm = async () => {
    if (!activeDevice) return;

    setIsDailySyncing(true);
    setShowDailySyncDialog(false);
    setError(null);

    toast.info("Syncing...", {
      description: "Sending today's attendance data with first checkin, last checkout logic.",
    });

    try {
      const response = await attendanceAPI.syncDailyAttendance({
        device_id: activeDevice.id,
      });

      if (response.success) {
        toast.success("Sync Successful!", {
          description: `Sent attendance data for ${response.data?.count || 0} employees on ${response.data?.date || "today"}.`,
        });
      } else {
        toast.error("Sync Failed", {
          description: response.error || "Failed to send attendance data.",
        });
      }
    } catch (err) {
      setError("Failed to sync daily attendance data.");
      console.error("Error syncing daily attendance:", err);
      toast.error("Sync Error", {
        description: "Could not send today's attendance data. Please try again.",
      });
    } finally {
      setIsDailySyncing(false);
    }
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const paginatedAttendance = attendance; // No client-side slicing needed

  return (
    <div className="space-y-6">
      {!activeDevice && (
        <Alert>
          <Monitor className="h-4 w-4" />
          <AlertDescription>
            Please select a device first to view attendance records. Go to
            Device Management to configure a device.
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-6 w-6" />
            Attendance Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          {activeDevice && (
            <div className="flex items-center justify-between pb-4">
              <p className="text-sm text-muted-foreground">
                {totalCount > 0
                  ? `Displaying ${totalCount.toLocaleString()} records from the local database.`
                  : "Displaying logs from the local database."}
              </p>
              <div className="flex gap-2">
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
                  Get logs from {activeDevice.name}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDailySyncDialog(true)}
                  disabled={isLoading || isSyncing || isDailySyncing}
                >
                  {isDailySyncing ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  Sync Daily Attendance
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadAttendance()}
                  disabled={isLoading || isSyncing || isPageLoading || isDailySyncing}
                >
                  {(isLoading && !isSyncing) || isPageLoading ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Refresh
                </Button>
              </div>
            </div>
          )}
          {!activeDevice ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Monitor className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No device selected</p>
                <p className="text-sm text-muted-foreground">
                  Select a device to view attendance records
                </p>
              </div>
            </div>
          ) : isLoading && attendance.length === 0 ? (
            <p>Loading attendance...</p>
          ) : error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : attendance.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">
                No attendance records found.
              </p>
              <p className="text-sm text-muted-foreground">
                Try syncing with the device to fetch logs.
              </p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>User ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Sync Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedAttendance.map((record, index) => (
                    <TableRow key={record.id}>
                      <TableCell>
                        {(currentPage - 1) * PAGE_SIZE + index + 1}
                      </TableCell>
                      <TableCell>{record.user_id}</TableCell>
                      <TableCell>{record.name}</TableCell>
                      <TableCell>{record.timestamp}</TableCell>
                      <TableCell>
                        {ATTENDANCE_METHOD_MAP[record.method] || "Unknown"}
                      </TableCell>
                      <TableCell>
                        {PUNCH_ACTION_MAP[record.action] || "Unknown"}
                      </TableCell>
                      <TableCell>{getSyncStatusBadge(record)}</TableCell>
                    </TableRow>
                  ))}
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
                          aria-disabled={currentPage === 1 || isPageLoading}
                          className={
                            currentPage === 1 || isPageLoading
                              ? "pointer-events-none opacity-50"
                              : undefined
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <div className="flex items-center gap-2 text-sm">
                          <span>Go to page:</span>
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
                            title={`Enter page (1-${totalPages.toLocaleString()})`}
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
                            Go
                          </Button>
                        </div>
                      </PaginationItem>
                      <PaginationItem>
                        <span className="text-sm font-medium flex items-center gap-2">
                          {isPageLoading && (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          )}
                          Page {currentPage} / {totalPages}
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
        </CardContent>
      </Card>

      {/* Daily Sync Confirmation Dialog */}
      <Dialog open={showDailySyncDialog} onOpenChange={setShowDailySyncDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Confirm Daily Attendance Sync
            </DialogTitle>
            <DialogDescription className="space-y-2">
              <p>
                Are you sure you want to send today's attendance data?
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-yellow-800">
                    <p className="font-medium">Important Notice:</p>
                    <p>
                      After syncing, attendance data will be finalized (if any) using the following logic:
                    </p>
                    <ul className="mt-1 list-disc list-inside ml-2 space-y-1">
                      <li><strong>First checkin:</strong> First entry of the day</li>
                      <li><strong>Last checkout:</strong> Last exit of the day</li>
                    </ul>
                    <p className="mt-2">
                      Data will be sent to the external system and cannot be undone.
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
              Cancel
            </Button>
            <Button
              onClick={handleDailySyncConfirm}
              disabled={isDailySyncing}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isDailySyncing ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Confirm Send
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

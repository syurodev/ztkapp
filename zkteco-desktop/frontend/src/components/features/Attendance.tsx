import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
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
import { attendanceAPI } from "@/lib/api";
import { AlertCircle, Clock } from "lucide-react";
import { useEffect, useState } from "react";

interface AttendanceRecord {
  user_id: string;
  timestamp: string;
  status: number;
  punch: number;
  uid: number;
}

const STATUS_MAP: { [key: number]: string } = {
  0: "Check-in",
  1: "Check-out",
  2: "Break-out",
  3: "Break-in",
  4: "Overtime-in",
  5: "Overtime-out",
};

const PAGE_SIZE = 20;
const CACHE_KEY = "attendance_cache";
const CACHE_TS_KEY = "attendance_cache_at";
const CACHE_TTL_MS = 10 * 60 * 1000; // 2 minutes

export function Attendance() {
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    // Load from cache first for quick display
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const parsed: AttendanceRecord[] = JSON.parse(cached);
        setAttendance(parsed);
      }
    } catch (_) {
      // ignore cache parse errors
    }

    // Decide whether to fetch based on TTL
    const cachedAt = Number(localStorage.getItem(CACHE_TS_KEY) || 0);
    const now = Date.now();
    const isStale = now - cachedAt > CACHE_TTL_MS;

    if (isStale) {
      loadAttendance();
    }
  }, []);

  const loadAttendance = async (force = false) => {
    setIsLoading(true);
    setError(null);
    try {
      if (!force) {
        const cachedAt = Number(localStorage.getItem(CACHE_TS_KEY) || 0);
        const now = Date.now();
        if (now - cachedAt <= CACHE_TTL_MS) {
          setIsLoading(false);
          return;
        }
      }
      const response = await attendanceAPI.getAttendance();
      const data: AttendanceRecord[] = (response.data || []).slice().reverse();
      setAttendance(data);
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(data));
        localStorage.setItem(CACHE_TS_KEY, String(Date.now()));
      } catch (_) {
        // storage might be unavailable; ignore
      }
    } catch (err) {
      setError("Failed to load attendance records.");
      console.error("Error loading attendance:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const totalPages = Math.ceil(attendance.length / PAGE_SIZE);
  const paginatedAttendance = attendance.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-6 w-6" />
            Attendance Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between pb-4">
            <p className="text-sm text-muted-foreground">
              Uses cached data, auto-refresh every{" "}
              {Math.round(CACHE_TTL_MS / 1000)}s
            </p>
            <button
              onClick={() => loadAttendance(true)}
              className="text-sm px-3 py-1 rounded border hover:bg-accent"
              disabled={isLoading}
            >
              {isLoading ? "Refreshing..." : "Refresh now"}
            </button>
          </div>
          {isLoading ? (
            <p>Loading attendance...</p>
          ) : error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>User ID</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Punch</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedAttendance.map((record, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        {(currentPage - 1) * PAGE_SIZE + index + 1}
                      </TableCell>
                      <TableCell>{record.user_id}</TableCell>
                      <TableCell>{record.timestamp}</TableCell>
                      <TableCell>
                        {STATUS_MAP[record.status] || "Unknown"}
                      </TableCell>
                      <TableCell>{record.punch}</TableCell>
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
                            setCurrentPage((prev) => Math.max(prev - 1, 1));
                          }}
                          aria-disabled={currentPage === 1}
                          className={
                            currentPage === 1
                              ? "pointer-events-none opacity-50"
                              : undefined
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <span className="text-sm font-medium">
                          Page {currentPage} of {totalPages}
                        </span>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext
                          onClick={(e) => {
                            e.preventDefault();
                            setCurrentPage((prev) =>
                              Math.min(prev + 1, totalPages),
                            );
                          }}
                          aria-disabled={currentPage === totalPages}
                          className={
                            currentPage === totalPages
                              ? "pointer-events-none opacity-50"
                              : undefined
                          }
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}

              {totalPages > 1 && (
                <div className="flex items-center justify-center pt-4">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          onClick={(e) => {
                            e.preventDefault();
                            setCurrentPage((prev) => Math.max(prev - 1, 1));
                          }}
                          aria-disabled={currentPage === 1}
                          className={
                            currentPage === 1
                              ? "pointer-events-none opacity-50"
                              : undefined
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink href="#">
                          {currentPage - 1}
                        </PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink href="#" isActive>
                          {currentPage}
                        </PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink href="#">
                          {currentPage + 1}
                        </PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext
                          onClick={(e) => {
                            e.preventDefault();
                            setCurrentPage((prev) =>
                              Math.min(prev + 1, totalPages),
                            );
                          }}
                          aria-disabled={currentPage === totalPages}
                          className={
                            currentPage === totalPages
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
    </div>
  );
}

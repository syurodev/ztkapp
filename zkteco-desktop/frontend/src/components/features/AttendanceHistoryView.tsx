import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { buildAvatarUrl, getResourceDomain } from "@/lib/utils";
import { ATTENDANCE_METHOD_MAP, PUNCH_ACTION_MAP } from "@/types/constant";
import { format } from "date-fns";
import {
  ArrowLeftFromLine,
  ArrowRightToLine,
  Calendar as CalendarIcon,
  Fingerprint,
  History,
  IdCard,
  Loader2,
  RefreshCw,
  User,
} from "lucide-react";
import { useEffect, useState } from "react";

interface AttendanceRecord {
  user_id: string;
  name: string;
  full_name: string;
  avatar_url?: string | null;
  timestamp: string;
  method: number;
  action: number;
  id: number;
  is_synced: boolean;
}

interface AttendanceHistoryViewProps {
  data: AttendanceRecord[];
  selectedDate: Date | null;
  onDateChange: (date: Date | null) => void;
  onRefresh: () => void;
  isLoading: boolean;
  error: string | null;
}

export function AttendanceHistoryView({
  data,
  selectedDate,
  onDateChange,
  onRefresh,
  isLoading,
  error,
}: AttendanceHistoryViewProps) {
  const [actionFilter, setActionFilter] = useState<"all" | 0 | 1>("all");
  const [resourceDomain, setResourceDomain] = useState<string>("");
  const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);

  // Load resource domain on mount
  useEffect(() => {
    getResourceDomain().then(setResourceDomain);
  }, []);

  // Apply action filter to data
  const filteredData =
    actionFilter === "all"
      ? data
      : data.filter((r) => r.action === actionFilter);

  return (
    <div className="space-y-4">
      {/* Header with Date Picker */}
      <div className="flex items-center gap-4 flex-wrap">
        <Popover open={isDatePickerOpen} onOpenChange={setIsDatePickerOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="justify-start gap-2">
              <CalendarIcon className="h-4 w-4" />
              {selectedDate ? format(selectedDate, "PPP") : "Tất cả ngày"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="single"
              selected={selectedDate ?? undefined}
              onSelect={(date) => {
                onDateChange(date ?? null);
                setIsDatePickerOpen(false);
              }}
              initialFocus
            />
          </PopoverContent>
        </Popover>
        {/* <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onDateChange(new Date());
            setIsDatePickerOpen(false);
          }}
        >
          Today
        </Button> */}
        {/* <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onDateChange(null);
            setIsDatePickerOpen(false);
          }}
        >
          Tất cả ngày
        </Button> */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </Button>
        <Badge variant="secondary" className="ml-auto">
          {filteredData.length} bản ghi
        </Badge>
      </div>

      {/* Action Filter Buttons */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Lọc:</span>
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
            Vào ca
          </Button>
          <Button
            variant={actionFilter === 1 ? "default" : "outline"}
            size="sm"
            onClick={() => setActionFilter(1)}
          >
            Ra ca
          </Button>
        </div>
      </div>

      {/* Content */}
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="h-12 w-12 text-muted-foreground mx-auto mb-4 animate-spin" />
            <p className="text-muted-foreground">
              Đang tải dữ liệu chấm công...
            </p>
          </div>
        </div>
      ) : filteredData.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <History className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              {data.length === 0
                ? `Không có dữ liệu chấm công cho ${
                    selectedDate
                      ? format(selectedDate, "MMMM d, yyyy")
                      : "tất cả ngày"
                  }`
                : "Không có dữ liệu phù hợp với bộ lọc đã chọn"}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4 max-h-[600px] overflow-y-auto">
          {filteredData.map((record, index) => {
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
              <div
                key={`${record.id}-${index}`}
                className="flex items-center gap-4 p-4 rounded-lg border bg-card hover:bg-accent/50 transition-all"
              >
                {/* Avatar */}
                <Avatar className="h-12 w-12">
                  <AvatarImage
                    src={buildAvatarUrl(record.avatar_url, resourceDomain)}
                    alt={record.full_name ?? record.name}
                  />
                  <AvatarFallback>
                    {record.name ? (
                      record.name
                        .split(" ")
                        .map((n) => n[0])
                        .join("")
                        .toUpperCase()
                        .slice(0, 2)
                    ) : (
                      <User className="h-6 w-6" />
                    )}
                  </AvatarFallback>
                </Avatar>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate text-base">
                    {record.full_name ?? record.name}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>
                      {format(new Date(record.timestamp), "yyyy-MM-dd HH:mm")}
                    </span>
                    {methodIcon && (
                      <Badge variant={"outline"}>
                        {methodIcon}
                        {ATTENDANCE_METHOD_MAP[record.method] ||
                          "Không xác định"}
                      </Badge>
                    )}
                    {record.is_synced && (
                      <Badge variant={"outline"}>Đã đồng bộ</Badge>
                    )}
                  </div>
                </div>

                {/* Action Badge */}
                <div className="flex-shrink-0">
                  <Badge
                    variant={"outline"}
                    className={`gap-1 ${actionColor} w-[100px]`}
                  >
                    {actionIcon}
                    {PUNCH_ACTION_MAP[record.action] || "Không xác định"}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

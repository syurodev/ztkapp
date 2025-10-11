import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { LogEntry } from "@/hooks/useBackendHealth";
import { AlertTriangle, FileText, Info, X } from "lucide-react";
import { format } from "date-fns";

interface ErrorLogViewerProps {
  logs: LogEntry[];
  errorLogs: LogEntry[];
  onClearLogs: () => void;
  onRefreshLogs: () => void;
  trigger?: React.ReactNode;
}

const getLevelIcon = (level: string) => {
  switch (level.toLowerCase()) {
    case "error":
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case "info":
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
};

const getLevelColor = (level: string) => {
  switch (level.toLowerCase()) {
    case "error":
      return "bg-red-100 text-red-800 border-red-200";
    case "warning":
      return "bg-yellow-100 text-yellow-800 border-yellow-200";
    case "info":
    default:
      return "bg-blue-100 text-blue-800 border-blue-200";
  }
};

export function ErrorLogViewer({ 
  logs, 
  errorLogs, 
  onClearLogs, 
  onRefreshLogs,
  trigger
}: ErrorLogViewerProps) {
  const defaultTrigger = (
    <Button variant="outline" size="sm">
      <FileText className="h-4 w-4 mr-2" />
      Xem log
      {errorLogs.length > 0 && (
        <Badge variant="destructive" className="ml-2">
          {errorLogs.length}
        </Badge>
      )}
    </Button>
  );

  return (
    <Dialog>
      <DialogTrigger asChild>
        {trigger || defaultTrigger}
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader className="flex flex-row items-center justify-between">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Log backend
            {errorLogs.length > 0 && (
              <Badge variant="destructive">
                {errorLogs.length} lỗi
              </Badge>
            )}
          </DialogTitle>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onRefreshLogs}>
              Làm mới
            </Button>
            <Button variant="outline" size="sm" onClick={onClearLogs}>
              <X className="h-4 w-4 mr-1" />
              Xóa
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0">
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-muted-foreground">
              <div className="text-center">
                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>Không có log nào</p>
                <p className="text-sm">Log backend sẽ hiển thị ở đây khi có dữ liệu</p>
              </div>
            </div>
          ) : (
            <ScrollArea className="h-full border rounded-md">
              <div className="p-4 space-y-3">
                {logs.map((log, index) => (
                  <div
                    key={index}
                    className={`p-3 rounded-lg border-l-4 ${
                      log.level.toLowerCase() === "error"
                        ? "border-l-red-500 bg-red-50"
                        : log.level.toLowerCase() === "warning"
                        ? "border-l-yellow-500 bg-yellow-50"
                        : "border-l-blue-500 bg-blue-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 flex-1 min-w-0">
                        {getLevelIcon(log.level)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge 
                              variant="outline" 
                              className={`text-xs ${getLevelColor(log.level)}`}
                            >
                              {log.level.toUpperCase()}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              {log.source}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {format(new Date(log.timestamp), "HH:mm:ss.SSS")}
                            </span>
                          </div>
                          <div className="text-sm font-mono break-all whitespace-pre-wrap">
                            {log.message}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        {errorLogs.length > 0 && (
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Lỗi gần đây ({errorLogs.length})
            </h4>
            <ScrollArea className="h-24 border rounded-md bg-red-50">
              <div className="p-2 space-y-1">
                {errorLogs.slice(-3).map((log, index) => (
                  <div key={index} className="text-xs font-mono text-red-800">
                    <span className="text-red-600">
                      {format(new Date(log.timestamp), "HH:mm:ss")}:
                    </span>{" "}
                    {log.message}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
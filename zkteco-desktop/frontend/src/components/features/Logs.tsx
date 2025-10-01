import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { open } from "@tauri-apps/plugin-shell";
import {
  AlertCircle,
  AlertTriangle,
  Download,
  FileText,
  FolderOpen,
  Info,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

interface FileLogEntry {
  line_number: number;
  timestamp: string;
  level: string;
  module: string;
  message: string;
}

export function Logs() {
  const [logs, setLogs] = useState<FileLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [logFilePath, setLogFilePath] = useState<string>("");

  const fetchLogPath = async () => {
    try {
      const path = await invoke<string>("get_log_file_path_command");
      setLogFilePath(path);
    } catch (error) {
      console.error("Failed to get log file path:", error);
    }
  };

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const result = await invoke<FileLogEntry[]>("read_log_file", {
        lines: 500,
      });
      setLogs(result);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
      toast.error("Failed to fetch logs");
    } finally {
      setLoading(false);
    }
  };

  const clearLogs = async () => {
    try {
      await invoke("clear_log_file");
      setLogs([]);
      toast.success("Log file cleared successfully");
    } catch (error) {
      console.error("Failed to clear logs:", error);
      toast.error("Failed to clear logs");
    }
  };

  const exportLogs = async () => {
    try {
      // Open save dialog
      const filePath = await save({
        defaultPath: `zkteco-logs-${
          new Date().toISOString().split("T")[0]
        }.log`,
        filters: [
          {
            name: "Log Files",
            extensions: ["log", "txt"],
          },
        ],
      });

      if (!filePath) {
        return; // User cancelled
      }

      // Export log file
      await invoke("export_log_file", { destination: filePath });
      toast.success("Log file exported successfully");
    } catch (error) {
      console.error("Failed to export logs:", error);
      toast.error("Failed to export logs");
    }
  };

  const openLogFolder = async () => {
    if (!logFilePath) return;

    try {
      // Get folder path by removing filename
      const folderPath = logFilePath.substring(0, logFilePath.lastIndexOf("/"));
      await open(folderPath);
    } catch (error) {
      console.error("Failed to open log folder:", error);
      toast.error("Failed to open log folder");
    }
  };

  useEffect(() => {
    fetchLogPath();
    fetchLogs();
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs =
    filterLevel === "all"
      ? logs
      : logs.filter((log) =>
          log.level.toLowerCase().includes(filterLevel.toLowerCase())
        );

  const getLevelIcon = (level: string) => {
    const levelLower = level.toLowerCase();
    if (levelLower.includes("error")) {
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    } else if (levelLower.includes("warning") || levelLower.includes("warn")) {
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    } else {
      return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getLevelBadgeVariant = (
    level: string
  ): "default" | "destructive" | "secondary" => {
    const levelLower = level.toLowerCase();
    if (levelLower.includes("error")) {
      return "destructive";
    } else if (levelLower.includes("warning") || levelLower.includes("warn")) {
      return "default";
    } else {
      return "secondary";
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Backend Log File
                <Badge variant="outline">{filteredLogs.length} entries</Badge>
              </CardTitle>
              {logFilePath && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground font-mono">
                    {logFilePath}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={openLogFolder}
                    className="h-6 px-2"
                  >
                    <FolderOpen className="h-3 w-3" />
                  </Button>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              {/* Filter buttons */}
              <div className="flex gap-1">
                <Button
                  variant={filterLevel === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterLevel("all")}
                >
                  All
                </Button>
                <Button
                  variant={filterLevel === "info" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterLevel("info")}
                >
                  Info
                </Button>
                <Button
                  variant={filterLevel === "warning" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterLevel("warning")}
                >
                  Warning
                </Button>
                <Button
                  variant={filterLevel === "error" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterLevel("error")}
                >
                  Error
                </Button>
              </div>

              {/* Action buttons */}
              <Button
                variant="outline"
                size="sm"
                onClick={fetchLogs}
                disabled={loading}
                title="Refresh logs"
              >
                <RefreshCw
                  className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={exportLogs}
                disabled={logs.length === 0}
                title="Export logs"
              >
                <Download className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clearLogs}
                disabled={logs.length === 0}
                title="Clear logs"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[calc(100vh-245px)]">
            {filteredLogs.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                No logs available
              </div>
            ) : (
              <div className="space-y-2">
                {filteredLogs.map((log) => (
                  <div
                    key={log.line_number}
                    className="p-3 rounded-lg border bg-card hover:bg-accent/5 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{getLevelIcon(log.level)}</div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant={getLevelBadgeVariant(log.level)}>
                            {log.level}
                          </Badge>
                          <Badge
                            variant="outline"
                            className="font-mono text-xs"
                          >
                            {log.module}
                          </Badge>
                          <Badge variant="secondary" className="text-xs">
                            Line {log.line_number}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {log.timestamp}
                          </span>
                        </div>
                        <pre className="text-sm whitespace-pre-wrap break-words font-mono">
                          {log.message}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

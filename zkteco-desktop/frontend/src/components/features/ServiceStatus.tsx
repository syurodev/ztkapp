import { ErrorLogViewer } from "@/components/shared/ErrorLogViewer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import {
  Activity,
  AlertTriangle,
  Clock,
  Copy,
  Globe,
  HardDrive,
  Loader2,
  Play,
  RotateCcw,
  Server,
  Square,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export function ServiceStatus() {
  const {
    isBackendRunning,
    isStarting,
    error,
    metrics,
    logs,
    errorLogs,
    startBackend,
    stopBackend,
    restartBackend,
    refreshLogs,
    clearLogs,
  } = useBackendHealth();

  const [autoStart, setAutoStart] = useState(false);

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const handleServiceAction = async (action: "start" | "stop" | "restart") => {
    try {
      switch (action) {
        case "start":
          await startBackend();
          break;
        case "stop":
          await stopBackend();
          break;
        case "restart":
          await restartBackend();
          break;
      }
    } catch (error) {
      console.error(`Failed to ${action} backend:`, error);
    }
  };

  const getStatusColor = () => {
    if (isStarting) {
      return "text-blue-600 bg-blue-100 dark:bg-blue-900/20";
    }

    if (error) {
      return "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20";
    }

    if (isBackendRunning) {
      return "text-green-600 bg-green-100 dark:bg-green-900/20";
    }

    return "text-red-600 bg-red-100 dark:bg-red-900/20";
  };

  console.log("isBackendRunning", isBackendRunning);

  const getStatusText = () => {
    if (isStarting) return "ĐANG KHỞI ĐỘNG";
    if (error) return "LỖI";
    return isBackendRunning ? "ĐANG CHẠY" : "ĐÃ DỪNG";
  };

  const handleCopyIP = () => {
    if (metrics?.publicIp && metrics.publicIp !== "N/A") {
      navigator.clipboard.writeText(metrics.publicIp);
      toast.success("Đã sao chép IP vào clipboard");
    } else {
      toast.error("Không có IP để sao chép");
    }
  };

  // Auto-start logic (if enabled)
  useEffect(() => {
    if (autoStart && !isBackendRunning && !isStarting && !error) {
      // Small delay to prevent rapid startup attempts
      const timer = setTimeout(() => {
        startBackend();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [autoStart, isBackendRunning, isStarting, error, startBackend]);

  return (
    <div className="space-y-6">
      {/* Service Status Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                Trạng thái dịch vụ ZKTeco
              </CardTitle>
              <CardDescription>
                Quản lý và giám sát dịch vụ API backend
              </CardDescription>
            </div>
            <Badge className={getStatusColor()}>
              {isStarting && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
              {getStatusText()}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Service Controls */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              onClick={() => handleServiceAction("start")}
              disabled={isBackendRunning || isStarting}
              size="sm"
              className="flex items-center gap-2"
            >
              {isStarting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Khởi chạy
            </Button>
            <Button
              onClick={() => handleServiceAction("stop")}
              disabled={!isBackendRunning || isStarting}
              variant="destructive"
              size="sm"
              className="flex items-center gap-2"
            >
              <Square className="h-4 w-4" />
              Dừng
            </Button>
            <Button
              onClick={() => handleServiceAction("restart")}
              disabled={!isBackendRunning || isStarting}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              {isStarting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              Khởi động lại
            </Button>
          </div>

          {/* Error Alert with Logs */}
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle className="flex items-center justify-between">
                <span>Lỗi dịch vụ backend</span>
                <ErrorLogViewer
                  logs={logs}
                  errorLogs={errorLogs}
                  onClearLogs={clearLogs}
                  onRefreshLogs={refreshLogs}
                  trigger={
                    <Button variant="outline" size="sm" className="ml-2">
                      Xem chi tiết
                      {errorLogs.length > 0 && (
                        <Badge variant="destructive" className="ml-1 text-xs">
                          {errorLogs.length}
                        </Badge>
                      )}
                    </Button>
                  }
                />
              </AlertTitle>
              <AlertDescription className="mt-2">
                <div className="space-y-2">
                  <p>{error}</p>
                  {errorLogs.length > 0 && (
                    <div className="bg-red-900/10 border border-red-200 rounded p-2">
                      <p className="text-sm font-medium text-red-800 mb-1">
                        Lỗi gần nhất:
                      </p>
                      <code className="text-xs text-red-700 block whitespace-pre-wrap">
                        {errorLogs[errorLogs.length - 1]?.message}
                      </code>
                    </div>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Auto-start Setting */}
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Tự động khởi chạy khi bật máy</p>
              <p className="text-sm text-muted-foreground">
                Tự động khởi động dịch vụ khi hệ thống được bật
              </p>
            </div>
            <Switch checked={autoStart} onCheckedChange={setAutoStart} />
          </div>
        </CardContent>
      </Card>

      {/* Service Metrics - Row 1: Network Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IP Local</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-2">
              <div className="text-2xl font-bold truncate">
                {metrics?.localIp || "N/A"}
              </div>
              {metrics?.localIp &&
                metrics.localIp !== "N/A" &&
                metrics.localIp !== "127.0.0.1" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (metrics?.localIp) {
                        navigator.clipboard.writeText(metrics.localIp);
                        toast.success("Đã sao chép IP Local vào clipboard");
                      }
                    }}
                    className="h-8 w-8 p-0 flex-shrink-0"
                    title="Sao chép IP Local"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                )}
            </div>
            <p className="text-xs text-muted-foreground">IP trong mạng LAN</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IP Public</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-2">
              <div className="text-2xl font-bold truncate">
                {metrics?.publicIp || "N/A"}
              </div>
              {metrics?.publicIp && metrics.publicIp !== "N/A" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyIP}
                  className="h-8 w-8 p-0 flex-shrink-0"
                  title="Sao chép IP Public"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Địa chỉ IP công khai
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cổng</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">:{metrics?.port || 57575}</div>
            <p className="text-xs text-muted-foreground">Cổng đang lắng nghe</p>
          </CardContent>
        </Card>
      </div>

      {/* Service Metrics - Row 2: Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Thời gian hoạt động
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics ? formatUptime(metrics.uptime) : "0h 0m"}
            </div>
            <p className="text-xs text-muted-foreground">
              Kể từ lần khởi động lại gần nhất
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Bộ nhớ đang dùng
            </CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics ? `${metrics.memoryUsage.toFixed(1)} MB` : "0.0 MB"}
            </div>
            <p className="text-xs text-muted-foreground">
              Dung lượng RAM tiêu thụ
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tải CPU</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics ? `${metrics.cpuUsage.toFixed(1)}%` : "0.0%"}
            </div>
            <p className="text-xs text-muted-foreground">Mức độ sử dụng CPU</p>
          </CardContent>
        </Card>
      </div>

      {/* Status Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Lỗi dịch vụ</AlertTitle>
          <AlertDescription>
            {error}. Vui lòng kiểm tra log hoặc thử khởi động lại dịch vụ.
          </AlertDescription>
        </Alert>
      )}

      {!isBackendRunning && !isStarting && !error && (
        <Alert>
          <AlertTitle>Dịch vụ đã dừng</AlertTitle>
          <AlertDescription>
            Dịch vụ ZKTeco hiện chưa chạy. Bấm "Khởi chạy" để bắt đầu dịch vụ.
          </AlertDescription>
        </Alert>
      )}

      {isStarting && (
        <Alert>
          <AlertTitle>Đang khởi động</AlertTitle>
          <AlertDescription>
            Dịch vụ ZKTeco đang khởi động. Vui lòng chờ trong giây lát...
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

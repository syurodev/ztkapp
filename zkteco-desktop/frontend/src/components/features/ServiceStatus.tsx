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
import {
  Activity,
  Clock,
  HardDrive,
  Play,
  RotateCcw,
  Server,
  Square,
} from "lucide-react";
import { useEffect, useState } from "react";

interface ServiceMetrics {
  status: "running" | "stopped" | "error";
  uptime: number;
  memoryUsage: number;
  cpuUsage: number;
  pid?: number;
  port: number;
  lastRestart?: Date;
}

export function ServiceStatus() {
  const [metrics, setMetrics] = useState<ServiceMetrics>({
    status: "running",
    uptime: 3600, // seconds
    memoryUsage: 45.2, // MB
    cpuUsage: 2.1, // %
    pid: 1234,
    port: 5001,
    lastRestart: new Date(),
  });

  const [isLoading, setIsLoading] = useState(false);
  const [autoStart, setAutoStart] = useState(true);

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const handleServiceAction = async (action: "start" | "stop" | "restart") => {
    setIsLoading(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 2000));

      if (action === "start") {
        setMetrics((prev) => ({ ...prev, status: "running" }));
      } else if (action === "stop") {
        setMetrics((prev) => ({ ...prev, status: "stopped" }));
      } else if (action === "restart") {
        setMetrics((prev) => ({
          ...prev,
          status: "running",
          lastRestart: new Date(),
          uptime: 0,
        }));
      }
    } catch (error) {
      setMetrics((prev) => ({ ...prev, status: "error" }));
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = () => {
    switch (metrics.status) {
      case "running":
        return "text-green-600 bg-green-100 dark:bg-green-900/20";
      case "stopped":
        return "text-red-600 bg-red-100 dark:bg-red-900/20";
      case "error":
        return "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20";
    }
  };

  // Simulate real-time updates
  useEffect(() => {
    if (metrics.status === "running") {
      const interval = setInterval(() => {
        setMetrics((prev) => ({
          ...prev,
          uptime: prev.uptime + 1,
          memoryUsage: 40 + Math.random() * 10,
          cpuUsage: 1 + Math.random() * 3,
        }));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [metrics.status]);

  return (
    <div className="space-y-6">
      {/* Service Status Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                ZKTeco Service Status
              </CardTitle>
              <CardDescription>
                Backend API service management and monitoring
              </CardDescription>
            </div>
            <Badge className={getStatusColor()}>
              {metrics.status.toUpperCase()}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Service Controls */}
          <div className="flex items-center gap-2">
            <Button
              onClick={() => handleServiceAction("start")}
              disabled={metrics.status === "running" || isLoading}
              size="sm"
              className="flex items-center gap-2"
            >
              <Play className="h-4 w-4" />
              Start
            </Button>
            <Button
              onClick={() => handleServiceAction("stop")}
              disabled={metrics.status === "stopped" || isLoading}
              variant="destructive"
              size="sm"
              className="flex items-center gap-2"
            >
              <Square className="h-4 w-4" />
              Stop
            </Button>
            <Button
              onClick={() => handleServiceAction("restart")}
              disabled={metrics.status === "stopped" || isLoading}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              <RotateCcw className="h-4 w-4" />
              Restart
            </Button>
          </div>

          {/* Auto-start Setting */}
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Auto-start on Boot</p>
              <p className="text-sm text-muted-foreground">
                Automatically start service when system boots
              </p>
            </div>
            <Switch checked={autoStart} onCheckedChange={setAutoStart} />
          </div>
        </CardContent>
      </Card>

      {/* Service Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Uptime</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatUptime(metrics.uptime)}
            </div>
            <p className="text-xs text-muted-foreground">Since last restart</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics.memoryUsage.toFixed(1)} MB
            </div>
            <p className="text-xs text-muted-foreground">RAM consumption</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics.cpuUsage.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">Processor load</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Port</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">:{metrics.port}</div>
            <p className="text-xs text-muted-foreground">Listening port</p>
          </CardContent>
        </Card>
      </div>

      {/* Status Alerts */}
      {metrics.status === "error" && (
        <Alert variant="destructive">
          <AlertTitle>Service Error</AlertTitle>
          <AlertDescription>
            The ZKTeco service has encountered an error. Please check the logs
            for more information.
          </AlertDescription>
        </Alert>
      )}

      {metrics.status === "stopped" && (
        <Alert>
          <AlertTitle>Service Stopped</AlertTitle>
          <AlertDescription>
            The ZKTeco service is currently not running. Click "Start" to begin
            the service.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

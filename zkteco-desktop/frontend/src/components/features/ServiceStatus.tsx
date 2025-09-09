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
  Clock,
  HardDrive,
  Play,
  RotateCcw,
  Server,
  Square,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";

export function ServiceStatus() {
  const { 
    isBackendRunning, 
    isStarting, 
    error, 
    metrics, 
    startBackend, 
    stopBackend, 
    restartBackend 
  } = useBackendHealth();
  
  const [autoStart, setAutoStart] = useState(true);

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

  const getStatusText = () => {
    if (isStarting) return "STARTING";
    if (error) return "ERROR";
    return isBackendRunning ? "RUNNING" : "STOPPED";
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
                ZKTeco Service Status
              </CardTitle>
              <CardDescription>
                Backend API service management and monitoring
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
          <div className="flex items-center gap-2">
            <Button
              onClick={() => handleServiceAction("start")}
              disabled={isBackendRunning || isStarting}
              size="sm"
              className="flex items-center gap-2"
            >
              {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Start
            </Button>
            <Button
              onClick={() => handleServiceAction("stop")}
              disabled={!isBackendRunning || isStarting}
              variant="destructive"
              size="sm"
              className="flex items-center gap-2"
            >
              <Square className="h-4 w-4" />
              Stop
            </Button>
            <Button
              onClick={() => handleServiceAction("restart")}
              disabled={!isBackendRunning || isStarting}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
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
              {metrics ? formatUptime(metrics.uptime) : "0h 0m"}
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
              {metrics ? `${metrics.memoryUsage.toFixed(1)} MB` : "0.0 MB"}
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
              {metrics ? `${metrics.cpuUsage.toFixed(1)}%` : "0.0%"}
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
            <div className="text-2xl font-bold">:{metrics?.port || 5001}</div>
            <p className="text-xs text-muted-foreground">Listening port</p>
          </CardContent>
        </Card>
      </div>

      {/* Status Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Service Error</AlertTitle>
          <AlertDescription>
            {error}. Please check the logs or try restarting the service.
          </AlertDescription>
        </Alert>
      )}

      {!isBackendRunning && !isStarting && !error && (
        <Alert>
          <AlertTitle>Service Stopped</AlertTitle>
          <AlertDescription>
            The ZKTeco service is currently not running. Click "Start" to begin
            the service.
          </AlertDescription>
        </Alert>
      )}

      {isStarting && (
        <Alert>
          <AlertTitle>Service Starting</AlertTitle>
          <AlertDescription>
            The ZKTeco service is starting up. Please wait a moment...
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

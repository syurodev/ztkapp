import { healthCheck, serviceAPI } from "@/lib/api";
import { invoke } from "@tauri-apps/api/core";
import { useCallback, useEffect, useRef, useState } from "react";

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  source: string;
}

export interface ServiceMetrics {
  status: "running" | "stopped" | "error" | "starting";
  uptime: number;
  memoryUsage: number;
  cpuUsage: number;
  pid?: number;
  port: number;
  lastRestart?: Date;
}

interface BackendHealthHook {
  isBackendRunning: boolean;
  isStarting: boolean;
  error: string | null;
  metrics: ServiceMetrics | null;
  logs: LogEntry[];
  errorLogs: LogEntry[];
  startBackend: () => Promise<boolean>;
  stopBackend: () => Promise<boolean>;
  restartBackend: () => Promise<boolean>;
  checkHealth: () => Promise<boolean>;
  refreshMetrics: () => Promise<void>;
  refreshLogs: () => Promise<void>;
  clearLogs: () => Promise<void>;
}

const DEFAULT_METRICS: ServiceMetrics = {
  status: "stopped",
  uptime: 0,
  memoryUsage: 0,
  cpuUsage: 0,
  port: 5001,
};

export const useBackendHealth = (): BackendHealthHook => {
  const [isBackendRunning, setIsBackendRunning] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<ServiceMetrics | null>(
    DEFAULT_METRICS,
  );
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [errorLogs, setErrorLogs] = useState<LogEntry[]>([]);

  const healthCheckInterval = useRef<NodeJS.Timeout | null>(null);
  const metricsInterval = useRef<NodeJS.Timeout | null>(null);

  const checkHealth = useCallback(async (): Promise<boolean> => {
    try {
      const healthy = await healthCheck();
      setIsBackendRunning(healthy);
      setError(null);

      // Update metrics status based on health check
      setMetrics((prev) =>
        prev
          ? { ...prev, status: healthy ? "running" : "stopped" }
          : DEFAULT_METRICS,
      );

      return healthy;
    } catch (err) {
      console.error("Health check failed:", err);
      setError(err instanceof Error ? err.message : "Health check failed");
      setIsBackendRunning(false);
      setMetrics((prev) =>
        prev
          ? { ...prev, status: "error" }
          : { ...DEFAULT_METRICS, status: "error" },
      );
      return false;
    }
  }, []);

  const refreshMetrics = useCallback(async (): Promise<void> => {
    try {
      if (isBackendRunning) {
        const metricsData = await serviceAPI.getStatus();
        setMetrics({
          status: "running",
          uptime: metricsData.uptime || 0,
          memoryUsage: metricsData.memory_usage || 0,
          cpuUsage: metricsData.cpu_percent || 0,
          pid: metricsData.pid,
          port: 5001,
          lastRestart: new Date(),
        });
      }
    } catch (err) {
      console.error("Failed to refresh metrics:", err);
      // Don't set error state for metrics refresh failures
      // as the backend might be healthy but metrics endpoint might fail
    }
  }, [isBackendRunning]);

  const refreshLogs = useCallback(async (): Promise<void> => {
    try {
      const allLogs = await invoke<LogEntry[]>("get_backend_logs");
      setLogs(allLogs);
      
      const errors = await invoke<LogEntry[]>("get_backend_error_logs");
      setErrorLogs(errors);
    } catch (err) {
      console.error("Failed to refresh logs:", err);
    }
  }, []);

  const clearLogs = useCallback(async (): Promise<void> => {
    try {
      await invoke<string>("clear_backend_logs");
      setLogs([]);
      setErrorLogs([]);
    } catch (err) {
      console.error("Failed to clear logs:", err);
    }
  }, []);

  const startBackend = useCallback(async (): Promise<boolean> => {
    setIsStarting(true);
    setError(null);

    try {
      // First check if already running via Tauri
      const processRunning = await invoke<boolean>("is_backend_running");
      if (processRunning) {
        // Double-check with HTTP health check
        const healthy = await checkHealth();
        if (healthy) {
          setIsStarting(false);
          return true;
        }
      }

      // Start backend via Tauri command
      console.log("Starting backend via Tauri...");
      const result = await invoke<string>("start_backend");
      console.log("Backend start result:", result);

      // Check if start result indicates failure
      if (result && result.includes("Failed to start backend")) {
        setError("Backend failed to start: " + result);
        setIsBackendRunning(false);
        setIsStarting(false);
        return false;
      }

      // Wait longer for backend to initialize
      console.log("Waiting for backend to initialize...");
      await new Promise((resolve) => setTimeout(resolve, 5000));

      // Verify backend is running with health check (with retries)
      console.log("Verifying backend health...");
      const healthy = await checkHealth();

      if (healthy) {
        console.log("Backend started successfully");
        await refreshMetrics();
        await refreshLogs(); // Refresh logs after successful start
        setIsStarting(false);
        return true;
      } else {
        // Refresh logs to get error details
        await refreshLogs();
        
        // Get recent error logs to show detailed error message
        try {
          const errors = await invoke<LogEntry[]>("get_backend_error_logs");
          if (errors.length > 0) {
            const recentError = errors[errors.length - 1];
            setError(`Backend startup failed: ${recentError.message}`);
          } else {
            // Double-check if process is still running
            const stillRunning = await invoke<boolean>("is_backend_running");
            if (!stillRunning) {
              setError("Backend process terminated unexpectedly");
            } else {
              setError("Backend started but health check failed");
            }
          }
        } catch (logErr) {
          console.error("Failed to get error logs:", logErr);
          setError("Backend startup failed - unable to retrieve error details");
        }
        
        setIsStarting(false);
        return false;
      }
    } catch (err) {
      console.error("Failed to start backend:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to start backend";
      setError(errorMessage);
      setIsBackendRunning(false);
      setIsStarting(false);
      return false;
    }
  }, [checkHealth, refreshMetrics, refreshLogs]);

  const stopBackend = useCallback(async (): Promise<boolean> => {
    setError(null);

    try {
      // Stop backend via Tauri command
      console.log("Stopping backend via Tauri...");
      const result = await invoke<string>("stop_backend");
      console.log("Backend stop result:", result);

      // Update state immediately
      setIsBackendRunning(false);
      setMetrics({ ...DEFAULT_METRICS, status: "stopped" });

      return true;
    } catch (err) {
      console.error("Failed to stop backend:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to stop backend";
      setError(errorMessage);
      return false;
    }
  }, []);

  const restartBackend = useCallback(async (): Promise<boolean> => {
    setIsStarting(true);
    setError(null);

    try {
      console.log("Restarting backend via Tauri...");
      const result = await invoke<string>("restart_backend");
      console.log("Backend restart result:", result);

      // Wait a moment for backend to initialize
      await new Promise((resolve) => setTimeout(resolve, 3000));

      // Verify backend is running
      const healthy = await checkHealth();

      if (healthy) {
        console.log("Backend restarted successfully");
        await refreshMetrics();
        setMetrics((prev) =>
          prev
            ? { ...prev, lastRestart: new Date(), uptime: 0 }
            : DEFAULT_METRICS,
        );
        setIsStarting(false);
        return true;
      } else {
        setError("Backend restart failed - health check unsuccessful");
        setIsStarting(false);
        return false;
      }
    } catch (err) {
      console.error("Failed to restart backend:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to restart backend";
      setError(errorMessage);
      setIsBackendRunning(false);
      setIsStarting(false);
      return false;
    }
  }, [checkHealth, refreshMetrics]);

  // Initialize health checking on mount
  useEffect(() => {
    // Initial health check with delay to allow backend to start
    const initializeHealthCheck = async () => {
      console.log("Initializing health check...");
      // Wait a bit for backend to start if it's starting up
      await new Promise(resolve => setTimeout(resolve, 2000));
      await checkHealth();
    };
    
    initializeHealthCheck();

    // Set up periodic health checks (every 30 seconds)
    healthCheckInterval.current = setInterval(checkHealth, 30000);

    return () => {
      if (healthCheckInterval.current) {
        clearInterval(healthCheckInterval.current);
      }
    };
  }, [checkHealth]);

  // Set up metrics refresh when backend is running
  useEffect(() => {
    if (isBackendRunning) {
      // Initial metrics refresh
      refreshMetrics();

      // Set up periodic metrics refresh (every 5 seconds when running)
      metricsInterval.current = setInterval(refreshMetrics, 5000);
    } else {
      // Clear metrics interval when backend is not running
      if (metricsInterval.current) {
        clearInterval(metricsInterval.current);
        metricsInterval.current = null;
      }
    }

    return () => {
      if (metricsInterval.current) {
        clearInterval(metricsInterval.current);
      }
    };
  }, [isBackendRunning, refreshMetrics]);

  return {
    isBackendRunning,
    isStarting,
    error,
    metrics,
    logs,
    errorLogs,
    startBackend,
    stopBackend,
    restartBackend,
    checkHealth,
    refreshMetrics,
    refreshLogs,
    clearLogs,
  };
};

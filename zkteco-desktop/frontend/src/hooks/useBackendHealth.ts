import { serviceAPI } from "@/lib/api";
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
    publicIp?: string;
    localIp?: string;
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
    port: 57575,
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

    const detectExistingBackend = useCallback(async (): Promise<boolean> => {
        try {
            // Use the improved detection from Tauri
            const isRunning = await invoke<boolean>("is_backend_running");
            return isRunning;
        } catch (error) {
            console.error("Failed to detect existing backend:", error);
            return false;
        }
    }, []);

    const checkHttpHealth = useCallback(async (): Promise<boolean> => {
        try {
            return await invoke<boolean>("check_backend_http_health");
        } catch (error) {
            console.error("Failed to check HTTP health:", error);
            return false;
        }
    }, []);

    const checkHealth = useCallback(async (): Promise<boolean> => {
        try {
            // Use comprehensive backend detection
            const healthy = await detectExistingBackend();
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
            setError(
                err instanceof Error ? err.message : "Health check failed",
            );
            setIsBackendRunning(false);
            setMetrics((prev) =>
                prev
                    ? { ...prev, status: "error" }
                    : { ...DEFAULT_METRICS, status: "error" },
            );
            return false;
        }
    }, [detectExistingBackend]);

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
                    port: 57575,
                    publicIp: metricsData.public_ip || 'N/A',
                    localIp: metricsData.local_ip || 'N/A',
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
            console.log("Starting backend - performing pre-flight checks...");

            // Pre-flight check: detect existing backend with comprehensive method
            const existingBackend = await detectExistingBackend();
            if (existingBackend) {
                console.log("Existing backend detected - skipping startup");
                setIsBackendRunning(true);
                setIsStarting(false);
                await refreshMetrics();
                return true;
            }

            console.log(
                "No existing backend detected - proceeding with startup",
            );

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

            // Verify startup with retry logic
            console.log("Verifying backend startup with retry logic...");
            const maxRetries = 6; // 6 retries = 30 seconds total
            let retryCount = 0;
            let backendHealthy = false;

            while (retryCount < maxRetries && !backendHealthy) {
                console.log(
                    `Verification attempt ${retryCount + 1}/${maxRetries}`,
                );

                // Wait before checking (exponential backoff)
                const waitTime = Math.min(
                    2000 * Math.pow(1.5, retryCount),
                    8000,
                ); // 2s, 3s, 4.5s, 6.75s, 8s, 8s
                await new Promise((resolve) => setTimeout(resolve, waitTime));

                // Check both HTTP health and process status
                const httpHealthy = await checkHttpHealth();
                const processRunning = await detectExistingBackend();

                backendHealthy = httpHealthy && processRunning;
                console.log(
                    `Attempt ${retryCount + 1}: HTTP healthy: ${httpHealthy}, Process running: ${processRunning}`,
                );

                if (backendHealthy) {
                    console.log("Backend verification successful!");
                    break;
                }

                retryCount++;
            }

            if (backendHealthy) {
                console.log("Backend started successfully after verification");
                setIsBackendRunning(true);
                await refreshMetrics();
                await refreshLogs();
                setIsStarting(false);
                return true;
            } else {
                // Detailed error reporting
                console.log(
                    "Backend startup verification failed - gathering error details",
                );
                await refreshLogs();

                try {
                    const errors = await invoke<LogEntry[]>(
                        "get_backend_error_logs",
                    );
                    const httpHealthy = await checkHttpHealth();
                    const processRunning = await detectExistingBackend();

                    if (errors.length > 0) {
                        const recentError = errors[errors.length - 1];
                        setError(
                            `Backend startup failed: ${recentError.message}`,
                        );
                    } else if (!processRunning) {
                        setError(
                            "Backend process failed to start or terminated unexpectedly",
                        );
                    } else if (!httpHealthy) {
                        setError(
                            "Backend process started but HTTP service is not responding",
                        );
                    } else {
                        setError(
                            "Backend startup verification failed for unknown reasons",
                        );
                    }
                } catch (logErr) {
                    console.error(
                        "Failed to get detailed error information:",
                        logErr,
                    );
                    setError(
                        "Backend startup failed - unable to retrieve error details",
                    );
                }

                setIsBackendRunning(false);
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
    }, [detectExistingBackend, refreshMetrics, refreshLogs, checkHttpHealth]);

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
                err instanceof Error
                    ? err.message
                    : "Failed to restart backend";
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
            await new Promise((resolve) => setTimeout(resolve, 2000));
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

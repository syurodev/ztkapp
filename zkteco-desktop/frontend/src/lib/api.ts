import { invoke } from "@tauri-apps/api/core";
import axios from "axios";

// API base configuration with fallbacks
const API_HOSTS = [
  "http://127.0.0.1:57575",
  "http://localhost:57575",
  "http://0.0.0.0:57575",
];

// Try to detect working API host
let API_BASE_URL = API_HOSTS[0];

// Function to test and set the working API host
const detectApiHost = async (): Promise<string> => {
  for (const host of API_HOSTS) {
    try {
      const response = await fetch(`${host}/service/status`, {
        method: "GET",
        signal: AbortSignal.timeout(2000),
      });
      if (response.ok) {
        console.log(`Detected working API host: ${host}`);
        return host;
      }
    } catch (error) {
      console.log(
        `Host ${host} not reachable:`,
        error instanceof Error ? error.message : error,
      );
    }
  }
  console.warn("No working API host found, using default");
  return API_HOSTS[0];
};

// Track backend startup attempts to prevent infinite loops
let backendStartupAttempts = 0;
const MAX_STARTUP_ATTEMPTS = 3;
const STARTUP_COOLDOWN = 30000; // 30 seconds

export const api = axios.create({
  baseURL: API_BASE_URL,
  // Increase default timeout to better handle large payloads
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(
      `Making ${config.method?.toUpperCase()} request to ${config.url}`,
    );
    return config;
  },
  (error) => {
    console.error("Request error:", error);
    return Promise.reject(error);
  },
);

// Auto-restart backend function
const attemptBackendRestart = async (): Promise<boolean> => {
  if (backendStartupAttempts >= MAX_STARTUP_ATTEMPTS) {
    console.warn("Max backend startup attempts reached, skipping auto-restart");
    return false;
  }

  try {
    backendStartupAttempts++;
    console.log(
      `Attempting to start backend (attempt ${backendStartupAttempts}/${MAX_STARTUP_ATTEMPTS})`,
    );

    const result = await invoke<string>("start_backend");
    console.log("Backend start result:", result);

    // Wait for backend to initialize
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // Test if backend is responding
    const healthResponse = await fetch(`${API_BASE_URL}/service/status`);
    const isHealthy = healthResponse.ok;

    if (isHealthy) {
      console.log("Backend restarted successfully");
      // Reset attempts counter on success
      setTimeout(() => {
        backendStartupAttempts = 0;
      }, STARTUP_COOLDOWN);
      return true;
    } else {
      console.warn("Backend started but health check failed");
      return false;
    }
  } catch (error) {
    console.error("Failed to restart backend:", error);
    return false;
  }
};

// Response interceptor with auto-restart capability
api.interceptors.response.use(
  (response) => {
    // Reset startup attempts on successful response
    if (backendStartupAttempts > 0) {
      setTimeout(() => {
        backendStartupAttempts = 0;
      }, STARTUP_COOLDOWN);
    }
    return response;
  },
  async (error) => {
    console.error("Response error:", error);

    const isNetworkError =
      error.code === "ECONNREFUSED" ||
      error.code === "ERR_NETWORK" ||
      error.message?.includes("Network Error") ||
      !error.response;

    if (isNetworkError) {
      console.error("Backend service connection failed");

      // Only attempt auto-restart for non-health-check requests
      const isHealthCheckRequest =
        error.config?.url?.includes("/service/status");

      if (
        !isHealthCheckRequest &&
        backendStartupAttempts < MAX_STARTUP_ATTEMPTS
      ) {
        console.log("Attempting automatic backend restart...");

        const restartSuccess = await attemptBackendRestart();

        if (restartSuccess) {
          // Retry the original request
          console.log("Retrying original request after backend restart...");

          // Wait a bit more for the backend to be fully ready
          await new Promise((resolve) => setTimeout(resolve, 2000));

          try {
            return await api.request(error.config);
          } catch (retryError) {
            console.error("Retry after restart failed:", retryError);
            return Promise.reject(retryError);
          }
        }
      }

      // Enhance error message for network errors
      error.message =
        "Backend service is not available. Please check if the service is running.";
    }

    return Promise.reject(error);
  },
);

// Service Status API
export const serviceAPI = {
  // Get service status
  getStatus: async () => {
    try {
      const response = await api.get("/service/status");
      return response.data;
    } catch (error) {
      throw new Error("Failed to get service status");
    }
  },

  // Stop service
  stop: async () => {
    try {
      const response = await api.post("/service/stop");
      return response.data;
    } catch (error) {
      throw new Error("Failed to stop service");
    }
  },

  // Restart service
  restart: async () => {
    try {
      const response = await api.post("/service/restart");
      return response.data;
    } catch (error) {
      throw new Error("Failed to restart service");
    }
  },

  // Get service logs
  getLogs: async () => {
    try {
      const response = await api.get("/service/logs");
      return response.data;
    } catch (error) {
      throw new Error("Failed to get service logs");
    }
  },
};

// User Management API
export const userAPI = {
  // Get all users (with automatic sync from device)
  getUsers: async () => {
    try {
      const response = await api.get("/users");
      return response.data;
    } catch (error) {
      throw new Error("Failed to get users");
    }
  },

  // Manual sync users from device
  syncUsers: async (deviceId?: string) => {
    try {
      const response = await api.post(
        "/users/sync",
        deviceId ? { device_id: deviceId } : {},
      );
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Alias for syncUsers (for backward compatibility)
  syncUsersFromDevice: async (deviceId?: string) => {
    try {
      const response = await api.post(
        "/users/sync",
        deviceId ? { device_id: deviceId } : {},
      );
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Create user
  createUser: async (userData: any) => {
    try {
      const response = await api.post("/user", userData);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Delete user
  deleteUser: async (userId: number) => {
    try {
      const response = await api.delete(`/user/${userId}`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Sync single user
  syncUser: async (userId: string) => {
    try {
      const response = await api.post(`/user/${userId}/sync`);
      return response.data;
    } catch (error: any) {
      // Preserve the error message from the API response
      const message =
        error.response?.data?.message || error.message || "Failed to sync user";
      const newError = new Error(message);
      (newError as any).response = error.response;
      throw newError;
    }
  },

  // Export users to JSON
  exportUsers: async () => {
    try {
      const response = await api.get("/users/export");
      return response.data;
    } catch (error: any) {
      const message =
        error.response?.data?.message ||
        error.message ||
        "Failed to export users";
      throw new Error(message);
    }
  },

  // Import users from JSON
  importUsers: async (formData: FormData) => {
    try {
      const response = await api.post("/users/import", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return response.data;
    } catch (error: any) {
      const message =
        error.response?.data?.message ||
        error.message ||
        "Failed to import users";
      const newError = new Error(message);
      (newError as any).response = error.response;
      throw newError;
    }
  },
};

// Fingerprint API
export const fingerprintAPI = {
  // Get fingerprint
  getFingerprint: async (userId: number, tempId: number) => {
    try {
      const response = await api.get(`/user/${userId}/fingerprint/${tempId}`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Create fingerprint
  createFingerprint: async (userId: number, tempId: number) => {
    try {
      const response = await api.post(`/user/${userId}/fingerprint`, {
        temp_id: tempId,
      });
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Delete fingerprint
  deleteFingerprint: async (userId: number, tempId: number) => {
    try {
      const response = await api.delete(
        `/user/${userId}/fingerprint/${tempId}`,
      );
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Device API (Legacy - single device)
export const deviceAPI = {
  // Connect to device
  capture: async () => {
    try {
      const response = await api.get("/device/capture");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Get device information
  getDeviceInfo: async () => {
    try {
      const response = await api.get("/device/info");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Sync employees to external API
  syncEmployee: async () => {
    try {
      const response = await api.post("/device/sync-employee");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Multi-Device Management API
export type DevicePingStatus = "success" | "failure";

export interface DevicePingEvent {
  type: "device_ping";
  device_id: string;
  status: DevicePingStatus;
  message: string;
  source: string;
  timestamp: string;
}

interface DeviceEventHandlers {
  onEvent: (event: DevicePingEvent) => void;
  onError?: (event: Event) => void;
  onOpen?: () => void;
}

export const devicesAPI = {
  // Get all devices
  getAllDevices: async () => {
    try {
      const response = await api.get("/devices");
      return response.data;
    } catch (error: any) {
      // Preserve original error for better handling in components
      if (error.response?.status) {
        const statusError = new Error(`API Error: ${error.response.status}`);
        (statusError as any).status = error.response.status;
        (statusError as any).originalError = error;
        throw statusError;
      }
      throw error;
    }
  },

  // Add new device
  addDevice: async (deviceData: any) => {
    try {
      const response = await api.post("/devices", deviceData);
      console.log(response);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Update device
  updateDevice: async (deviceId: string, deviceData: any) => {
    try {
      const response = await api.put(`/devices/${deviceId}`, deviceData);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Delete device
  deleteDevice: async (deviceId: string) => {
    try {
      const response = await api.delete(`/devices/${deviceId}`);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Activate device
  activateDevice: async (deviceId: string) => {
    try {
      const response = await api.put(`/devices/${deviceId}/activate`);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Test device connection
  testDevice: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/test`);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Get device info
  getDeviceInfo: async (deviceId: string) => {
    try {
      const response = await api.get(`/devices/${deviceId}/info`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Sync employees from device
  syncEmployeeFromDevice: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/sync-employee`);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Sync users from push device (queues DATA UPDATE USERINFO command)
  syncUsersFromPushDevice: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/sync-users`);
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  // Multi-Device Live Capture Management
  startAllCapture: async () => {
    try {
      const response = await api.post("/devices/capture/start-all");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  stopAllCapture: async () => {
    try {
      const response = await api.post("/devices/capture/stop-all");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  startDeviceCapture: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/capture/start`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  stopDeviceCapture: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/capture/stop`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  getCaptureStatus: async () => {
    try {
      const response = await api.get("/devices/capture/status");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  getDeviceCaptureStatus: async (deviceId: string) => {
    try {
      const response = await api.get(`/devices/${deviceId}/capture/status`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },

  subscribeToEvents: ({ onEvent, onError, onOpen }: DeviceEventHandlers) => {
    const eventSource = new EventSource(`${API_BASE_URL}/devices/events`);

    if (onOpen) {
      eventSource.addEventListener("ready", () => {
        onOpen();
      });
    }

    eventSource.onmessage = (event) => {
      if (!event.data) {
        return;
      }

      try {
        const payload = JSON.parse(event.data) as DevicePingEvent;
        if (payload?.type === "device_ping" && payload.device_id) {
          onEvent(payload);
        }
      } catch (parseError) {
        console.error("Failed to parse device event payload:", parseError);
      }
    };

    eventSource.onerror = (event) => {
      console.error("Device events SSE error:", event);
      onError?.(event);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  },

  // Sync all devices to external API
  syncToExternal: async () => {
    try {
      const response = await api.post("/devices/sync-external");
      return response.data;
    } catch (error) {
      // Re-throw the original error to preserve response data
      throw error;
    }
  },

  // Get all branches
  getBranches: async () => {
    try {
      const response = await api.get("/branches");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]?.["data"]?.["error"]);
    }
  },
};

export const attendanceAPI = {
  getAttendance: async (options?: {
    limit?: number;
    offset?: number;
    device_id?: string;
    date?: string;
  }) => {
    try {
      const params = new URLSearchParams();
      if (options?.limit) params.set("limit", options.limit.toString());
      if (options?.offset) params.set("offset", options.offset.toString());
      if (options?.device_id) params.set("device_id", options.device_id);
      if (options?.date) params.set("date", options.date);

      const url = `/attendance/logs${
        params.toString() ? `?${params.toString()}` : ""
      }`;
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      throw new Error("Failed to get attendance");
    }
  },
  syncAttendance: async () => {
    try {
      // Extend timeout specifically for heavy attendance requests
      const response = await api.post(
        "/attendance/sync",
        {},
        { timeout: 120000 },
      );
      return response.data;
    } catch (error) {
      throw new Error("Failed to sync attendance");
    }
  },
  syncDailyAttendance: async (options?: {
    date?: string;
    device_id?: string;
  }) => {
    try {
      const response = await api.post(
        "/attendance/sync-daily",
        {
          date: options?.date,
          device_id: options?.device_id,
        },
        { timeout: 60000 },
      );
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  previewDailyAttendance: async (options?: {
    date?: string;
    device_id?: string;
  }) => {
    try {
      const params = new URLSearchParams();
      if (options?.date) params.set("date", options.date);
      if (options?.device_id) params.set("device_id", options.device_id);

      const url = `/attendance/daily-preview${
        params.toString() ? `?${params.toString()}` : ""
      }`;
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  getHistory: async (options?: { date?: string; device_id?: string }) => {
    try {
      const params = new URLSearchParams();
      if (options?.date) params.set("date", options.date);
      if (options?.device_id) params.set("device_id", options.device_id);

      const url = `/attendance/history${
        params.toString() ? `?${params.toString()}` : ""
      }`;
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

export const configAPI = {
  getConfig: async () => {
    try {
      const response = await api.get("/config");
      return response.data;
    } catch (error: any) {
      // Preserve original error for better handling in components
      if (error.response?.status) {
        const statusError = new Error(`API Error: ${error.response.status}`);
        (statusError as any).status = error.response.status;
        (statusError as any).originalError = error;
        throw statusError;
      }
      throw error;
    }
  },
  updateConfig: async (configData: any) => {
    try {
      const response = await api.post("/config", configData);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Settings API
export const settingsAPI = {
  getAllSettings: async () => {
    try {
      const response = await api.get("/settings");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  getSetting: async (key: string) => {
    try {
      const response = await api.get(`/settings/${key}`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  updateSetting: async (key: string, value: string, description?: string) => {
    try {
      const response = await api.put(`/settings/${key}`, {
        value,
        description,
      });
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  getCleanupConfig: async () => {
    try {
      const response = await api.get("/settings/cleanup/config");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  updateCleanupConfig: async (config: {
    retention_days?: number;
    enabled?: boolean;
  }) => {
    try {
      const response = await api.put("/settings/cleanup/config", config);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Cleanup API
export const cleanupAPI = {
  previewCleanup: async (retentionDays?: number) => {
    try {
      const params = retentionDays ? `?retention_days=${retentionDays}` : "";
      const response = await api.get(`/attendance/cleanup/preview${params}`);
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
  executeCleanup: async (retentionDays?: number) => {
    try {
      const response = await api.post("/attendance/cleanup", {
        retention_days: retentionDays,
        confirmed: true,
      });
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Types
export interface Device {
  id: string;
  name: string;
  ip: string;
  port: number;
  password: string;
  timeout: number;
  retry_count: number;
  retry_delay: number;
  ping_interval: number;
  force_udp: boolean;
  is_active: boolean;
  device_type?: "pull" | "push"; // Device type: pull (TCP) or push (HTTP), defaults to 'pull'
  device_info: DeviceInfo;
}

export interface DeviceInfo {
  current_time: string;
  firmware_version: string;
  device_name: string;
  serial_number: string;
  mac_address: string;
  face_version: string;
  fp_version: string;
  platform: string;
  network: {
    ip: string;
    netmask: string;
    gateway: string;
  } | null;
}

export interface DevicesResponse {
  devices: Device[];
  active_device_id: string | null;
}

export interface User {
  id: string;
  user_id: number;
  name: string;
  full_name: string;
  groupId: number;
  privilege: number;
  card: number;
  device_id: string;
  is_synced: boolean;
  synced_at: string | null;
  created_at: string | null;
  external_user_id: number | null;
  avatar_url: string | null;
}

export interface UsersResponse {
  message: string;
  data: User[];
  sync_status: {
    success: boolean;
    synced_count: number;
    error: string | null;
  };
  source: string;
  device_connected: boolean;
}

export interface DeviceCaptureStatus {
  device_id: string;
  device_name: string;
  is_active: boolean;
  is_capturing: boolean;
  is_healthy: boolean;
  health_stats: {
    connections: number;
    disconnections: number;
    errors: number;
    last_connected: string | null;
    last_error: {
      time: string;
      message: string;
    } | null;
  };
}

export interface CaptureStatusResponse {
  overall_status: {
    active_captures: number;
    devices: string[];
    max_concurrent: number;
  };
  devices: DeviceCaptureStatus[];
}

export interface LiveAttendanceRecord {
  id?: number;
  user_id: string;
  name: string;
  avatar_url?: string | null;
  timestamp: string;
  method: number;
  action: number;
  device_id: string;
  is_synced: boolean;
  // New employee fields from external API
  full_name?: string;
  employee_code?: string;
  position?: string;
  department?: string;
  notes?: string;
  employee_object?: string;
}

// Health check
export const liveAPI = {
  connect: (
    onMessage: (data: LiveAttendanceRecord) => void,
    onError: (error: Event) => void,
    onOpen: () => void,
    deviceFilter?: string | "all", // Optional device filter
  ) => {
    const eventSource = new EventSource(`${API_BASE_URL}/live-events`);

    // Use our custom 'connected' event to confirm the connection is ready
    eventSource.addEventListener("connected", (event) => {
      console.log("SSE connection established:", event);
      onOpen();
    });

    eventSource.onerror = (error) => {
      console.error("EventSource failed:", error);
      onError(error);
      eventSource.close();
    };

    eventSource.addEventListener("attendance", (event) => {
      try {
        console.log("SSE attendance event received:", event.data);
        const newRecord = JSON.parse(event.data) as LiveAttendanceRecord;
        console.log("Parsed attendance record:", newRecord);

        // Apply device filter if specified
        if (deviceFilter && deviceFilter !== "all") {
          if (newRecord.device_id !== deviceFilter) {
            return; // Skip this record if it doesn't match the filter
          }
        }

        onMessage(newRecord);
      } catch (error) {
        console.error("Failed to parse attendance event:", error);
      }
    });

    // The heartbeat event can be used to implement a client-side timeout if needed
    eventSource.addEventListener("heartbeat", (event) => {
      console.log("SSE heartbeat received:", event.data);
    });

    // Return a cleanup function to close the connection
    return () => {
      eventSource.close();
    };
  },

  // Multi-Device Live API functions
  multiDevice: {
    startAllCapture: async () => {
      try {
        const response = await api.post("/devices/capture/start-all");
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },

    stopAllCapture: async () => {
      try {
        const response = await api.post("/devices/capture/stop-all");
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },

    startDeviceCapture: async (deviceId: string) => {
      try {
        const response = await api.post(`/devices/${deviceId}/capture/start`);
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },

    stopDeviceCapture: async (deviceId: string) => {
      try {
        const response = await api.post(`/devices/${deviceId}/capture/stop`);
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },

    getCaptureStatus: async (): Promise<CaptureStatusResponse> => {
      try {
        const response = await api.get("/devices/capture/status");
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },

    getDeviceCaptureStatus: async (
      deviceId: string,
    ): Promise<DeviceCaptureStatus> => {
      try {
        const response = await api.get(`/devices/${deviceId}/capture/status`);
        return response.data;
      } catch (error) {
        throw new Error((error as any)?.["response"]["data"]["error"]);
      }
    },
  },

  getBranches: async () => {
    try {
      const response = await api.get("/branches");
      return response.data;
    } catch (error) {
      throw new Error((error as any)?.["response"]["data"]["error"]);
    }
  },
};

// Health check with better error handling and retries
export const healthCheck = async (
  retries = 3,
  delay = 1000,
): Promise<boolean> => {
  // First try to detect the correct API host
  console.log("Detecting API host...");
  API_BASE_URL = await detectApiHost();

  for (let i = 0; i < retries; i++) {
    // Try all possible hosts on each retry
    for (const host of API_HOSTS) {
      try {
        console.log(`Health check attempt ${i + 1}/${retries} on ${host}`);

        // Try with fetch first as it's more direct
        const response = await fetch(`${host}/service/status`, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          // Timeout for fetch
          signal: AbortSignal.timeout(5000),
        });

        console.log(
          `Health check response status: ${response.status} for ${host}`,
        );

        if (response.ok) {
          const data = await response.json();
          console.log("Health check successful:", data);
          // Update API_BASE_URL to working host
          API_BASE_URL = host;
          // Update axios instance
          api.defaults.baseURL = host;
          return true;
        } else {
          console.warn(
            `Health check failed with status: ${response.status} for ${host}`,
          );
        }
      } catch (error) {
        console.error(`Health check on ${host} failed:`, error);

        // Log detailed error information
        if (error instanceof Error) {
          console.error("Error details:", {
            message: error.message,
            name: error.name,
            host: host,
          });
        }
      }
    }

    // Wait before retry (except for last attempt)
    if (i < retries - 1) {
      console.log(`Waiting ${delay}ms before retry...`);
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay *= 1.5; // Exponential backoff
    }
  }

  console.error("All health check attempts failed on all hosts");
  return false;
};

// Door Management API
export interface Door {
  id: number;
  name: string;
  device_id: string | null;
  location?: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DoorAccessLog {
  id: number;
  door_id: number;
  user_id?: number;
  user_name?: string;
  action: string;
  status: string;
  timestamp: string;
  notes?: string;
}

export const doorAPI = {
  // Get all doors
  getAllDoors: async (): Promise<{ success: boolean; data: Door[] }> => {
    const response = await api.get("/doors");
    return response.data;
  },

  // Get door by ID
  getDoor: async (
    doorId: number,
  ): Promise<{ success: boolean; data: Door }> => {
    const response = await api.get(`/doors/${doorId}`);
    return response.data;
  },

  // Create new door
  createDoor: async (doorData: {
    name: string;
    device_id?: number | null;
    location?: string;
    description?: string;
    status?: string;
  }): Promise<{ success: boolean; message: string; data: Door }> => {
    const response = await api.post("/doors", doorData);
    return response.data;
  },

  // Update door
  updateDoor: async (
    doorId: number,
    updates: Partial<Door>,
  ): Promise<{ success: boolean; message: string; data: Door }> => {
    const response = await api.put(`/doors/${doorId}`, updates);
    return response.data;
  },

  // Delete door
  deleteDoor: async (
    doorId: number,
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/doors/${doorId}`);
    return response.data;
  },

  // Unlock door
  unlockDoor: async (
    doorId: number,
    duration: number = 3,
    userId?: number,
    userName?: string,
  ): Promise<{ success: boolean; message: string; data: any }> => {
    const response = await api.post(`/doors/${doorId}/unlock`, {
      duration,
      user_id: userId,
      user_name: userName,
    });
    return response.data;
  },

  // Get door state
  getDoorState: async (
    doorId: number,
  ): Promise<{ success: boolean; data: any }> => {
    const response = await api.get(`/doors/${doorId}/state`);
    return response.data;
  },

  // Get access logs for a door
  getDoorAccessLogs: async (
    doorId: number,
    limit: number = 100,
    offset: number = 0,
  ): Promise<{ success: boolean; data: DoorAccessLog[] }> => {
    const response = await api.get(`/doors/${doorId}/access-logs`, {
      params: { limit, offset },
    });
    return response.data;
  },

  // Get doors by device
  getDoorsByDevice: async (
    deviceId: number,
  ): Promise<{ success: boolean; data: Door[] }> => {
    const response = await api.get(`/doors/device/${deviceId}`);
    return response.data;
  },

  // Get all access logs with optional filters
  getAllAccessLogs: async (
    userId?: number,
    limit: number = 100,
    offset: number = 0,
  ): Promise<{ success: boolean; data: DoorAccessLog[] }> => {
    const response = await api.get("/doors/access-logs", {
      params: { user_id: userId, limit, offset },
    });
    return response.data;
  },
};

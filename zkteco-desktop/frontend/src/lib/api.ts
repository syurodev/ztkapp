import { invoke } from "@tauri-apps/api/core";
import axios from "axios";

// API base configuration
const API_BASE_URL = "http://127.0.0.1:5001";

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
      throw new Error("Failed to sync users from device");
    }
  },

  // Create user
  createUser: async (userData: any) => {
    try {
      const response = await api.post("/user", userData);
      return response.data;
    } catch (error) {
      throw new Error("Failed to create user");
    }
  },

  // Delete user
  deleteUser: async (userId: number) => {
    try {
      const response = await api.delete(`/user/${userId}`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to delete user");
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
      throw new Error("Failed to get fingerprint");
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
      throw new Error("Failed to create fingerprint");
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
      throw new Error("Failed to delete fingerprint");
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
      throw new Error("Failed to connect to device");
    }
  },

  // Get device information
  getDeviceInfo: async () => {
    try {
      const response = await api.get("/device/info");
      return response.data;
    } catch (error) {
      throw new Error("Failed to get device info");
    }
  },

  // Sync employees to external API
  syncEmployee: async () => {
    try {
      const response = await api.post("/device/sync-employee");
      return response.data;
    } catch (error) {
      throw new Error("Failed to sync employees");
    }
  },
};

// Multi-Device Management API
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
      return response.data;
    } catch (error) {
      throw new Error("Failed to add device");
    }
  },

  // Update device
  updateDevice: async (deviceId: string, deviceData: any) => {
    try {
      const response = await api.put(`/devices/${deviceId}`, deviceData);
      return response.data;
    } catch (error) {
      throw new Error("Failed to update device");
    }
  },

  // Delete device
  deleteDevice: async (deviceId: string) => {
    try {
      const response = await api.delete(`/devices/${deviceId}`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to delete device");
    }
  },

  // Activate device
  activateDevice: async (deviceId: string) => {
    try {
      const response = await api.put(`/devices/${deviceId}/activate`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to activate device");
    }
  },

  // Test device connection
  testDevice: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/test`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to test device connection");
    }
  },

  // Get device info
  getDeviceInfo: async (deviceId: string) => {
    try {
      const response = await api.get(`/devices/${deviceId}/info`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to get device info");
    }
  },

  // Sync employees from device
  syncEmployeeFromDevice: async (deviceId: string) => {
    try {
      const response = await api.post(`/devices/${deviceId}/sync-employee`);
      return response.data;
    } catch (error) {
      throw new Error("Failed to sync employees from device");
    }
  },
};

export const attendanceAPI = {
  getAttendance: async () => {
    try {
      // Extend timeout specifically for heavy attendance requests
      const response = await api.get("/attendance", { timeout: 120000 });
      return response.data;
    } catch (error) {
      throw new Error("Failed to get attendance");
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
      throw new Error("Failed to update config");
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
  groupId: number;
  privilege: number;
  card: number;
  device_id: string;
  is_synced: boolean;
  synced_at: string | null;
  created_at: string | null;
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

// Health check
export const liveAPI = {
  connect: (
    onMessage: (data: any) => void,
    onError: (error: Event) => void,
    onOpen: () => void,
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
        const newRecord = JSON.parse(event.data);
        console.log("Parsed attendance record:", newRecord);
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
};

// Health check
export const healthCheck = async () => {
  try {
    const response = await api.get("/service/status");
    return response.status === 200;
  } catch (error) {
    return false;
  }
};

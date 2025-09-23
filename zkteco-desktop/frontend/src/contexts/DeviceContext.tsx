import {
    CaptureStatusResponse,
    Device,
    DeviceCaptureStatus,
    devicesAPI,
    DevicesResponse,
    liveAPI,
} from "@/lib/api";
import { createContext, useContext, useEffect, useState } from "react";
import { toast } from "sonner";

interface DeviceContextValue {
    devices: Device[];
    activeDevice: Device | null;
    activeDeviceId: string | null;
    isLoading: boolean;
    loadDevices: () => Promise<void>;
    setActiveDevice: (deviceId: string) => Promise<void>;
    refreshDevices: () => Promise<void>;
    addDevice: (device: Device) => void;
    updateDevice: (deviceId: string, device: Device) => void;
    removeDevice: (deviceId: string) => void;

    // Multi-Device Live Capture Management
    captureStatus: CaptureStatusResponse | null;
    isCaptureLoading: boolean;
    loadCaptureStatus: () => Promise<void>;
    startAllCapture: () => Promise<void>;
    stopAllCapture: () => Promise<void>;
    startDeviceCapture: (deviceId: string) => Promise<void>;
    stopDeviceCapture: (deviceId: string) => Promise<void>;
    getDeviceCaptureStatus: (deviceId: string) => DeviceCaptureStatus | null;
    isDeviceCapturing: (deviceId: string) => boolean;
}

const DeviceContext = createContext<DeviceContextValue | undefined>(undefined);

interface DeviceProviderProps {
    children: React.ReactNode;
}

export function DeviceProvider({ children }: DeviceProviderProps) {
    const [devices, setDevices] = useState<Device[]>([]);
    const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    // Multi-Device Live Capture State
    const [captureStatus, setCaptureStatus] =
        useState<CaptureStatusResponse | null>(null);
    const [isCaptureLoading, setIsCaptureLoading] = useState(false);

    const activeDevice =
        devices.find((device) => device.id === activeDeviceId) || null;

    // Helper function to extract error message from API response
    const getErrorMessage = (error: any): string => {
        if (error?.response?.data?.error) {
            return error.response.data.error;
        }
        if (error?.message) {
            return error.message;
        }
        if (typeof error === "string") {
            return error;
        }
        return "An unexpected error occurred";
    };

    const loadDevices = async () => {
        setIsLoading(true);
        try {
            const response: DevicesResponse = await devicesAPI.getAllDevices();
            setDevices(response.devices);
            setActiveDeviceId(response.active_device_id);
        } catch (error) {
            console.error("Error loading devices:", error);
            // Don't show toast error for initial load as it might fail if no devices exist
        } finally {
            setIsLoading(false);
        }
    };

    const setActiveDevice = async (deviceId: string) => {
        try {
            await devicesAPI.activateDevice(deviceId);
            setActiveDeviceId(deviceId);
            toast.success("Active device changed successfully");
        } catch (error) {
            toast.error("Failed to change active device");
            console.error("Error setting active device:", error);
            throw error;
        }
    };

    const refreshDevices = async () => {
        await loadDevices();
    };

    // Optimistic update methods for immediate UI updates
    const addDevice = (device: Device) => {
        setDevices((prev) => [...prev, device]);
    };

    const updateDevice = (deviceId: string, updatedDevice: Device) => {
        setDevices((prev) =>
            prev.map((device) =>
                device.id === deviceId ? updatedDevice : device,
            ),
        );
    };

    const removeDevice = (deviceId: string) => {
        setDevices((prev) => prev.filter((device) => device.id !== deviceId));
        // If removing active device, clear active device
        if (activeDeviceId === deviceId) {
            setActiveDeviceId(null);
        }
    };

    // Multi-Device Live Capture Functions
    const loadCaptureStatus = async () => {
        setIsCaptureLoading(true);
        try {
            const status = await liveAPI.multiDevice.getCaptureStatus();
            setCaptureStatus(status);
        } catch (error) {
            console.error("Error loading capture status:", error);
            const errorMessage = getErrorMessage(error);
            toast.error(`Failed to load capture status: ${errorMessage}`);
        } finally {
            setIsCaptureLoading(false);
        }
    };

    const startAllCapture = async () => {
        setIsCaptureLoading(true);
        try {
            await liveAPI.multiDevice.startAllCapture();
            toast.success("Multi-device live capture started successfully");
            await loadCaptureStatus(); // Refresh status
        } catch (error) {
            console.error("Error starting multi-device capture:", error);
            const errorMessage = getErrorMessage(error);
            toast.error(
                `Failed to start multi-device capture: ${errorMessage}`,
            );
            throw error;
        } finally {
            setIsCaptureLoading(false);
        }
    };

    const stopAllCapture = async () => {
        setIsCaptureLoading(true);
        try {
            await liveAPI.multiDevice.stopAllCapture();
            toast.success("Multi-device live capture stopped successfully");
            await loadCaptureStatus(); // Refresh status
        } catch (error) {
            console.error("Error stopping multi-device capture:", error);
            const errorMessage = getErrorMessage(error);
            toast.error(`Failed to stop multi-device capture: ${errorMessage}`);
            throw error;
        } finally {
            setIsCaptureLoading(false);
        }
    };

    const startDeviceCapture = async (deviceId: string) => {
        const device = devices.find((d) => d.id === deviceId);
        const deviceName = device?.name || deviceId;

        try {
            await liveAPI.multiDevice.startDeviceCapture(deviceId);
            toast.success(`Live capture started for ${deviceName}`);
            await loadCaptureStatus(); // Refresh status
        } catch (error) {
            console.error(
                `Error starting capture for device ${deviceId}:`,
                error,
            );
            const errorMessage = getErrorMessage(error);
            toast.error(
                `Failed to start capture for ${deviceName}: ${errorMessage}`,
            );
            throw error;
        }
    };

    const stopDeviceCapture = async (deviceId: string) => {
        const device = devices.find((d) => d.id === deviceId);
        const deviceName = device?.name || deviceId;

        try {
            await liveAPI.multiDevice.stopDeviceCapture(deviceId);
            toast.success(`Live capture stopped for ${deviceName}`);
            await loadCaptureStatus(); // Refresh status
        } catch (error) {
            console.error(
                `Error stopping capture for device ${deviceId}:`,
                error,
            );
            const errorMessage = getErrorMessage(error);
            toast.error(
                `Failed to stop capture for ${deviceName}: ${errorMessage}`,
            );
            throw error;
        }
    };

    const getDeviceCaptureStatus = (
        deviceId: string,
    ): DeviceCaptureStatus | null => {
        return (
            captureStatus?.devices.find((d) => d.device_id === deviceId) || null
        );
    };

    const isDeviceCapturing = (deviceId: string): boolean => {
        const deviceStatus = getDeviceCaptureStatus(deviceId);
        return deviceStatus?.is_capturing || false;
    };

    useEffect(() => {
        loadDevices();
        loadCaptureStatus(); // Load initial capture status
    }, []);

    // Auto-refresh capture status every 30 seconds
    useEffect(() => {
        const interval = setInterval(() => {
            loadCaptureStatus();
        }, 30000);

        return () => clearInterval(interval);
    }, []);

    const value: DeviceContextValue = {
        devices,
        activeDevice,
        activeDeviceId,
        isLoading,
        loadDevices,
        setActiveDevice,
        refreshDevices,
        addDevice,
        updateDevice,
        removeDevice,

        // Multi-Device Live Capture
        captureStatus,
        isCaptureLoading,
        loadCaptureStatus,
        startAllCapture,
        stopAllCapture,
        startDeviceCapture,
        stopDeviceCapture,
        getDeviceCaptureStatus,
        isDeviceCapturing,
    };

    return (
        <DeviceContext.Provider value={value}>
            {children}
        </DeviceContext.Provider>
    );
}

export function useDevice() {
    const context = useContext(DeviceContext);
    if (context === undefined) {
        throw new Error("useDevice must be used within a DeviceProvider");
    }
    return context;
}

import { Device, devicesAPI, DevicesResponse } from "@/lib/api";
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
}

const DeviceContext = createContext<DeviceContextValue | undefined>(undefined);

interface DeviceProviderProps {
  children: React.ReactNode;
}

export function DeviceProvider({ children }: DeviceProviderProps) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const activeDevice = devices.find((device) => device.id === activeDeviceId) || null;

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
    setDevices(prev => [...prev, device]);
  };

  const updateDevice = (deviceId: string, updatedDevice: Device) => {
    setDevices(prev => prev.map(device => 
      device.id === deviceId ? updatedDevice : device
    ));
  };

  const removeDevice = (deviceId: string) => {
    setDevices(prev => prev.filter(device => device.id !== deviceId));
    // If removing active device, clear active device
    if (activeDeviceId === deviceId) {
      setActiveDeviceId(null);
    }
  };

  useEffect(() => {
    loadDevices();
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
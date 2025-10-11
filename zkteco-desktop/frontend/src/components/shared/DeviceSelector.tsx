import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDevice } from "@/contexts/DeviceContext";
import {
  CheckCircle2,
  ChevronDown,
  Monitor,
  Plus,
  Settings,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

export function DeviceSelector() {
  const { devices, activeDevice, setActiveDevice, isLoading } = useDevice();
  const navigate = useNavigate();

  const handleDeviceChange = async (deviceId: string) => {
    if (deviceId === activeDevice?.id) return;

    try {
      await setActiveDevice(deviceId);
    } catch (error) {
      // Error is already handled in context
    }
  };

  if (devices.length === 0) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => navigate("/devices")}
        className="flex items-center gap-2"
      >
        <Plus className="h-4 w-4" />
        Thêm thiết bị
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading}
          className="flex items-center gap-2 min-w-[200px] justify-between"
        >
          <div className="flex items-center gap-2">
            <Monitor className="h-4 w-4" />
            <span className="truncate">
              {activeDevice ? `${activeDevice.name}` : "Chưa chọn thiết bị"}
            </span>
          </div>
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[250px]">
        <DropdownMenuLabel>Chọn thiết bị</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {devices.map((device) => {
          const isPushDevice = device.device_type === 'push';
          const deviceSubtext = isPushDevice
            ? `Push • ${device.device_info?.serial_number || 'Chờ cập nhật'}`
            : `${device.ip}:${device.port}`;

          return (
            <DropdownMenuItem
              key={device.id}
              onClick={() => handleDeviceChange(device.id)}
              className="flex items-center gap-3"
            >
              <div className="flex items-center gap-2 flex-1">
                {activeDevice?.id === device.id ? (
                  <CheckCircle2 className="h-4 w-4 text-teal-500" />
                ) : (
                  <Monitor className="h-4 w-4 text-muted-foreground" />
                )}
                <div className="flex-1">
                  <div className="font-medium">{device.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {deviceSubtext}
                  </div>
                </div>
              </div>
              {device.is_active && (
                <div className="w-2 h-2 rounded-full bg-green-500" />
              )}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => navigate("/devices")}
          className="flex items-center gap-2"
        >
          <Settings className="h-4 w-4" />
          Quản lý thiết bị
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Device } from "@/lib/api";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export interface DeviceFormData {
  name: string;
  ip: string;
  port: number;
  password: string;
  timeout: number;
  retry_count: number;
  retry_delay: number;
  ping_interval: number;
  force_udp: boolean;
  device_type?: 'pull' | 'push';
}

interface DeviceFormProps {
  initialData?: Partial<Device>;
  onSubmit: (data: DeviceFormData) => Promise<void>;
  isLoading?: boolean;
  mode: "add" | "edit";
  onCancel: () => void;
}

export function DeviceForm({
  initialData,
  onSubmit,
  isLoading = false,
  mode,
  onCancel,
}: DeviceFormProps) {
  const [formData, setFormData] = useState<DeviceFormData>({
    name: "",
    ip: "",
    port: 4370,
    password: "",
    timeout: 180,
    retry_count: 3,
    retry_delay: 2,
    ping_interval: 30,
    force_udp: true,
    device_type: 'pull',
  });

  const [portInput, setPortInput] = useState<string>("");

  // Load initial data for edit mode
  useEffect(() => {
    if (initialData && mode === "edit") {
      const portValue = initialData.port || 4370;
      setFormData({
        name: initialData.name || "",
        ip: initialData.ip || "",
        port: portValue,
        password: initialData.password || "",
        timeout:
          typeof initialData.timeout === "number"
            ? Math.max(initialData.timeout, 180)
            : 180,
        retry_count: initialData.retry_count || 3,
        retry_delay: initialData.retry_delay || 2,
        ping_interval: initialData.ping_interval || 30,
        force_udp: initialData.force_udp || false,
        device_type: initialData.device_type || 'pull',
      });
      setPortInput(portValue.toString());
    } else if (mode === "add") {
      // Reset form for add mode
      setFormData({
        name: "",
        ip: "",
        port: 4370,
        password: "",
        timeout: 180,
        retry_count: 3,
        retry_delay: 2,
        ping_interval: 30,
        force_udp: false,
        device_type: 'pull',
      });
      setPortInput("");
    }
  }, [initialData, mode]);

  const handleSubmit = async () => {
    // Validation
    const isPushDevice = formData.device_type === 'push';

    if (!formData.name) {
      toast.error("Tên thiết bị là bắt buộc");
      return;
    }

    // IP validation only for Pull devices
    if (!isPushDevice && !formData.ip) {
      toast.error("Thiết bị Pull bắt buộc phải có địa chỉ IP");
      return;
    }

    // Use default port if empty
    const finalFormData = {
      ...formData,
      port: portInput === "" ? 4370 : formData.port,
      // For push devices, set IP to 0.0.0.0 (not needed)
      ip: isPushDevice ? "0.0.0.0" : formData.ip,
    };

    try {
      await onSubmit(finalFormData);
    } catch (error) {
      // Error handling is done in parent component
      console.error("Form submission error:", error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !isLoading) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  };

  const isPushDevice = formData.device_type === 'push';

  return (
    <div className="space-y-6" onKeyDown={handleKeyDown}>
      {/* Device Type Selector */}
      <div className="space-y-2">
        <Label htmlFor="device_type">Loại thiết bị *</Label>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="device_type"
              value="pull"
              checked={formData.device_type === 'pull'}
              onChange={(e) => setFormData({ ...formData, device_type: 'pull' })}
              disabled={isLoading || mode === 'edit'}
              className="cursor-pointer"
            />
            <span className={mode === 'edit' ? 'text-muted-foreground' : ''}>Pull (TCP) - Thiết bị truyền thống</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="device_type"
              value="push"
              checked={formData.device_type === 'push'}
              onChange={(e) => setFormData({ ...formData, device_type: 'push' })}
              disabled={isLoading || mode === 'edit'}
              className="cursor-pointer"
            />
            <span className={mode === 'edit' ? 'text-muted-foreground' : ''}>Push (HTTP) - Thiết bị hiện đại</span>
          </label>
        </div>
        {isPushDevice && (
          <p className="text-sm text-muted-foreground">
            Thiết bị Push sẽ tự đăng ký khi gửi tín hiệu về máy chủ. Không cần cấu hình IP.
          </p>
        )}
        {mode === 'edit' && (
          <p className="text-sm text-yellow-600">
            Không thể đổi loại thiết bị sau khi đã tạo
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="name">Tên thiết bị *</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Cổng chính"
            disabled={isLoading}
            autoFocus
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="ip">Địa chỉ IP {!isPushDevice && '*'}</Label>
          <Input
            id="ip"
            value={formData.ip}
            onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
            placeholder={isPushDevice ? "Không cần cho thiết bị Push" : "192.168.1.201"}
            disabled={isLoading || isPushDevice}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="port">Cổng kết nối</Label>
          <Input
            id="port"
            type="number"
            value={portInput}
            onChange={(e) => {
              const value = e.target.value;
              setPortInput(value);
              setFormData({
                ...formData,
                port: value === "" ? 4370 : parseInt(value, 10) || 4370,
              });
            }}
            placeholder={isPushDevice ? "Không cần thiết" : "4370"}
            disabled={isLoading || isPushDevice}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Mật khẩu</Label>
          <Input
            id="password"
            type="password"
            value={formData.password}
            onChange={(e) =>
              setFormData({
                ...formData,
                password: e.target.value || "",
              })
            }
            disabled={isLoading}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="timeout">Timeout (giây)</Label>
          <Input
            id="timeout"
            type="number"
            value={formData.timeout}
            onChange={(e) =>
              setFormData({
                ...formData,
                timeout: parseInt(e.target.value, 10) || 180,
              })
            }
            disabled={isLoading}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="retry_count">Số lần thử lại</Label>
          <Input
            id="retry_count"
            type="number"
            value={formData.retry_count}
            onChange={(e) =>
              setFormData({
                ...formData,
                retry_count: parseInt(e.target.value, 10) || 3,
              })
            }
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={isLoading}>
          Hủy
        </Button>
        <Button onClick={handleSubmit} disabled={isLoading}>
          {isLoading
            ? mode === "add"
              ? "Đang thêm..."
              : "Đang cập nhật..."
            : mode === "add"
            ? "Thêm thiết bị"
            : "Cập nhật thiết bị"}
        </Button>
      </div>
    </div>
  );
}

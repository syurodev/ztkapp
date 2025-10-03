import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
    port: 0,
    password: "",
    timeout: 180,
    retry_count: 3,
    retry_delay: 2,
    ping_interval: 30,
    force_udp: true,
  });

  // Load initial data for edit mode
  useEffect(() => {
    if (initialData && mode === "edit") {
      setFormData({
        name: initialData.name || "",
        ip: initialData.ip || "",
        port: initialData.port || 0,
        password: initialData.password || "",
        timeout:
          typeof initialData.timeout === "number"
            ? Math.max(initialData.timeout, 180)
            : 180,
        retry_count: initialData.retry_count || 3,
        retry_delay: initialData.retry_delay || 2,
        ping_interval: initialData.ping_interval || 30,
        force_udp: initialData.force_udp || false,
      });
    } else if (mode === "add") {
      // Reset form for add mode
      setFormData({
        name: "",
        ip: "",
        port: 0,
        password: "",
        timeout: 180,
        retry_count: 3,
        retry_delay: 2,
        ping_interval: 30,
        force_udp: false,
      });
    }
  }, [initialData, mode]);

  const handleSubmit = async () => {
    // Validation
    if (!formData.name || !formData.ip) {
      toast.error("Device name and IP are required");
      return;
    }

    try {
      await onSubmit(formData);
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

  return (
    <div className="space-y-6" onKeyDown={handleKeyDown}>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="name">Device Name *</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Main Entrance"
            disabled={isLoading}
            autoFocus
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="ip">IP Address *</Label>
          <Input
            id="ip"
            value={formData.ip}
            onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
            placeholder="192.168.1.201"
            disabled={isLoading}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="port">Port</Label>
          <Input
            id="port"
            type="number"
            value={formData.port}
            onChange={(e) =>
              setFormData({
                ...formData,
                port: parseInt(e.target.value, 10) || 0,
              })
            }
            disabled={isLoading}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
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
          <Label htmlFor="timeout">Timeout (seconds)</Label>
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
          <Label htmlFor="retry_count">Retry Count</Label>
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
        <div className="col-span-2 flex items-center space-x-2">
          <Switch
            id="force_udp"
            checked={formData.force_udp}
            onCheckedChange={(checked) =>
              setFormData({ ...formData, force_udp: checked })
            }
            disabled={isLoading}
          />
          <Label htmlFor="force_udp">Force UDP</Label>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isLoading}>
          {isLoading
            ? mode === "add"
              ? "Adding..."
              : "Updating..."
            : mode === "add"
            ? "Add Device"
            : "Update Device"}
        </Button>
      </div>
    </div>
  );
}

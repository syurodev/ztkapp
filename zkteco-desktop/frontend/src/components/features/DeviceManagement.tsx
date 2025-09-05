import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Device, devicesAPI, DevicesResponse } from "@/lib/api";
import {
  AlertCircle,
  CheckCircle2,
  Monitor,
  Plus,
  Settings,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export function DeviceManagement() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  // Form state for adding/editing devices
  const [formData, setFormData] = useState({
    name: "",
    ip: "",
    port: 4370,
    password: 0,
    timeout: 10,
    retry_count: 3,
    retry_delay: 2,
    ping_interval: 30,
    force_udp: false,
  });

  useEffect(() => {
    loadDevices();
  }, []);

  const loadDevices = async () => {
    setIsLoading(true);
    try {
      const response: DevicesResponse = await devicesAPI.getAllDevices();
      setDevices(response.devices);
      setActiveDeviceId(response.active_device_id);
    } catch (error) {
      toast.error("Failed to load devices");
      console.error("Error loading devices:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      ip: "",
      port: 4370,
      password: 0,
      timeout: 10,
      retry_count: 3,
      retry_delay: 2,
      ping_interval: 30,
      force_udp: false,
    });
    setSelectedDevice(null);
  };

  const openAddDialog = () => {
    resetForm();
    setIsAddDialogOpen(true);
  };

  const openEditDialog = (device: Device) => {
    setFormData({
      name: device.name,
      ip: device.ip,
      port: device.port,
      password: device.password,
      timeout: device.timeout,
      retry_count: device.retry_count,
      retry_delay: device.retry_delay,
      ping_interval: device.ping_interval,
      force_udp: device.force_udp,
    });
    setSelectedDevice(device);
    setIsEditDialogOpen(true);
  };

  const handleAddDevice = async () => {
    if (!formData.name || !formData.ip) {
      toast.error("Device name and IP are required");
      return;
    }

    setIsLoading(true);
    try {
      await devicesAPI.addDevice(formData);
      toast.success("Device added successfully");
      setIsAddDialogOpen(false);
      resetForm();
      loadDevices();
    } catch (error) {
      toast.error("Failed to add device");
      console.error("Error adding device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateDevice = async () => {
    if (!selectedDevice || !formData.name || !formData.ip) {
      toast.error("Device name and IP are required");
      return;
    }

    setIsLoading(true);
    try {
      await devicesAPI.updateDevice(selectedDevice.id, formData);
      toast.success("Device updated successfully");
      setIsEditDialogOpen(false);
      resetForm();
      loadDevices();
    } catch (error) {
      toast.error("Failed to update device");
      console.error("Error updating device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDevice = async (deviceId: string, deviceName: string) => {
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }

    setIsLoading(true);
    try {
      await devicesAPI.deleteDevice(deviceId);
      toast.success("Device deleted successfully");
      loadDevices();
    } catch (error) {
      toast.error("Failed to delete device");
      console.error("Error deleting device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActivateDevice = async (deviceId: string) => {
    setIsLoading(true);
    try {
      await devicesAPI.activateDevice(deviceId);
      toast.success("Device activated successfully");
      setActiveDeviceId(deviceId);
      loadDevices();
    } catch (error) {
      toast.error("Failed to activate device");
      console.error("Error activating device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestDevice = async (deviceId: string) => {
    setIsLoading(true);
    try {
      const result = await devicesAPI.testDevice(deviceId);
      if (result.success) {
        toast.success("Device connection successful");
      } else {
        toast.error(`Connection failed: ${result.error}`);
      }
    } catch (error) {
      toast.error("Failed to test device connection");
      console.error("Error testing device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSyncEmployees = async (deviceId: string) => {
    setIsLoading(true);
    try {
      const result = await devicesAPI.syncEmployeeFromDevice(deviceId);
      toast.success(`Successfully synced ${result.employees_count} employees`);
    } catch (error) {
      toast.error("Failed to sync employees");
      console.error("Error syncing employees:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const DeviceFormFields = () => (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label htmlFor="name">Device Name *</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="Main Entrance"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ip">IP Address *</Label>
        <Input
          id="ip"
          value={formData.ip}
          onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
          placeholder="192.168.1.201"
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
              port: parseInt(e.target.value, 10) || 4370,
            })
          }
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="number"
          value={formData.password}
          onChange={(e) =>
            setFormData({
              ...formData,
              password: parseInt(e.target.value, 10) || 0,
            })
          }
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
              timeout: parseInt(e.target.value, 10) || 10,
            })
          }
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
        />
      </div>
      <div className="col-span-2 flex items-center space-x-2">
        <Switch
          id="force_udp"
          checked={formData.force_udp}
          onCheckedChange={(checked) =>
            setFormData({ ...formData, force_udp: checked })
          }
        />
        <Label htmlFor="force_udp">Force UDP</Label>
      </div>
    </div>
  );

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Device Management</h1>
        <Button onClick={openAddDialog} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Add Device
        </Button>
      </div>

      {devices.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-8">
            <Monitor className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No devices configured</h3>
            <p className="text-muted-foreground mb-4">
              Add your first ZKTeco device to get started
            </p>
            <Button onClick={openAddDialog}>Add Device</Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Devices</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>IP Address</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Serial Number</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {devices.map((device) => (
                  <TableRow key={device.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {device.device_info.device_name}
                        {activeDeviceId === device.id && (
                          <Badge variant="default" className="bg-teal-400">
                            Active
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {device.ip}:{device.port}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {device.is_active ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-yellow-500" />
                        )}
                        {device.is_active ? "Connected" : "Inactive"}
                      </div>
                    </TableCell>
                    <TableCell>
                      {device.device_info?.serial_number || "Unknown"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleTestDevice(device.id)}
                          disabled={isLoading}
                        >
                          Test
                        </Button>
                        {activeDeviceId !== device.id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleActivateDevice(device.id)}
                            disabled={isLoading}
                          >
                            Activate
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSyncEmployees(device.id)}
                          disabled={isLoading}
                        >
                          Sync
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openEditDialog(device)}
                          disabled={isLoading}
                        >
                          <Settings className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            handleDeleteDevice(device.id, device.name)
                          }
                          disabled={isLoading}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Add Device Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add New Device</DialogTitle>
            <DialogDescription>
              Configure a new ZKTeco device to connect to your system.
            </DialogDescription>
          </DialogHeader>
          <DeviceFormFields />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddDevice} disabled={isLoading}>
              {isLoading ? "Adding..." : "Add Device"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Device Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Device</DialogTitle>
            <DialogDescription>
              Update the configuration for {selectedDevice?.name}.
            </DialogDescription>
          </DialogHeader>
          <DeviceFormFields />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setIsEditDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleUpdateDevice} disabled={isLoading}>
              {isLoading ? "Updating..." : "Update Device"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

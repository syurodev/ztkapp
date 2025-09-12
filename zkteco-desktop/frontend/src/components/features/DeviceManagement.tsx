import { DeleteConfirmDialog } from "@/components/shared/DeleteConfirmDialog";
import { DeviceForm, DeviceFormData } from "@/components/shared/DeviceForm";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDevice } from "@/contexts/DeviceContext";
import { Device, devicesAPI } from "@/lib/api";
import {
  AlertCircle,
  CheckCircle2,
  Monitor,
  Plus,
  Settings,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export function DeviceManagement() {
  // Use DeviceContext instead of local state
  const {
    devices,
    activeDeviceId,
    refreshDevices,
    isLoading: contextLoading,
  } = useDevice();

  const [isLoading, setIsLoading] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  // Use context loading state or local loading state
  const loading = isLoading || contextLoading;

  const openAddDialog = () => {
    setSelectedDevice(null);
    setIsAddDialogOpen(true);
  };

  const openEditDialog = (device: Device) => {
    setSelectedDevice(device);
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (device: Device) => {
    setSelectedDevice(device);
    setIsDeleteDialogOpen(true);
  };

  const handleAddDevice = async (formData: DeviceFormData) => {
    setIsLoading(true);
    try {
      await devicesAPI.addDevice(formData);
      toast.success("Device added successfully");
      setIsAddDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      toast.error("Failed to add device");
      console.error("Error adding device:", error);
      throw error; // Re-throw to let DeviceForm handle it
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateDevice = async (formData: DeviceFormData) => {
    if (!selectedDevice) {
      toast.error("No device selected for update");
      return;
    }

    setIsLoading(true);
    try {
      await devicesAPI.updateDevice(selectedDevice.id, formData);
      toast.success("Device updated successfully");
      setIsEditDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      toast.error("Failed to update device");
      console.error("Error updating device:", error);
      throw error; // Re-throw to let DeviceForm handle it
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDevice = async () => {
    if (!selectedDevice) return;

    setIsLoading(true);
    try {
      await devicesAPI.deleteDevice(selectedDevice.id);
      toast.success("Device deleted successfully");
      setIsDeleteDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
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
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
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
                  <TableHead>Device Name</TableHead>
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
                        {device.name}
                        {activeDeviceId === device.id && (
                          <Badge variant="default" className="bg-teal-400">
                            Active
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">
                      {device.device_info.device_name}
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
                          disabled={loading}
                        >
                          Test
                        </Button>
                        {activeDeviceId !== device.id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleActivateDevice(device.id)}
                            disabled={loading}
                          >
                            Activate
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSyncEmployees(device.id)}
                          disabled={loading}
                        >
                          Sync
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openEditDialog(device)}
                          disabled={loading}
                        >
                          <Settings className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200 hover:border-red-300"
                          onClick={() => openDeleteDialog(device)}
                          disabled={loading}
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
          <DeviceForm
            mode="add"
            onSubmit={handleAddDevice}
            onCancel={() => setIsAddDialogOpen(false)}
            isLoading={loading}
          />
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
          <DeviceForm
            mode="edit"
            initialData={selectedDevice || undefined}
            onSubmit={handleUpdateDevice}
            onCancel={() => setIsEditDialogOpen(false)}
            isLoading={loading}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        device={selectedDevice}
        onConfirm={handleDeleteDevice}
        isLoading={loading}
        isActiveDevice={selectedDevice?.id === activeDeviceId}
      />
    </div>
  );
}

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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useDevice } from "@/contexts/DeviceContext";
import { Device, devicesAPI } from "@/lib/api";
import {
  AlertCircle,
  CheckCircle2,
  Monitor,
  Play,
  Plus,
  RefreshCw,
  SearchCheck,
  Settings,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { CloudUpload } from "lucide-react";

export function DeviceManagement() {
  // Use DeviceContext instead of local state
  const {
    devices,
    activeDeviceId,
    refreshDevices,
    isLoading: contextLoading,
    getDeviceHealthStatus,
  } = useDevice();

  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  // Use context loading state or local loading state
  const loading = isLoading || contextLoading;

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
    return "Đã xảy ra lỗi không xác định";
  };

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
      toast.success("Thêm thiết bị thành công");
      setIsAddDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể thêm thiết bị: ${errorMessage}`);
      console.error("Error adding device:", error);
      throw error; // Re-throw to let DeviceForm handle it
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateDevice = async (formData: DeviceFormData) => {
    if (!selectedDevice) {
      toast.error("Chưa chọn thiết bị để cập nhật");
      return;
    }

    setIsLoading(true);
    try {
      await devicesAPI.updateDevice(selectedDevice.id, formData);
      toast.success("Cập nhật thiết bị thành công");
      setIsEditDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể cập nhật thiết bị: ${errorMessage}`);
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
      toast.success("Xóa thiết bị thành công");
      setIsDeleteDialogOpen(false);
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể xóa thiết bị: ${errorMessage}`);
      console.error("Error deleting device:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActivateDevice = async (deviceId: string) => {
    setIsLoading(true);
    try {
      await devicesAPI.activateDevice(deviceId);
      toast.success("Kích hoạt thiết bị thành công");
      // Refresh devices in context - this will also update DeviceSelector
      await refreshDevices();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể kích hoạt thiết bị: ${errorMessage}`);
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
        toast.success("Kết nối thiết bị thành công");
      } else {
        toast.error(`Kết nối thất bại: ${result.error}`);
      }
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể kiểm tra kết nối thiết bị: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSyncToExternal = async () => {
    setIsSyncing(true);
    try {
      const result = await devicesAPI.syncToExternal();
      if (result.status === 200) {
        toast.success(
          result.message || "Đồng bộ thiết bị lên cloud thành công!",
        );
      } else {
        toast.error(
          result.message || "Đồng bộ thất bại với lỗi không xác định.",
        );
      }
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      toast.error(`Không thể đồng bộ: ${errorMessage}`);
      console.error("Error syncing devices to external API:", error);
    } finally {
      setIsSyncing(false);
    }
  };

  const formatPingTime = (timestamp?: string) => {
    if (!timestamp) return "";
    try {
      const date = new Date(timestamp);
      return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
    } catch (error) {
      console.error("Failed to format timestamp:", error);
      return timestamp;
    }
  };

  const renderStatusCell = (device: Device) => {
    const isPushDevice = device.device_type === "push";

    // Push devices are always connected (they push data to server)
    if (isPushDevice) {
      return (
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <span>Đã kết nối</span>
        </div>
      );
    }

    // Pull devices use health monitoring
    const healthEvent = getDeviceHealthStatus(device.id);

    if (healthEvent) {
      const isSuccess = healthEvent.status === "success";
      const Icon = isSuccess ? CheckCircle2 : AlertCircle;
      const statusLabel = isSuccess ? "Sẵn sàng" : "Không liên lạc được";

      const tooltipContent = [
        formatPingTime(healthEvent.timestamp),
        healthEvent.message,
        healthEvent.source && `Nguồn: ${healthEvent.source.replace(/_/g, " ")}`,
      ]
        .filter(Boolean)
        .join("\n");

      return (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2 cursor-default">
                <Icon
                  className={`h-4 w-4 ${
                    isSuccess ? "text-green-500" : "text-red-500"
                  }`}
                />
                <span>{statusLabel}</span>
              </div>
            </TooltipTrigger>
            {tooltipContent && (
              <TooltipContent className="whitespace-pre-line max-w-xs">
                {tooltipContent}
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      );
    }

    const fallbackIcon = device.is_active ? (
      <CheckCircle2 className="h-4 w-4 text-green-500" />
    ) : (
      <AlertCircle className="h-4 w-4 text-yellow-500" />
    );

    return (
      <div className="flex items-center gap-2">
        {fallbackIcon}
        <span>
          {device.is_active ? "Đang chờ tín hiệu" : "Không hoạt động"}
        </span>
      </div>
    );
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Quản lý thiết bị</h1>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={refreshDevices}
            disabled={loading || isSyncing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Tải lại
          </Button>
          <Button
            variant="outline"
            onClick={handleSyncToExternal}
            disabled={loading || isSyncing}
            className="flex items-center gap-2"
          >
            <CloudUpload
              className={`h-4 w-4 ${isSyncing ? "animate-spin" : ""}`}
            />
            Đồng bộ lên hệ thống
          </Button>
          <Button onClick={openAddDialog} className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Thêm thiết bị
          </Button>
        </div>
      </div>

      {devices.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-8">
            <Monitor className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Chưa có thiết bị nào</h3>
            <p className="text-muted-foreground mb-4">
              Thêm thiết bị ZKTeco đầu tiên để bắt đầu sử dụng
            </p>
            <Button onClick={openAddDialog}>Thêm thiết bị</Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>Danh sách thiết bị</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={refreshDevices}
                disabled={loading}
                className="flex items-center gap-2"
              >
                <RefreshCw
                  className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                />
                Làm mới
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên hiển thị</TableHead>
                  <TableHead>Tên thiết bị</TableHead>
                  <TableHead>Loại</TableHead>
                  <TableHead>Địa chỉ IP</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead>Số serial</TableHead>
                  <TableHead>Hành động</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {devices.map((device) => {
                  const isPushDevice = device.device_type === "push";

                  return (
                    <TableRow key={device.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {device.name}
                          {activeDeviceId === device.id && (
                            <Badge variant="default" className="bg-teal-400">
                              Đang dùng
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">
                        {device.device_info?.device_name || "Không rõ"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={isPushDevice ? "secondary" : "outline"}>
                          {isPushDevice ? "Push" : "Pull"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {isPushDevice ? (
                          <span className="text-muted-foreground">
                            Không áp dụng
                          </span>
                        ) : (
                          `${device.ip}:${device.port}`
                        )}
                      </TableCell>
                      <TableCell>{renderStatusCell(device)}</TableCell>
                      <TableCell>
                        {device.device_info?.serial_number || "Không rõ"}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {/* Test button only for Pull devices */}
                          {!isPushDevice && (
                            <Tooltip>
                              <TooltipTrigger>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleTestDevice(device.id)}
                                  disabled={loading}
                                >
                                  <SearchCheck />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Kiểm tra</p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                          {activeDeviceId !== device.id && (
                            <Tooltip>
                              <TooltipTrigger>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    handleActivateDevice(device.id)
                                  }
                                  disabled={loading}
                                >
                                  <Play />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Kích hoạt</p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                          <Tooltip>
                            <TooltipTrigger>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openEditDialog(device)}
                                disabled={loading}
                              >
                                <Settings className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Cài đặt</p>
                            </TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => openDeleteDialog(device)}
                                disabled={loading}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Xoá</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
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

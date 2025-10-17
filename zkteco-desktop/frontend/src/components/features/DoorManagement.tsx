import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Door, doorAPI, devicesAPI, Device } from "@/lib/api";
import {
  DoorOpen,
  Plus,
  Trash2,
  Settings,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";

const MotionTableRow = motion(TableRow);

export function DoorManagement() {
  const [doors, setDoors] = useState<Door[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedDoor, setSelectedDoor] = useState<Door | null>(null);
  const [unlockingDoorId, setUnlockingDoorId] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState<{
    name: string;
    device_id: string | null;
    location: string;
    description: string;
    status: string;
  }>({
    name: "",
    device_id: null,
    location: "",
    description: "",
    status: "active",
  });

  useEffect(() => {
    loadDoors();
    loadDevices();
  }, []);

  const loadDoors = async () => {
    setIsLoading(true);
    try {
      const response = await doorAPI.getAllDoors();
      if (response.success) {
        setDoors(response.data);
      }
    } catch (error) {
      toast.error("Không thể tải danh sách cửa");
      console.error("Error loading doors:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      const response = await devicesAPI.getAllDevices();
      const payload = response as any;
      const deviceList = Array.isArray(payload?.devices)
        ? payload.devices
        : Array.isArray(payload?.data?.devices)
          ? payload.data.devices
          : Array.isArray(payload?.data)
            ? payload.data
            : Array.isArray(payload)
              ? payload
              : [];

      setDevices(deviceList);
    } catch (error) {
      console.error("Error loading devices:", error);
    }
  };

  const openAddDialog = () => {
    setFormData({
      name: "",
      device_id: null,
      location: "",
      description: "",
      status: "active",
    });
    setSelectedDoor(null);
    setIsAddDialogOpen(true);
  };

  const openEditDialog = (door: Door) => {
    setFormData({
      name: door.name,
      device_id: door.device_id,
      location: door.location || "",
      description: door.description || "",
      status: door.status,
    });
    setSelectedDoor(door);
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (door: Door) => {
    setSelectedDoor(door);
    setIsDeleteDialogOpen(true);
  };

  const handleAddDoor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) {
      toast.error("Vui lòng nhập tên cửa");
      return;
    }

    setIsLoading(true);
    try {
      const payload = {
        ...formData,
        device_id: formData.device_id ? parseInt(formData.device_id, 10) : null,
      };
      const response = await doorAPI.createDoor(payload);
      if (response.success) {
        toast.success("Thêm cửa thành công");
        setIsAddDialogOpen(false);
        await loadDoors();
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || "Không thể thêm cửa");
      console.error("Error adding door:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateDoor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoor) return;

    setIsLoading(true);
    try {
      const response = await doorAPI.updateDoor(selectedDoor.id, formData);
      if (response.success) {
        toast.success("Cập nhật cửa thành công");
        setIsEditDialogOpen(false);
        await loadDoors();
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || "Không thể cập nhật cửa");
      console.error("Error updating door:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDoor = async () => {
    if (!selectedDoor) return;

    setIsLoading(true);
    try {
      const response = await doorAPI.deleteDoor(selectedDoor.id);
      if (response.success) {
        toast.success("Xóa cửa thành công");
        setIsDeleteDialogOpen(false);
        await loadDoors();
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || "Không thể xóa cửa");
      console.error("Error deleting door:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnlockDoor = async (doorId: number, duration: number = 3) => {
    setUnlockingDoorId(doorId);
    try {
      const response = await doorAPI.unlockDoor(doorId, duration);
      if (response.success) {
        toast.success(`Mở cửa thành công trong ${duration} giây`);
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || "Không thể mở cửa");
      console.error("Error unlocking door:", error);
    } finally {
      setUnlockingDoorId(null);
    }
  };

  const getDeviceName = (deviceId: number | string | null) => {
    if (!deviceId) return "Chưa gán thiết bị";
    const targetId = deviceId.toString();
    const device = devices.find((d) => d.id === targetId);
    return device ? device.name : `Device #${targetId}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return <Badge className="bg-green-500">Hoạt động</Badge>;
      case "inactive":
        return <Badge variant="secondary">Không hoạt động</Badge>;
      case "error":
        return <Badge variant="destructive">Lỗi</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-2xl font-bold">Quản lý cửa</CardTitle>
          <div className="flex gap-2">
            <Button
              onClick={loadDoors}
              variant="outline"
              size="sm"
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              <span className="ml-2">Làm mới</span>
            </Button>
            <Button onClick={openAddDialog} size="sm">
              <Plus className="h-4 w-4" />
              <span className="ml-2">Thêm cửa</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && doors.length === 0 ? (
            <div className="flex justify-center items-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : doors.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Chưa có cửa nào. Nhấn "Thêm cửa" để bắt đầu.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên</TableHead>
                  <TableHead>Thiết bị</TableHead>
                  <TableHead>Vị trí</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnimatePresence>
                  {doors.map((door) => (
                    <MotionTableRow
                      key={door.id}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.2 }}
                    >
                      <TableCell className="font-medium">{door.name}</TableCell>
                      <TableCell>{getDeviceName(door.device_id)}</TableCell>
                      <TableCell>{door.location || "-"}</TableCell>
                      <TableCell>{getStatusBadge(door.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            onClick={() => handleUnlockDoor(door.id, 3)}
                            variant="default"
                            size="sm"
                            disabled={
                              unlockingDoorId === door.id || !door.device_id
                            }
                          >
                            {unlockingDoorId === door.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <DoorOpen className="h-4 w-4" />
                            )}
                            <span className="ml-2">Mở cửa</span>
                          </Button>
                          <Button
                            onClick={() => openEditDialog(door)}
                            variant="outline"
                            size="sm"
                          >
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button
                            onClick={() => openDeleteDialog(door)}
                            variant="destructive"
                            size="sm"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </MotionTableRow>
                  ))}
                </AnimatePresence>
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add Door Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Thêm cửa mới</DialogTitle>
            <DialogDescription>
              Nhập thông tin cửa cần thêm vào hệ thống
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddDoor} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Tên cửa *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Ví dụ: Cửa chính"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="device_id">Thiết bị (tùy chọn)</Label>
              <Select
                value={formData.device_id || "none"}
                onValueChange={(value) =>
                  setFormData({
                    ...formData,
                    device_id: value === "none" ? null : value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Chọn thiết bị hoặc để trống" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Không gán thiết bị</SelectItem>
                  {devices.map((device) => (
                    <SelectItem key={device.id} value={device.id.toString()}>
                      {device.name} ({device.ip})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">Vị trí</Label>
              <Input
                id="location"
                value={formData.location}
                onChange={(e) =>
                  setFormData({ ...formData, location: e.target.value })
                }
                placeholder="Ví dụ: Tầng 1"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Mô tả</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Mô tả chi tiết về cửa"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsAddDialogOpen(false)}
              >
                Hủy
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Thêm"
                )}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Door Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Chỉnh sửa cửa</DialogTitle>
            <DialogDescription>
              Cập nhật thông tin cửa trong hệ thống
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUpdateDoor} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Tên cửa *</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Ví dụ: Cửa chính"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-device_id">Thiết bị (tùy chọn)</Label>
              <Select
                value={formData.device_id || "none"}
                onValueChange={(value) =>
                  setFormData({
                    ...formData,
                    device_id: value === "none" ? null : value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Chọn thiết bị hoặc để trống" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Không gán thiết bị</SelectItem>
                  {devices.map((device) => (
                    <SelectItem key={device.id} value={device.id.toString()}>
                      {device.name} ({device.ip})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-location">Vị trí</Label>
              <Input
                id="edit-location"
                value={formData.location}
                onChange={(e) =>
                  setFormData({ ...formData, location: e.target.value })
                }
                placeholder="Ví dụ: Tầng 1"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Mô tả</Label>
              <Input
                id="edit-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Mô tả chi tiết về cửa"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-status">Trạng thái</Label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Hoạt động</SelectItem>
                  <SelectItem value="inactive">Không hoạt động</SelectItem>
                  <SelectItem value="error">Lỗi</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsEditDialogOpen(false)}
              >
                Hủy
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Cập nhật"
                )}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xóa cửa</AlertDialogTitle>
            <AlertDialogDescription>
              {`Bạn có chắc chắn muốn xóa cửa "${selectedDoor?.name}"? Hành động này không thể hoàn tác.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteDoor} disabled={isLoading}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Xóa"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

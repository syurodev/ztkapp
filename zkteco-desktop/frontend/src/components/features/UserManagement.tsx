import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDevice } from "@/contexts/DeviceContext";
import { deviceAPI, User, userAPI, UsersResponse } from "@/lib/api";
import { buildAvatarUrl, getResourceDomain } from "@/lib/utils";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Monitor,
  RefreshCw,
  UserCheck,
  Users,
  XCircle,
  RefreshCcw,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

// Using User interface from API types

// interface UserFormData {
//   name: string;
//   privilege: number;
//   password: string;
//   group_id: number;
//   card: number;
// }

// const initialFormData: UserFormData = {
//   name: "",
//   privilege: 0,
//   password: "",
//   group_id: 0,
//   card: 0,
// };

export function UserManagement() {
  const { activeDevice } = useDevice();
  const [users, setUsers] = useState<User[]>([]);
  const [syncStatus, setSyncStatus] = useState<
    UsersResponse["sync_status"] | null
  >(null);
  const [deviceConnected, setDeviceConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSyncingFromDevice, setIsSyncingFromDevice] = useState(false);
  const [resourceDomain, setResourceDomain] = useState<string>("");

  // Load resource domain on mount
  useEffect(() => {
    getResourceDomain().then(setResourceDomain);
  }, []);
  // const [isDialogOpen, setIsDialogOpen] = useState(false);
  // const [formData, setFormData] = useState<UserFormData>(initialFormData);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [syncingUsers, setSyncingUsers] = useState<Set<string>>(new Set());

  // Load users when activeDevice changes
  useEffect(() => {
    if (activeDevice) {
      loadUsers();
    } else {
      setUsers([]);
      setError(null);
    }
  }, [activeDevice]);

  const loadUsers = async () => {
    if (!activeDevice) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response: UsersResponse = await userAPI.getUsers();
      console.log("Users response:", response);

      // Set sync status and device connection info
      setSyncStatus(response.sync_status);
      setDeviceConnected(response.device_connected);

      // Use the data directly from response as it's already properly formatted
      setUsers(response.data || []);
    } catch (err) {
      setError(
        "Không thể tải danh sách người dùng. Vui lòng kiểm tra dịch vụ backend.",
      );
      console.error("Error loading users:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // const handleCreateUser = async () => {
  //   if (!activeDevice) {
  //     toast.error("Please select a device first");
  //     return;
  //   }

  //   if (!formData.name.trim()) {
  //     toast.error("User name is required");
  //     return;
  //   }

  //   setIsLoading(true);
  //   try {
  //     // Generate unique user_id
  //     const maxId = users.reduce(
  //       (max, user: User) => Math.max(max, user.user_id),
  //       0
  //     );
  //     const newUserId = maxId + 1;

  //     const userData = {
  //       user_id: newUserId,
  //       user_data: {
  //         name: formData.name,
  //         privilege: formData.privilege,
  //         password: formData.password || "123456", // Default password
  //         group_id: formData.group_id,
  //         card: formData.card || 0,
  //       },
  //     };

  //     await userAPI.createUser(userData);
  //     toast.success("User created successfully");
  //     setIsDialogOpen(false);
  //     setFormData(initialFormData);
  //     await loadUsers(); // Reload users
  //   } catch (err) {
  //     toast.error("Failed to create user");
  //     console.error("Error creating user:", err);
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };

  // const handleDeleteUser = async (userId: number, userName: string) => {
  //   if (!confirm(`Are you sure you want to delete user "${userName}"?`)) {
  //     return;
  //   }

  //   setIsLoading(true);
  //   try {
  //     await userAPI.deleteUser(userId);
  //     toast.success("User deleted successfully");
  //     await loadUsers(); // Reload users
  //   } catch (err) {
  //     toast.error("Failed to delete user");
  //     console.error("Error deleting user:", err);
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };

  const handleSyncEmployee = async () => {
    if (!activeDevice) {
      toast.error("Vui lòng chọn thiết bị trước");
      return;
    }

    setIsSyncing(true);
    try {
      const result = await deviceAPI.syncEmployee();

      if (result["success"]) {
        toast.success(
          `Đã đồng bộ ${result.employees_count} nhân sự lên hệ thống ngoài`,
        );
        // Reload users to get updated sync status
        await loadUsers();
      } else {
        toast.error(result.message);
      }

      console.log("Sync result:", result);
    } catch (err: any) {
      console.log(err);

      const errorMessage = err.message || "Không thể đồng bộ nhân sự";
      toast.error(errorMessage);
      console.error("Error syncing employees:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSyncSingleUser = async (userId: string, userName: string) => {
    if (!activeDevice) {
      toast.error("Vui lòng chọn thiết bị trước");
      return;
    }

    setSyncingUsers((prev) => new Set(prev).add(userId));
    try {
      const result = await userAPI.syncUser(userId);

      if (result.success) {
        toast.success(`Đã đồng bộ ${userName} lên hệ thống ngoài`);
        // Reload users to get updated sync status
        await loadUsers();
      } else {
        toast.error(result.message || "Không thể đồng bộ người dùng");
      }
    } catch (err: any) {
      const errorMessage = err.message || "Không thể đồng bộ người dùng";
      toast.error(errorMessage);
      console.error("Error syncing user:", err);
    } finally {
      setSyncingUsers((prev) => {
        const newSet = new Set(prev);
        newSet.delete(userId);
        return newSet;
      });
    }
  };

  const handleSyncUsersFromDevice = async () => {
    if (!activeDevice) {
      toast.error("Vui lòng chọn thiết bị trước");
      return;
    }

    setIsSyncingFromDevice(true);
    try {
      const result = await userAPI.syncUsersFromDevice();

      if (result.success) {
        toast.success(
          `Đã đồng bộ ${result.synced_count} người dùng từ thiết bị`,
        );
        // Reload users to get updated data
        await loadUsers();
      } else {
        toast.error(
          result.message || "Không thể đồng bộ người dùng từ thiết bị",
        );
      }
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.error ||
        err.message ||
        "Không thể đồng bộ người dùng từ thiết bị";
      toast.error(errorMessage);
      console.error("Error syncing users from device:", err);
    } finally {
      setIsSyncingFromDevice(false);
    }
  };

  // const handleSyncUsersFromPushDevice = async () => {
  //   if (!activeDevice) {
  //     toast.error("Vui lòng chọn thiết bị trước");
  //     return;
  //   }

  //   setIsSyncingFromDevice(true);
  //   try {
  //     const result = await devicesAPI.syncUsersFromPushDevice(activeDevice.id);

  //     toast.success(result.message || "Đã gửi lệnh đồng bộ người dùng thành công");
  //     toast.info("Thiết bị sẽ đẩy dữ liệu người dùng ở lần ping tiếp theo. Vui lòng chờ...");

  //     // Wait a bit then reload users
  //     setTimeout(() => {
  //       loadUsers();
  //     }, 3000);
  //   } catch (err: any) {
  //     const errorMessage = err.response?.data?.error || err.message || "Không thể đồng bộ người dùng từ thiết bị push";
  //     toast.error(errorMessage);
  //     console.error("Error syncing users from push device:", err);
  //   } finally {
  //     setIsSyncingFromDevice(false);
  //   }
  // };

  // Filter users based on search query
  const filteredUsers = users.filter((user) =>
    user.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const getSyncStatusBadge = (user: User) => {
    if (user.is_synced) {
      return (
        <Badge
          variant="default"
          className="bg-green-100 text-green-800 border-green-300"
        >
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Đã đồng bộ
        </Badge>
      );
    } else {
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 border-yellow-300"
        >
          <Clock className="h-3 w-3 mr-1" />
          Đang chờ
        </Badge>
      );
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Không có";
    try {
      return new Date(dateString).toLocaleString("vi-VN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  // const getPrivilegeLabel = (privilege: number) => {
  //   switch (privilege) {
  //     case 0:
  //       return { label: "User", variant: "secondary" as const };
  //     case 1:
  //       return { label: "Enroller", variant: "default" as const };
  //     case 2:
  //       return { label: "Administrator", variant: "destructive" as const };
  //     case 3:
  //       return { label: "Super Admin", variant: "destructive" as const };
  //     default:
  //       return { label: "Unknown", variant: "outline" as const };
  //   }
  // };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Users className="h-6 w-6" />
            Quản lý người dùng
          </h2>
          <div className="flex items-center gap-4 mt-1">
            <p className="text-muted-foreground">
              Quản lý người dùng và quyền truy cập
            </p>
            {syncStatus && (
              <div className="flex items-center gap-2">
                {deviceConnected ? (
                  <Badge
                    variant="default"
                    className="bg-green-100 text-green-800 border-green-300"
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Thiết bị đã kết nối
                  </Badge>
                ) : (
                  <Badge
                    variant="secondary"
                    className="bg-orange-100 text-orange-800 border-orange-300"
                  >
                    <XCircle className="h-3 w-3 mr-1" />
                    Thiết bị ngoại tuyến
                  </Badge>
                )}
                {syncStatus.success && syncStatus.synced_count > 0 && (
                  <Badge
                    variant="outline"
                    className="bg-blue-50 text-blue-800 border-blue-300"
                  >
                    +{syncStatus.synced_count} người dùng mới đã đồng bộ
                  </Badge>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Sync from device button for pull devices */}
          {activeDevice?.device_type === "pull" && (
            <Button
              variant="outline"
              onClick={handleSyncUsersFromDevice}
              disabled={isSyncingFromDevice}
              className="flex items-center gap-2"
            >
              <RefreshCw
                className={`h-4 w-4 ${isSyncingFromDevice ? "animate-spin" : ""}`}
              />
              {isSyncingFromDevice ? "Đang đồng bộ..." : "Đồng bộ từ thiết bị"}
            </Button>
          )}
          {/* Refresh button for push devices - just reload data from DB */}
          {activeDevice?.device_type === "push" && (
            <Button
              variant="outline"
              onClick={loadUsers}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              <RefreshCw
                className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
              />
              {isLoading ? "Đang tải..." : "Làm mới"}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleSyncEmployee}
            disabled={isSyncing}
            className="flex items-center gap-2"
          >
            <RefreshCw
              className={`h-4 w-4 ${isSyncing ? "animate-spin" : ""}`}
            />
            {isSyncing ? "Đang đồng bộ..." : "Đồng bộ nhân sự"}
          </Button>
          {/* <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Add User
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create New User</DialogTitle>
                <DialogDescription>
                  Add a new user to the ZKTeco system.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, name: e.target.value }))
                    }
                    placeholder="Enter user name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="privilege">Privilege Level</Label>
                  <select
                    id="privilege"
                    value={formData.privilege}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        privilege: parseInt(e.target.value),
                      }))
                    }
                    className="w-full p-2 border rounded-md"
                  >
                    <option value={0}>User</option>
                    <option value={1}>Enroller</option>
                    <option value={2}>Administrator</option>
                    <option value={3}>Super Admin</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        password: e.target.value,
                      }))
                    }
                    placeholder="Leave empty for default (123456)"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="group_id">Group ID</Label>
                    <Input
                      id="group_id"
                      type="number"
                      value={formData.group_id}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          group_id: parseInt(e.target.value) || 0,
                        }))
                      }
                      placeholder="0"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="card">Card Number</Label>
                    <Input
                      id="card"
                      type="number"
                      value={formData.card}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          card: parseInt(e.target.value) || 0,
                        }))
                      }
                      placeholder="0"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsDialogOpen(false);
                      setFormData(initialFormData);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleCreateUser} disabled={isLoading}>
                    {isLoading ? "Creating..." : "Create User"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog> */}
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex items-center space-x-2">
        <div className="flex-1">
          <Input
            placeholder="Tìm kiếm người dùng theo tên..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
      </div>

      {/* No Device Selected Alert */}
      {!activeDevice ? (
        <Alert>
          <Monitor className="h-4 w-4" />
          <AlertDescription>
            Vui lòng chọn thiết bị để quản lý người dùng. Truy cập Quản lý thiết
            bị để cấu hình.
          </AlertDescription>
        </Alert>
      ) : error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : syncStatus?.error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Đồng bộ với thiết bị thất bại: {syncStatus.error}. Đang hiển thị dữ
            liệu từ cơ sở dữ liệu.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCheck className="h-5 w-5" />
            Người dùng ({filteredUsers.length})
          </CardTitle>
          <CardDescription>
            Danh sách người dùng đang có trong hệ thống
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">
                Đang tải danh sách người dùng...
              </div>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  {searchQuery
                    ? `Không tìm thấy người dùng nào khớp với "${searchQuery}"`
                    : "Chưa có người dùng nào"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Bấm "Thêm người dùng" để tạo người dùng đầu tiên
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableCaption>
                Danh sách người dùng từ thiết bị ZKTeco kèm trạng thái đồng bộ
              </TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>STT</TableHead>
                  <TableHead>ID người dùng</TableHead>
                  <TableHead>Họ tên</TableHead>
                  <TableHead>Nhóm</TableHead>
                  <TableHead>Trạng thái đồng bộ</TableHead>
                  <TableHead>Đồng bộ lúc</TableHead>
                  <TableHead>Tạo lúc</TableHead>
                  <TableHead className="text-right">Hành động</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user, index) => {
                  const initials = user.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .toUpperCase()
                    .slice(0, 2);

                  return (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{index + 1}</TableCell>
                      <TableCell className="font-medium">{user.id}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            {user.avatar_url && (
                              <AvatarImage
                                src={buildAvatarUrl(
                                  user.avatar_url,
                                  resourceDomain,
                                )}
                                alt={user.name}
                              />
                            )}
                            <AvatarFallback className="text-xs">
                              {initials}
                            </AvatarFallback>
                          </Avatar>
                          <span>{user.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>{user.groupId}</TableCell>
                      <TableCell>{getSyncStatusBadge(user)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(user.synced_at)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(user.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            handleSyncSingleUser(user.id, user.name)
                          }
                          disabled={syncingUsers.has(user.id)}
                          className="h-8 w-8 p-0"
                          title="Đồng bộ người dùng này lên API ngoài"
                        >
                          <RefreshCcw
                            className={`h-4 w-4 ${syncingUsers.has(user.id) ? "animate-spin" : ""}`}
                          />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Tổng số người dùng</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{users.length}</div>
            <p className="text-sm text-muted-foreground">
              Số người dùng đã đăng ký
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Đã đồng bộ
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">
              {users.filter((user) => user.is_synced).length}
            </div>
            <p className="text-sm text-muted-foreground">
              Đã đẩy lên hệ thống ngoài
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-4 w-4 text-yellow-600" />
              Đang chờ đồng bộ
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-yellow-600">
              {users.filter((user) => !user.is_synced).length}
            </div>
            <p className="text-sm text-muted-foreground">Đang chờ đồng bộ</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quản trị viên</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {users.filter((user) => user.privilege >= 2).length}
            </div>
            <p className="text-sm text-muted-foreground">
              Người dùng thuộc nhóm quản trị
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

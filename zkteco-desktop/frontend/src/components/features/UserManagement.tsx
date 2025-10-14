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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
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
    Download,
    FileJson, Minus,
    Monitor,
    RefreshCcw,
    RefreshCw,
    Upload,
    UserCheck,
    Users,
    XCircle,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";

const MotionTableRow = motion(TableRow);

interface UserToImport {
  user_id: string;
  name: string;
  serial_number?: string;
}

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
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [syncingUsers, setSyncingUsers] = useState<Set<string>>(new Set());

  // Import Dialog State
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isExactImport, setIsExactImport] = useState(false);
  const [usersToImportPreview, setUsersToImportPreview] = useState<
    UserToImport[]
  >([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getResourceDomain().then(setResourceDomain);
  }, []);

  useEffect(() => {
    if (activeDevice) {
      loadUsers();
    } else {
      setUsers([]);
      setError(null);
    }
  }, [activeDevice]);

  const loadUsers = async () => {
    if (!activeDevice) return;
    setIsLoading(true);
    setError(null);
    try {
      const response: UsersResponse = await userAPI.getUsers();
      setSyncStatus(response.sync_status);
      setDeviceConnected(response.device_connected);
      setUsers(response.data || []);
    } catch (err) {
      setError(
        "Không thể tải danh sách người dùng. Vui lòng kiểm tra dịch vụ backend."
      );
      console.error("Error loading users:", err);
    } finally {
      setIsLoading(false);
    }
  };

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
          `Đã đồng bộ ${result.employees_count} nhân sự lên hệ thống ngoài`
        );
        await loadUsers();
      } else {
        toast.error(result.message);
      }
    } catch (err: any) {
      const errorMessage = err.message || "Không thể đồng bộ nhân sự";
      toast.error(errorMessage);
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
        await loadUsers();
      } else {
        toast.error(result.message || "Không thể đồng bộ người dùng");
      }
    } catch (err: any) {
      const errorMessage = err.message || "Không thể đồng bộ người dùng";
      toast.error(errorMessage);
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
          `Đã đồng bộ ${result.synced_count} người dùng từ thiết bị`
        );
        await loadUsers();
      } else {
        toast.error(
          result.message || "Không thể đồng bộ người dùng từ thiết bị"
        );
      }
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.error ||
        err.message ||
        "Không thể đồng bộ người dùng từ thiết bị";
      toast.error(errorMessage);
    } finally {
      setIsSyncingFromDevice(false);
    }
  };

  const handleExport = async () => {
    if (!activeDevice) {
      toast.error("Vui lòng chọn thiết bị trước");
      return;
    }
    const promise = userAPI.exportUsers();
    toast.promise(promise, {
      loading: "Đang xuất danh sách người dùng...",
      success: (data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `users_export_${activeDevice.name}_${new Date()
          .toISOString()
          .split("T")[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return "Xuất danh sách người dùng thành công!";
      },
      error: "Xuất danh sách người dùng thất bại",
    });
  };

  const handleImportDialogFileSelect = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result;
        if (typeof text === "string") {
          const data = JSON.parse(text);
          if (Array.isArray(data)) {
            setUsersToImportPreview(data);
          } else {
            toast.error("File JSON không hợp lệ: phải là một mảng người dùng.");
          }
        }
      } catch (err) {
        toast.error("Không thể đọc file. File JSON có lỗi.");
        console.error("Error parsing import file:", err);
      }
    };
    reader.readAsText(file);
  };

  const handleRemoveUserFromPreview = (userIdToRemove: string) => {
    setUsersToImportPreview((currentUsers) =>
      currentUsers.filter((user) => user.user_id !== userIdToRemove)
    );
  };

  const handleConfirmImport = async () => {
    if (usersToImportPreview.length === 0) {
        toast.error("Không có người dùng nào để nhập.");
        return;
    }

    setIsImporting(true);

    // Create a new File object from the potentially filtered preview data
    const filteredDataStr = JSON.stringify(usersToImportPreview, null, 2);
    const blob = new Blob([filteredDataStr], { type: "application/json" });
    const filteredFile = new File([blob], "filtered_import.json", { type: "application/json" });

    const formData = new FormData();
    formData.append("file", filteredFile);
    formData.append("exact_import", String(isExactImport));

    const promise = userAPI.importUsers(formData);
    toast.promise(promise, {
      loading: "Đang nhập danh sách người dùng...",
      success: (result) => {
        loadUsers();
        setIsImportDialogOpen(false);
        return `Nhập thành công: ${result.created} mới, ${result.updated} cập nhật, ${result.failed} lỗi.`;
      },
      error: (err) => {
        return err.response?.data?.error || "Nhập file thất bại";
      },
      finally: () => {
        setIsImporting(false);
      },
    });
  };

  const resetImportDialog = () => {
    setUsersToImportPreview([]);
    setIsExactImport(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const filteredUsers = users.filter((user) =>
    user.name.toLowerCase().includes(searchQuery.toLowerCase())
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

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
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
          {activeDevice?.device_type === "pull" && (
            <Button
              variant="outline"
              onClick={handleSyncUsersFromDevice}
              disabled={isSyncingFromDevice}
              className="flex items-center gap-2"
            >
              <RefreshCw
                className={`h-4 w-4 ${
                  isSyncingFromDevice ? "animate-spin" : ""
                }`}
              />
              {isSyncingFromDevice ? "Đang đồng bộ..." : "Đồng bộ từ thiết bị"}
            </Button>
          )}
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
          <Button
            variant="outline"
            onClick={handleExport}
            className="flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            Xuất file
          </Button>

          <Dialog
            open={isImportDialogOpen}
            onOpenChange={(isOpen) => {
              setIsImportDialogOpen(isOpen);
              if (!isOpen) {
                resetImportDialog();
              }
            }}
          >
            <DialogTrigger asChild>
              <Button variant="outline" className="flex items-center gap-2">
                <Upload className="h-4 w-4" />
                Nhập file
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-3xl">
              <DialogHeader>
                <DialogTitle>Nhập danh sách người dùng</DialogTitle>
                <DialogDescription>
                  Chọn một file JSON để xem trước và nhập vào hệ thống.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <FileJson className="h-4 w-4 mr-2" />
                  {usersToImportPreview.length > 0
                    ? "Chọn file khác"
                    : "Chọn file JSON"}
                </Button>

                {usersToImportPreview.length > 0 && (
                  <div className="space-y-4">
                    <div className="flex items-center space-x-2 mt-4">
                      <Switch
                        id="exact-import-switch"
                        checked={isExactImport}
                        onCheckedChange={setIsExactImport}
                      />
                      <Label htmlFor="exact-import-switch">
                        Nhập chính xác theo Serial Number
                      </Label>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Khi bật, hệ thống sẽ nhập người dùng vào thiết bị có `serial_number` trùng khớp trong file. Nếu không, người dùng sẽ được nhập vào thiết bị đang hoạt động.
                    </p>

                    <h4 className="font-semibold">
                      Xem trước dữ liệu ({usersToImportPreview.length} người dùng)
                    </h4>
                    <ScrollArea className="h-64 w-full rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>ID</TableHead>
                            <TableHead>Tên</TableHead>
                            <TableHead>Serial Number</TableHead>
                            <TableHead className="text-right">Hành động</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {usersToImportPreview.map((user) => (
                            <TableRow key={user.user_id}>
                              <TableCell>{user.user_id}</TableCell>
                              <TableCell>{user.name}</TableCell>
                              <TableCell className="text-muted-foreground">
                                {user.serial_number || "(trống)"}
                              </TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                                  onClick={() =>
                                    handleRemoveUserFromPreview(user.user_id)
                                  }
                                >
                                  <Minus className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsImportDialogOpen(false);
                    resetImportDialog();
                  }}
                >
                  Hủy
                </Button>
                <Button
                  onClick={handleConfirmImport}
                  disabled={usersToImportPreview.length === 0 || isImporting}
                >
                  {isImporting ? "Đang nhập..." : "Xác nhận nhập"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImportDialogFileSelect}
            className="hidden"
            accept=".json"
          />
        </div>
      </div>

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
                  <TableHead>ID</TableHead>
                  <TableHead>Họ tên</TableHead>
                  <TableHead>Họ tên hệ thống</TableHead>
                  <TableHead>Nhóm</TableHead>
                  <TableHead>Trạng thái đồng bộ</TableHead>
                  <TableHead>Đồng bộ lúc</TableHead>
                  <TableHead>Tạo lúc</TableHead>
                  <TableHead className="text-right">Hành động</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnimatePresence initial={false}>
                  {filteredUsers.map((user) => {
                    const initials = user.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .toUpperCase()
                      .slice(0, 2);

                    return (
                      <MotionTableRow
                        key={user.id}
                        layout
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -12 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                      >
                        <TableCell className="font-medium">{user.id}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              {user.avatar_url && (
                                <AvatarImage
                                  src={buildAvatarUrl(
                                    user.avatar_url,
                                    resourceDomain
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
                        <TableCell className="font-medium">
                          {user.full_name ?? "-"}
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
                              className={`h-4 w-4 ${
                                syncingUsers.has(user.id) ? "animate-spin" : ""
                              }`}
                            />
                          </Button>
                        </TableCell>
                      </MotionTableRow>
                    );
                  })}
                </AnimatePresence>
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

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
    </motion.div>
  );
}
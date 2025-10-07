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
        "Failed to load users. Make sure the backend service is running."
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
      toast.error("Please select a device first");
      return;
    }

    setIsSyncing(true);
    try {
      const result = await deviceAPI.syncEmployee();

      if (result["success"]) {
        toast.success(
          `Successfully synced ${result.employees_count} employees to external API`
        );
        // Reload users to get updated sync status
        await loadUsers();
      } else {
        toast.error(result.message);
      }

      console.log("Sync result:", result);
    } catch (err: any) {
      console.log(err);

      const errorMessage = err.message || "Failed to sync employees";
      toast.error(errorMessage);
      console.error("Error syncing employees:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSyncSingleUser = async (userId: string, userName: string) => {
    if (!activeDevice) {
      toast.error("Please select a device first");
      return;
    }

    setSyncingUsers((prev) => new Set(prev).add(userId));
    try {
      const result = await userAPI.syncUser(userId);

      if (result.success) {
        toast.success(`Successfully synced ${userName} to external API`);
        // Reload users to get updated sync status
        await loadUsers();
      } else {
        toast.error(result.message || "Failed to sync user");
      }
    } catch (err: any) {
      const errorMessage = err.message || "Failed to sync user";
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

  // Filter users based on search query
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
          Synced
        </Badge>
      );
    } else {
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 border-yellow-300"
        >
          <Clock className="h-3 w-3 mr-1" />
          Pending
        </Badge>
      );
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
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
            User Management
          </h2>
          <div className="flex items-center gap-4 mt-1">
            <p className="text-muted-foreground">
              Manage users and their access permissions
            </p>
            {syncStatus && (
              <div className="flex items-center gap-2">
                {deviceConnected ? (
                  <Badge
                    variant="default"
                    className="bg-green-100 text-green-800 border-green-300"
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Device Connected
                  </Badge>
                ) : (
                  <Badge
                    variant="secondary"
                    className="bg-orange-100 text-orange-800 border-orange-300"
                  >
                    <XCircle className="h-3 w-3 mr-1" />
                    Device Offline
                  </Badge>
                )}
                {syncStatus.success && syncStatus.synced_count > 0 && (
                  <Badge
                    variant="outline"
                    className="bg-blue-50 text-blue-800 border-blue-300"
                  >
                    +{syncStatus.synced_count} new users synced
                  </Badge>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleSyncEmployee}
            disabled={isSyncing}
            className="flex items-center gap-2"
          >
            <RefreshCw
              className={`h-4 w-4 ${isSyncing ? "animate-spin" : ""}`}
            />
            {isSyncing ? "Syncing..." : "Sync Employee"}
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
            placeholder="Search users by name..."
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
            Please select a device first to manage users. Go to Device
            Management to configure a device.
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
            Device sync failed: {syncStatus.error}. Showing data from database
            only.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCheck className="h-5 w-5" />
            Users ({filteredUsers.length})
          </CardTitle>
          <CardDescription>
            Current users registered in the system
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">Loading users...</div>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  {searchQuery
                    ? `No users found matching "${searchQuery}"`
                    : "No users found"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Click "Add User" to create the first user
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableCaption>
                User list from ZKTeco device with sync status
              </TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>STT</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Group</TableHead>
                  <TableHead>Sync Status</TableHead>
                  <TableHead>Synced At</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
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
                                src={buildAvatarUrl(user.avatar_url, resourceDomain)}
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
                          onClick={() => handleSyncSingleUser(user.id, user.name)}
                          disabled={syncingUsers.has(user.id)}
                          className="h-8 w-8 p-0"
                          title="Sync this user to external API"
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
            <CardTitle className="text-lg">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{users.length}</div>
            <p className="text-sm text-muted-foreground">Registered users</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Synced Users
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">
              {users.filter((user) => user.is_synced).length}
            </div>
            <p className="text-sm text-muted-foreground">
              Synced to external API
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-4 w-4 text-yellow-600" />
              Pending Sync
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-yellow-600">
              {users.filter((user) => !user.is_synced).length}
            </div>
            <p className="text-sm text-muted-foreground">Waiting to sync</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Administrators</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {users.filter((user) => user.privilege >= 2).length}
            </div>
            <p className="text-sm text-muted-foreground">Admin level users</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

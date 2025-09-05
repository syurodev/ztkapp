import { Alert, AlertDescription } from "@/components/ui/alert";
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
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { deviceAPI, userAPI } from "@/lib/api";
import { AlertCircle, Plus, RefreshCw, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

interface User {
  user_id: number;
  name: string;
  privilege: number;
  password?: string;
  group_id: number;
  card: number;
  fingerprints?: number[];
}

interface UserFormData {
  name: string;
  privilege: number;
  password: string;
  group_id: number;
  card: number;
}

const initialFormData: UserFormData = {
  name: "",
  privilege: 0,
  password: "",
  group_id: 0,
  card: 0,
};

export function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState<UserFormData>(initialFormData);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Load users on component mount
  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await userAPI.getUsers();
      console.log(response);
      const mappedUsers = response.data.map((user: any) => ({
        user_id: parseInt(user.id, 10),
        name: user.name,
        privilege: user.privilege || 0, // Assuming default privilege is 0
        group_id: parseInt(user.groupId, 10),
        card: user.card || 0, // Assuming default card is 0
      }));
      setUsers(mappedUsers || []);
    } catch (err) {
      setError(
        "Failed to load users. Make sure the backend service is running."
      );
      console.error("Error loading users:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!formData.name.trim()) {
      toast.error("User name is required");
      return;
    }

    setIsLoading(true);
    try {
      // Generate unique user_id
      const maxId = users.reduce((max, user) => Math.max(max, user.user_id), 0);
      const newUserId = maxId + 1;

      const userData = {
        user_id: newUserId,
        user_data: {
          name: formData.name,
          privilege: formData.privilege,
          password: formData.password || "123456", // Default password
          group_id: formData.group_id,
          card: formData.card || 0,
        },
      };

      await userAPI.createUser(userData);
      toast.success("User created successfully");
      setIsDialogOpen(false);
      setFormData(initialFormData);
      await loadUsers(); // Reload users
    } catch (err) {
      toast.error("Failed to create user");
      console.error("Error creating user:", err);
    } finally {
      setIsLoading(false);
    }
  };

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
    setIsSyncing(true);
    try {
      const result = await deviceAPI.syncEmployee();

      if (result["success"]) {
        toast.success(
          `Successfully synced ${result.employees_count} employees to external API`
        );
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

  // Filter users based on search query
  const filteredUsers = users.filter((user) =>
    user.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
          <p className="text-muted-foreground">
            Manage users and their access permissions
          </p>
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
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
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
          </Dialog>
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

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

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
              <TableCaption>User list from ZKTeco device</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>STT</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Group</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user, index) => {
                  return (
                    <TableRow key={user.user_id}>
                      <TableCell className="font-medium">{index + 1}</TableCell>
                      <TableCell className="font-medium">
                        {user.user_id}
                      </TableCell>
                      <TableCell>{user.name}</TableCell>
                      <TableCell>{user.group_id}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
            <CardTitle className="text-lg">Administrators</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {users.filter((user) => user.privilege >= 2).length}
            </div>
            <p className="text-sm text-muted-foreground">Admin level users</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">With Fingerprints</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {
                users.filter(
                  (user) => user.fingerprints && user.fingerprints.length > 0
                ).length
              }
            </div>
            <p className="text-sm text-muted-foreground">
              Users with biometric data
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

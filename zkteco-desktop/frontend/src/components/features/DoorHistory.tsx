import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DatePicker } from "@/components/ui/datepicker";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface Door {
  id: number;
  name: string;
  device_id: string | null;
}

interface Device {
  id: string;
  name: string;
  device_type?: "pull" | "push";
}

interface AccessLog {
  id: number;
  door_id: number;
  user_id: string;
  user_name: string;
  timestamp: string;
  action: string;
  status: string;
  notes: string;
}

export function DoorHistory() {
  const [doors, setDoors] = useState<Door[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDoor, setSelectedDoor] = useState<string>("");
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [startDate, setStartDate] = useState<Date | undefined>();
  const [endDate, setEndDate] = useState<Date | undefined>();
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const [doorsResponse, devicesResponse] = await Promise.all([
          api.get("/doors"),
          api.get("/devices"),
        ]);

        if (doorsResponse.data.success) {
          setDoors(doorsResponse.data.data);
        }

        if (devicesResponse.data.devices) {
          setDevices(devicesResponse.data.devices);
          console.log("Fetched devices:", devicesResponse.data.devices);
        }
      } catch (error) {
        toast.error("Failed to fetch initial data.");
      }
    };
    fetchInitialData();
  }, []);

  const handleDoorSelect = (doorId: string) => {
    const door = doors.find((d) => d.id.toString() === doorId);
    setSelectedDoor(doorId);
    console.log("Selected door:", door);

    if (door && door.device_id) {
      const device = devices.find((d) => d.id === door.device_id);
      setSelectedDevice(device || null);
      console.log("Found device:", device);
    } else {
      setSelectedDevice(null);
      console.log("No device associated with this door.");
    }
  };

  const handleViewHistory = async () => {
    if (!selectedDoor || !startDate || !endDate) {
      toast.warning("Please select a door and a date range.");
      return;
    }
    setLoading(true);
    try {
      const response = await api.get(`/doors/${selectedDoor}/access-logs`, {
        params: {
          start_date: startDate.toISOString().split("T")[0],
          end_date: endDate.toISOString().split("T")[0],
        },
      });
      if (response.data.success) {
        setLogs(response.data.data);
      }
    } catch (error) {
      toast.error("Failed to fetch door history.");
    } finally {
      setLoading(false);
    }
  };

  const handleSyncFromAttendance = async () => {
    if (!selectedDoor) {
      toast.warning("Please select a door first.");
      return;
    }
    setSyncLoading(true);
    try {
      const response = await api.post(
        `/doors/${selectedDoor}/sync-from-attendance`,
      );
      if (response.data.success) {
        toast.success(response.data.message);
        // Refresh the logs view
        if (startDate && endDate) {
          handleViewHistory();
        }
      }
    } catch (error) {
      toast.error("Failed to sync from attendance machine.");
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Door Access History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center space-x-4 mb-4">
          <Select onValueChange={handleDoorSelect} value={selectedDoor}>
            <SelectTrigger className="w-[280px]">
              <SelectValue placeholder="Select a door" />
            </SelectTrigger>
            <SelectContent>
              {doors.map((door) => (
                <SelectItem key={door.id} value={String(door.id)}>
                  {door.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DatePicker date={startDate} setDate={setStartDate} />
          <DatePicker date={endDate} setDate={setEndDate} />
          <Button onClick={handleViewHistory} disabled={loading}>
            {loading ? "Loading..." : "View History"}
          </Button>
          {selectedDevice?.device_type === "pull" && (
            <Button
              onClick={handleSyncFromAttendance}
              disabled={!selectedDoor || syncLoading}
              variant="outline"
            >
              {syncLoading ? "Syncing..." : "Lấy lịch sử từ máy"}
            </Button>
          )}
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User ID</TableHead>
              <TableHead>User Name</TableHead>
              <TableHead>Timestamp</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((log) => (
              <TableRow key={log.id}>
                <TableCell>{log.user_id}</TableCell>
                <TableCell>{log.user_name}</TableCell>
                <TableCell>
                  {new Date(log.timestamp).toLocaleString()}
                </TableCell>
                <TableCell>{log.action}</TableCell>
                <TableCell>{log.status}</TableCell>
                <TableCell>{log.notes}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

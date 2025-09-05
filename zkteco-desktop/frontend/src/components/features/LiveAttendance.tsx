import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { liveAPI } from "@/lib/api";
import { Activity, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

interface LiveAttendanceRecord {
  user_id: string;
  timestamp: string;
  status: number;
  punch: number;
}

const MAX_RECORDS = 50;

const STATUS_MAP: { [key: number]: string } = {
  0: "Check-in",
  1: "Check-out",
  2: "Break-out",
  3: "Break-in",
  4: "Overtime-in",
  5: "Overtime-out",
};

export function LiveAttendance() {
  const [liveAttendance, setLiveAttendance] = useState<LiveAttendanceRecord[]>(
    [],
  );
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const handleMessage = (newRecord: LiveAttendanceRecord) => {
      setLiveAttendance((prev) => [newRecord, ...prev].slice(0, MAX_RECORDS));
    };

    const handleError = () => {
      setIsConnected(false);
    };

    const handleOpen = () => {
      setIsConnected(true);
    };

    const cleanup = liveAPI.connect(handleMessage, handleError, handleOpen);

    return () => {
      cleanup();
    };
  }, []);

  const ConnectionIcon = isConnected ? Wifi : WifiOff;
  const connectionColor = isConnected ? "text-green-500" : "text-red-500";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-6 w-6" />
          Live Attendance Feed
          <span
            title={isConnected ? "Connected" : "Disconnected"}
            className="ml-auto"
          >
            <ConnectionIcon className={`h-5 w-5 ${connectionColor}`} />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User ID</TableHead>
              <TableHead>Timestamp</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Punch</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {liveAttendance.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="h-48 text-center text-muted-foreground"
                >
                  {isConnected
                    ? "Waiting for attendance events..."
                    : "Connecting to live feed..."}
                </TableCell>
              </TableRow>
            ) : (
              liveAttendance.map((record, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium">
                    {record.user_id}
                  </TableCell>
                  <TableCell>{record.timestamp}</TableCell>
                  <TableCell>
                    {STATUS_MAP[record.status] || "Unknown"}
                  </TableCell>
                  <TableCell>{record.punch}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

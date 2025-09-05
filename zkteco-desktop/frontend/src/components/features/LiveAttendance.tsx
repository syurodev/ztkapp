import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { useDevice } from "@/contexts/DeviceContext";
import { Activity, Monitor, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

interface LiveAttendanceRecord {
  user_id: string;
  timestamp: string;
  status: number;
  punch: number;
}

const MAX_RECORDS = 50;

// Map for attendance method (what the 'status' field represents)
const ATTENDANCE_METHOD_MAP: { [key: number]: string } = {
  1: "Fingerprint",
  4: "Card",
};

// Map for punch action (what the 'punch' field represents) 
const PUNCH_ACTION_MAP: { [key: number]: string } = {
  0: "Check-in",
  1: "Check-out",
  2: "Overtime Start",
  3: "Overtime End",
  4: "Unspecified",
};

export function LiveAttendance() {
  const { activeDevice } = useDevice();
  const [liveAttendance, setLiveAttendance] = useState<LiveAttendanceRecord[]>(
    [],
  );
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!activeDevice) {
      setLiveAttendance([]);
      setIsConnected(false);
      return;
    }

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
  }, [activeDevice]);

  const ConnectionIcon = isConnected ? Wifi : WifiOff;
  const connectionColor = isConnected ? "text-green-500" : "text-red-500";

  return (
    <div className="space-y-6">
      {/* No Device Selected Alert */}
      {!activeDevice && (
        <Alert>
          <Monitor className="h-4 w-4" />
          <AlertDescription>
            Please select a device first to view live attendance. Go to Device Management to configure a device.
          </AlertDescription>
        </Alert>
      )}
      
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-6 w-6" />
            Live Attendance Feed
            {activeDevice && (
              <span
                title={isConnected ? "Connected" : "Disconnected"}
                className="ml-auto"
              >
                <ConnectionIcon className={`h-5 w-5 ${connectionColor}`} />
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!activeDevice ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Monitor className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  No device selected
                </p>
                <p className="text-sm text-muted-foreground">
                  Select a device to view live attendance feed
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Action</TableHead>
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
                        {ATTENDANCE_METHOD_MAP[record.status] || "Unknown"}
                      </TableCell>
                      <TableCell>
                        {PUNCH_ACTION_MAP[record.punch] || "Unknown"}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

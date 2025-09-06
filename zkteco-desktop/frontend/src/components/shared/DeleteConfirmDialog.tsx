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
import { Device } from "@/lib/api";
import { AlertTriangle, Monitor, Trash2 } from "lucide-react";

interface DeleteConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device: Device | null;
  onConfirm: () => void;
  isLoading?: boolean;
  isActiveDevice?: boolean;
}

export function DeleteConfirmDialog({
  open,
  onOpenChange,
  device,
  onConfirm,
  isLoading = false,
  isActiveDevice = false,
}: DeleteConfirmDialogProps) {
  if (!device) return null;

  const handleConfirm = () => {
    onConfirm();
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
              <Trash2 className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <AlertDialogTitle className="text-lg font-semibold">
                Delete Device
              </AlertDialogTitle>
              <AlertDialogDescription className="text-sm text-muted-foreground">
                This action cannot be undone
              </AlertDialogDescription>
            </div>
          </div>
        </AlertDialogHeader>

        <div className="space-y-4">
          {/* Device Info Card */}
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-3 mb-3">
              <Monitor className="h-5 w-5 text-gray-600" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{device.name}</span>
                  {isActiveDevice && (
                    <Badge variant="default" className="bg-teal-400">
                      Active
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-gray-600">
                  {device.ip}:{device.port}
                </p>
              </div>
            </div>

            {device.device_info?.serial_number && (
              <div className="text-xs text-gray-500">
                Serial: {device.device_info.serial_number}
              </div>
            )}
          </div>

          {/* Warning Message */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-yellow-50 border border-yellow-200">
            <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-yellow-800">
                Are you sure you want to delete this device?
              </p>
              <p className="text-yellow-700 mt-1">
                This will permanently remove the device configuration and
                disconnect any active connections.
                {isActiveDevice && (
                  <span className="block mt-1 font-medium">
                    ⚠️ This is your active device. You'll need to activate
                    another device after deletion.
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>

        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel disabled={isLoading} className="flex-1">
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isLoading}
            className="flex-1 bg-red-600 hover:bg-red-700 focus:ring-red-600"
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Deleting...
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Trash2 className="h-4 w-4" />
                Delete Device
              </div>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

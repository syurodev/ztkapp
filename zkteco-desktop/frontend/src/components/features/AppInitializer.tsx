import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

interface AppInitializerProps {
  children: React.ReactNode;
}

export function AppInitializer({ children }: AppInitializerProps) {
  const { isBackendRunning, isStarting, error } = useBackendHealth();
  const [initializationComplete, setInitializationComplete] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const initializeApp = async () => {
      try {
        // If backend is already running, finish immediately
        if (isBackendRunning) {
          setInitializationComplete(true);
          setInitError(null);
          return;
        }

        // Wait a moment for the initial health check to complete
        await new Promise((resolve) => setTimeout(resolve, 1000));

        if (!mounted) return;

        if (isBackendRunning) {
          setInitializationComplete(true);
          setInitError(null);
          return;
        }

        if (error) {
          setInitError(error);
          return;
        }

        // Keep showing the loading screen while waiting for backend to come up
        setInitializationComplete(false);
        setInitError(null);
      } catch (err) {
        if (!mounted) return;

        console.error("App initialization failed:", err);
        setInitError(
          err instanceof Error ? err.message : "Initialization failed"
        );
      }
    };

    initializeApp();

    return () => {
      mounted = false;
    };
  }, [isBackendRunning, error]);

  // Show initialization screen while backend is starting or not ready
  if (
    !initializationComplete ||
    isStarting ||
    (!isBackendRunning && !error && !initError)
  ) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
            </div>
            <CardTitle>Đang khởi tạo HAO HOA Time Clock</CardTitle>
            <CardDescription>
              Đang chuẩn bị ứng dụng và khởi động các dịch vụ...
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>
                {isStarting
                  ? "Đang khởi động dịch vụ backend..."
                  : "Đang kiểm tra trạng thái backend..."}
              </span>
            </div>

            <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
              <div
                className="bg-primary h-full transition-all duration-1000 ease-out"
                style={{
                  width: isStarting ? "75%" : isBackendRunning ? "100%" : "25%",
                }}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show error screen if initialization failed
  if (initError || (error && !isBackendRunning)) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/20">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
            <CardTitle className="text-red-600">
              Khởi tạo thất bại
            </CardTitle>
            <CardDescription>
              Không thể khởi động ứng dụng HAO HOA Time Clock
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertDescription>
                {initError || error || "Đã xảy ra lỗi không xác định"}
              </AlertDescription>
            </Alert>

            <Button
              onClick={() => window.location.reload()}
              className="w-full"
              variant="outline"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Thử khởi động lại
            </Button>

            <div className="text-xs text-muted-foreground space-y-1">
              <p>
                <strong>Hướng dẫn xử lý:</strong>
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Kiểm tra file thực thi backend đã tồn tại hay chưa</li>
                <li>Đảm bảo cổng 57575 đang trống</li>
                <li>Kiểm tra quyền truy cập hệ thống</li>
                <li>Xem lại nhật ký ứng dụng</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render main application if initialization is complete
  return <>{children}</>;
}

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { configAPI, settingsAPI, cleanupAPI } from "@/lib/api";
import { clearResourceDomainCache } from "@/lib/utils";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTray } from "../../contexts/TrayContext";
import { AlertCircle, Database, Info, Trash2 } from "lucide-react";

export function Settings() {
  const [apiGatewayDomain, setApiGatewayDomain] = useState("");
  const [externalApiKey, setExternalApiKey] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { minimizeToTray, toggleMinimizeToTray } = useTray();
  const normalizedDisplayDomain = (apiGatewayDomain || "<domain>").replace(/\/$/, "");

  // Cleanup settings
  const [retentionDays, setRetentionDays] = useState(365);
  const [cleanupEnabled, setCleanupEnabled] = useState(true);
  const [cleanupPreview, setCleanupPreview] = useState<any>(null);
  const [showCleanupDialog, setShowCleanupDialog] = useState(false);
  const [isCleanupLoading, setIsCleanupLoading] = useState(false);

  useEffect(() => {
    loadConfig();
    loadCleanupConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const config = await configAPI.getConfig();
      setApiGatewayDomain(config.API_GATEWAY_DOMAIN || "");
      setExternalApiKey(config.EXTERNAL_API_KEY || "");
    } catch (err: any) {
      console.error("Error loading settings:", err);

      // Only show error toast for actual server errors (5xx) or network issues
      const status = err.status || err.response?.status;

      if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error')) {
        toast.error("Không thể kết nối tới máy chủ. Vui lòng kiểm tra dịch vụ backend.");
      } else if (status >= 500) {
        toast.error("Máy chủ gặp lỗi khi tải cấu hình. Vui lòng thử lại.");
      }
      // For empty/default config, don't show toast error as it's a normal state
    } finally {
      setIsLoading(false);
    }
  };

  const loadCleanupConfig = async () => {
    try {
      const response = await settingsAPI.getCleanupConfig();
      if (response.success) {
        setRetentionDays(response.data.retention_days || 365);
        setCleanupEnabled(response.data.enabled !== false);
      }
    } catch (err) {
      console.error("Error loading cleanup config:", err);
    }
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await configAPI.updateConfig({
        API_GATEWAY_DOMAIN: apiGatewayDomain,
        EXTERNAL_API_KEY: externalApiKey,
      });
      // Clear resource domain cache to pick up new value
      clearResourceDomainCache();
      toast.success("Đã lưu cấu hình thành công");
    } catch (err) {
      toast.error("Không thể lưu cấu hình");
      console.error("Error saving settings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveCleanupConfig = async () => {
    setIsCleanupLoading(true);
    try {
      await settingsAPI.updateCleanupConfig({
        retention_days: retentionDays,
        enabled: cleanupEnabled,
      });
      toast.success("Đã lưu cấu hình dọn dẹp thành công");
    } catch (err: any) {
      toast.error(err.message || "Không thể lưu cấu hình dọn dẹp");
      console.error("Error saving cleanup config:", err);
    } finally {
      setIsCleanupLoading(false);
    }
  };

  const handlePreviewCleanup = async () => {
    setIsCleanupLoading(true);
    try {
      const response = await cleanupAPI.previewCleanup(retentionDays);
      if (response.success) {
        setCleanupPreview(response);
        setShowCleanupDialog(true);
      }
    } catch (err: any) {
      toast.error(err.message || "Không thể xem trước dọn dẹp");
      console.error("Error previewing cleanup:", err);
    } finally {
      setIsCleanupLoading(false);
    }
  };

  const handleExecuteCleanup = async () => {
    setIsCleanupLoading(true);
    try {
      const response = await cleanupAPI.executeCleanup(retentionDays);
      if (response.success) {
        const deleted = response.data.deleted_count || 0;
        toast.success(`Đã xoá ${deleted.toLocaleString()} bản ghi cũ`);
        setShowCleanupDialog(false);
        setCleanupPreview(null);
      }
    } catch (err: any) {
      toast.error(err.message || "Không thể thực hiện dọn dẹp");
      console.error("Error executing cleanup:", err);
    } finally {
      setIsCleanupLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Cài đặt</h1>
        <p className="text-muted-foreground">
          Thiết lập cấu hình chung cho ứng dụng
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cấu hình API bên ngoài</CardTitle>
          <p className="text-sm text-muted-foreground">
            Thiết lập API bên ngoài cho việc đồng bộ nhân sự và tài nguyên
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="domain">Tên miền API Gateway</Label>
            <Input
              id="domain"
              placeholder="https://beta.api.gateway.daihy.ohqsoft.com"
              value={apiGatewayDomain}
              onChange={(e) => setApiGatewayDomain(e.target.value)}
            />
            <p className="text-sm text-muted-foreground mt-1">
              Sử dụng một tên miền chung cho cả API (`/api/v1`) và tài nguyên (`/short`).
            </p>
            <p className="text-sm text-muted-foreground">
              Ví dụ endpoint API: {normalizedDisplayDomain}/api/v1
            </p>
            <p className="text-sm text-muted-foreground">
              Ví dụ endpoint tài nguyên: {normalizedDisplayDomain}/short
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              type="password"
              placeholder="Nhập API key"
              value={externalApiKey}
              onChange={(e) => setExternalApiKey(e.target.value)}
            />
            <p className="text-sm text-muted-foreground mt-1">
              Khóa xác thực để truy cập API bên ngoài
            </p>
          </div>

          <div className="pt-4">
            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? "Đang lưu..." : "Lưu cấu hình"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hành vi ứng dụng</CardTitle>
          <p className="text-sm text-muted-foreground">
            Thiết lập cách ứng dụng xử lý khi đóng cửa sổ
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="minimize-to-tray">Thu nhỏ xuống khay hệ thống</Label>
              <p className="text-sm text-muted-foreground">
                Khi bật, thao tác đóng cửa sổ sẽ thu nhỏ ứng dụng xuống khay hệ thống thay vì thoát hẳn
              </p>
            </div>
            <Switch
              id="minimize-to-tray"
              checked={minimizeToTray}
              onCheckedChange={toggleMinimizeToTray}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hướng dẫn khay hệ thống</CardTitle>
          <p className="text-sm text-muted-foreground">
            Cách sử dụng chức năng khay hệ thống
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>• Nhấp chuột phải vào biểu tượng khay để mở danh sách tùy chọn</p>
            <p>
              • Nhấp chuột trái vào biểu tượng khay để ẩn/hiện cửa sổ ứng dụng
            </p>
            <p>
              • Ứng dụng vẫn chạy nền khi được thu nhỏ xuống khay
            </p>
            <p>
              • Chọn "Thoát" trong menu khay để đóng ứng dụng hoàn toàn
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Dọn dẹp dữ liệu chấm công
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Tự động xoá dữ liệu chấm công cũ đã đồng bộ để giữ database gọn nhẹ
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Info className="h-4 w-4" />
            <AlertTitle>Lưu ý an toàn</AlertTitle>
            <AlertDescription>
              Dọn dẹp CHỈ xoá dữ liệu đã đồng bộ (synced) và bỏ qua (skipped).
              Dữ liệu chưa đồng bộ (pending) KHÔNG BAO GIỜ bị xoá.
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <Label htmlFor="retention-days">Thời gian lưu trữ (ngày)</Label>
            <Input
              id="retention-days"
              type="number"
              min="30"
              max="3650"
              value={retentionDays}
              onChange={(e) => setRetentionDays(parseInt(e.target.value) || 365)}
            />
            <p className="text-sm text-muted-foreground">
              Dữ liệu cũ hơn {retentionDays} ngày sẽ bị xoá. Tối thiểu 30 ngày.
            </p>
            <p className="text-sm text-muted-foreground">
              Khuyến nghị: 365 ngày (1 năm) hoặc 730 ngày (2 năm)
            </p>
          </div>

          <div className="flex items-center justify-between py-2">
            <div className="space-y-0.5">
              <Label htmlFor="cleanup-enabled">Tự động dọn dẹp hàng tháng</Label>
              <p className="text-sm text-muted-foreground">
                Chạy vào ngày 1 hàng tháng lúc 2:00 AM
              </p>
            </div>
            <Switch
              id="cleanup-enabled"
              checked={cleanupEnabled}
              onCheckedChange={setCleanupEnabled}
            />
          </div>

          <div className="flex gap-2 pt-4">
            <Button
              onClick={handleSaveCleanupConfig}
              disabled={isCleanupLoading}
              variant="default"
            >
              {isCleanupLoading ? "Đang lưu..." : "Lưu cấu hình"}
            </Button>
            <Button
              onClick={handlePreviewCleanup}
              disabled={isCleanupLoading}
              variant="outline"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Xem trước dọn dẹp
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Quản lý thiết bị</CardTitle>
          <p className="text-sm text-muted-foreground">
            Quản lý thiết bị ZKTeco tại trang Quản lý thiết bị
          </p>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <p className="text-muted-foreground mb-4">
              Các cài đặt riêng cho thiết bị được quản lý tại mục Quản lý thiết bị.
            </p>
            <Button
              variant="outline"
              onClick={() => (window.location.href = "/devices")}
            >
              Mở trang Quản lý thiết bị
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Cleanup Preview Dialog */}
      <Dialog open={showCleanupDialog} onOpenChange={setShowCleanupDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Xem trước dọn dẹp dữ liệu</DialogTitle>
            <DialogDescription>
              Kiểm tra trước khi xoá dữ liệu
            </DialogDescription>
          </DialogHeader>

          {cleanupPreview && (
            <div className="space-y-4">
              <Alert variant="default">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Sẽ xoá {cleanupPreview.records_to_delete?.toLocaleString()} bản ghi</AlertTitle>
                <AlertDescription>
                  Giữ lại {cleanupPreview.records_to_keep?.toLocaleString()} bản ghi
                </AlertDescription>
              </Alert>

              <div className="grid grid-cols-2 gap-4 p-4 bg-muted rounded-lg">
                <div>
                  <p className="text-sm font-medium">Thời gian lưu trữ</p>
                  <p className="text-2xl font-bold">{cleanupPreview.retention_days} ngày</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Ngày cắt</p>
                  <p className="text-sm text-muted-foreground">
                    {cleanupPreview.cutoff_date ? new Date(cleanupPreview.cutoff_date).toLocaleDateString('vi-VN') : 'N/A'}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold">Chi tiết xoá:</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Đã đồng bộ (synced):</span>
                    <span className="font-medium">{cleanupPreview.breakdown?.synced?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Bỏ qua (skipped):</span>
                    <span className="font-medium">{cleanupPreview.breakdown?.skipped?.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold">Trạng thái hiện tại:</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Tổng:</span>
                    <span className="font-medium">{cleanupPreview.current_stats?.total_records?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Pending:</span>
                    <span className="font-medium text-orange-600">{cleanupPreview.current_stats?.pending?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Synced:</span>
                    <span className="font-medium">{cleanupPreview.current_stats?.synced?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 bg-muted rounded">
                    <span>Skipped:</span>
                    <span className="font-medium">{cleanupPreview.current_stats?.skipped?.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Cảnh báo</AlertTitle>
                <AlertDescription>
                  Thao tác này KHÔNG THỂ hoàn tác. Dữ liệu đã xoá sẽ không thể khôi phục.
                </AlertDescription>
              </Alert>

              <div className="flex gap-2 justify-end pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowCleanupDialog(false)}
                  disabled={isCleanupLoading}
                >
                  Huỷ
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleExecuteCleanup}
                  disabled={isCleanupLoading}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  {isCleanupLoading ? "Đang xoá..." : "Xác nhận xoá"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

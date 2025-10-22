import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { configAPI, settingsAPI, cleanupAPI, devicesAPI } from "@/lib/api";
import { clearResourceDomainCache } from "@/lib/utils";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTray } from "../../contexts/TrayContext";
import { AlertCircle, Database, Info, Trash2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function Settings() {
  const [apiGatewayDomain, setApiGatewayDomain] = useState("");
  const [externalApiKey, setExternalApiKey] = useState("");
  const [resourceDomain, setResourceDomain] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { minimizeToTray, toggleMinimizeToTray } = useTray();

  // Branch settings
  const [branches, setBranches] = useState<{ id: number; name: string }[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<string>("");

  // Cleanup settings
  const [retentionDays, setRetentionDays] = useState(365);
  const [cleanupEnabled, setCleanupEnabled] = useState(true);
  const [cleanupPreview, setCleanupPreview] = useState<any>(null);
  const [showCleanupDialog, setShowCleanupDialog] = useState(false);
  const [isCleanupLoading, setIsCleanupLoading] = useState(false);

  useEffect(() => {
    loadConfig();
    loadCleanupConfig();
    loadBranchSettings();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const config = await configAPI.getConfig();
      setApiGatewayDomain(config.API_GATEWAY_DOMAIN || "");
      setExternalApiKey(config.EXTERNAL_API_KEY || "");
      setResourceDomain(config.RESOURCE_DOMAIN || "");
    } catch (err: any) {
      console.error("Error loading settings:", err);
      const status = err.status || err.response?.status;
      if (
        err.code === "ECONNREFUSED" ||
        err.message?.includes("Network Error")
      ) {
        toast.error(
          "Không thể kết nối tới máy chủ. Vui lòng kiểm tra dịch vụ backend.",
        );
      } else if (status >= 500) {
        toast.error("Máy chủ gặp lỗi khi tải cấu hình. Vui lòng thử lại.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadBranchSettings = async () => {
    try {
      const branchResponse = await devicesAPI.getBranches();
      if (branchResponse.status === 200) {
        setBranches(branchResponse.data || []);
      } else {
        // Even if mocked, there might be an issue. Log it.
        console.error("Branch API did not return status 200:", branchResponse);
        toast.error(
          `Lỗi tải danh sách chi nhánh: ${branchResponse.message || "Unknown error"}`,
        );
      }
    } catch (err) {
      console.error("Error fetching branches:", err);
      toast.error("Không thể gọi API lấy danh sách chi nhánh.");
    }

    try {
      const settingResponse = await settingsAPI.getSetting("ACTIVE_BRANCH_ID");
      if (settingResponse.success) {
        setSelectedBranchId(settingResponse.data.value || "");
      } else {
        // Handle cases where success is false, even if it's a 200 OK
        console.warn(
          "Could not retrieve ACTIVE_BRANCH_ID setting:",
          settingResponse.error,
        );
        // This is not a critical error, so we don't show a toast.
      }
    } catch (err) {
      console.error("Error fetching active branch setting:", err);
      // This is also not critical for the initial load, so no toast.
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
        RESOURCE_DOMAIN: resourceDomain,
      });
      clearResourceDomainCache(resourceDomain);
      toast.success("Đã lưu cấu hình thành công");
    } catch (err) {
      toast.error("Không thể lưu cấu hình");
      console.error("Error saving settings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBranchChange = async (newBranchId: string) => {
    setSelectedBranchId(newBranchId);
    try {
      await settingsAPI.updateSetting(
        "ACTIVE_BRANCH_ID",
        newBranchId,
        "Active Branch ID",
      );
      toast.success("Đã cập nhật chi nhánh hoạt động.");
    } catch (err) {
      toast.error("Không thể lưu cài đặt chi nhánh.");
      console.error("Error saving branch setting:", err);
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
              Sử dụng một tên miền chung cho cả API (`/api/v1`) và tài nguyên
              (`/short`).
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
          </div>

          <div className="space-y-2">
            <Label htmlFor="resource-domain">Tên miền tài nguyên</Label>
            <Input
              id="resource-domain"
              placeholder="https://beta.api.gateway.daihy.ohqsoft.com/short"
              value={resourceDomain}
              onChange={(e) => setResourceDomain(e.target.value)}
            />
            <p className="text-sm text-muted-foreground mt-1">
              Để trống để sử dụng mặc định `{apiGatewayDomain}/short`.
            </p>
          </div>

          <div className="pt-4">
            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? "Đang lưu..." : "Lưu cấu hình API"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cấu hình Chi nhánh</CardTitle>
          <p className="text-sm text-muted-foreground">
            Chọn chi nhánh mà ứng dụng này đang hoạt động
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Chi nhánh hoạt động</Label>
            <Select value={selectedBranchId} onValueChange={handleBranchChange}>
              <SelectTrigger>
                <SelectValue placeholder="Chọn một chi nhánh..." />
              </SelectTrigger>
              <SelectContent>
                {branches.map((branch) => (
                  <SelectItem key={branch.id} value={String(branch.id)}>
                    {branch.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Chi nhánh được chọn sẽ được sử dụng cho các hoạt động liên quan.
            </p>
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
              <Label htmlFor="minimize-to-tray">
                Thu nhỏ xuống khay hệ thống
              </Label>
              <p className="text-sm text-muted-foreground">
                Khi bật, thao tác đóng cửa sổ sẽ thu nhỏ ứng dụng xuống khay hệ
                thống thay vì thoát hẳn
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
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>
              • Nhấp chuột phải vào biểu tượng khay để mở danh sách tùy chọn
            </p>
            <p>
              • Nhấp chuột trái vào biểu tượng khay để ẩn/hiện cửa sổ ứng dụng
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
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Info className="h-4 w-4" />
            <AlertTitle>Lưu ý an toàn</AlertTitle>
            <AlertDescription>
              Dọn dẹp CHỈ xoá dữ liệu đã đồng bộ (synced) và bỏ qua (skipped).
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
              onChange={(e) =>
                setRetentionDays(parseInt(e.target.value) || 365)
              }
            />
          </div>

          <div className="flex items-center justify-between py-2">
            <div className="space-y-0.5">
              <Label htmlFor="cleanup-enabled">
                Tự động dọn dẹp hàng tháng
              </Label>
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
              {isCleanupLoading ? "Đang lưu..." : "Lưu cấu hình dọn dẹp"}
            </Button>
            <Button
              onClick={handlePreviewCleanup}
              disabled={isCleanupLoading}
              variant="outline"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Xem trước
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Cleanup Preview Dialog */}
      <Dialog open={showCleanupDialog} onOpenChange={setShowCleanupDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Xem trước dọn dẹp dữ liệu</DialogTitle>
          </DialogHeader>

          {cleanupPreview && (
            <div className="space-y-4">
              <Alert variant="default">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>
                  Sẽ xoá {cleanupPreview.records_to_delete?.toLocaleString()}{" "}
                  bản ghi
                </AlertTitle>
              </Alert>

              <div className="grid grid-cols-2 gap-4 p-4 bg-muted rounded-lg">
                <div>
                  <p className="text-sm font-medium">Thời gian lưu trữ</p>
                  <p className="text-2xl font-bold">
                    {cleanupPreview.retention_days} ngày
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium">Ngày cắt</p>
                  <p className="text-sm text-muted-foreground">
                    {cleanupPreview.cutoff_date
                      ? new Date(cleanupPreview.cutoff_date).toLocaleDateString(
                          "vi-VN",
                        )
                      : "N/A"}
                  </p>
                </div>
              </div>

              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Cảnh báo</AlertTitle>
                <AlertDescription>
                  Thao tác này KHÔNG THỂ hoàn tác.
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

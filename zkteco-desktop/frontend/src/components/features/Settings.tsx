import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { configAPI } from "@/lib/api";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTray } from "../../contexts/TrayContext";

export function Settings() {
  const [externalApiDomain, setExternalApiDomain] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { minimizeToTray, toggleMinimizeToTray } = useTray();

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const config = await configAPI.getConfig();
      setExternalApiDomain(config.EXTERNAL_API_DOMAIN || "");
    } catch (err: any) {
      console.error("Error loading settings:", err);
      
      // Only show error toast for actual server errors (5xx) or network issues
      const status = err.status || err.response?.status;
      
      if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error')) {
        toast.error("Cannot connect to server. Please check if the backend is running.");
      } else if (status >= 500) {
        toast.error("Server error while loading settings. Please try again.");
      }
      // For empty/default config, don't show toast error as it's a normal state
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await configAPI.updateConfig({
        EXTERNAL_API_DOMAIN: externalApiDomain,
      });
      toast.success("Settings saved successfully");
    } catch (err) {
      toast.error("Failed to save settings");
      console.error("Error saving settings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Settings</h1>
        <p className="text-muted-foreground">
          Configure global application settings
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>External API Configuration</CardTitle>
          <p className="text-sm text-muted-foreground">
            Configure the external API for employee synchronization
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="domain">API Domain</Label>
            <Input
              id="domain"
              placeholder="https://api.example.com"
              value={externalApiDomain}
              onChange={(e) => setExternalApiDomain(e.target.value)}
            />
            <p className="text-sm text-muted-foreground mt-1">
              The base URL for your external API (e.g.,
              https://api.yourcompany.com)
            </p>
          </div>

          <div className="pt-4">
            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application Behavior</CardTitle>
          <p className="text-sm text-muted-foreground">
            Configure how the application behaves when closing
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="minimize-to-tray">Minimize to System Tray</Label>
              <p className="text-sm text-muted-foreground">
                When enabled, closing the window will minimize the app to the
                system tray instead of quitting
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
          <CardTitle>System Tray Information</CardTitle>
          <p className="text-sm text-muted-foreground">
            How to use the system tray functionality
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>• Right-click on the tray icon to access menu options</p>
            <p>
              • Left-click on the tray icon to show/hide the application window
            </p>
            <p>
              • The application will continue running in the background when
              minimized to tray
            </p>
            <p>
              • Use "Quit" from the tray menu to completely exit the application
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Device Management</CardTitle>
          <p className="text-sm text-muted-foreground">
            Manage your ZKTeco devices from the Device Management page
          </p>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <p className="text-muted-foreground mb-4">
              Device-specific settings are now managed in the Device Management
              section.
            </p>
            <Button
              variant="outline"
              onClick={() => (window.location.href = "/devices")}
            >
              Go to Device Management
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

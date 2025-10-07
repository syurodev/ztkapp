import { DeviceSelector } from "@/components/shared/DeviceSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { cn } from "@/lib/utils";
import {
  Activity,
  CheckCircle,
  Circle,
  Clock,
  FileText,
  Loader2,
  Menu,
  Monitor,
  Server,
  Settings,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

interface AppLayoutProps {
  children: React.ReactNode;
}

interface NavItem {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { title: "Service Status", icon: Server, href: "/", badge: "running" },
  { title: "Device Management", icon: Monitor, href: "/devices" },
  { title: "User Management", icon: Users, href: "/users" },
  { title: "Attendance", icon: Clock, href: "/attendance" },
  { title: "Live Attendance", icon: Activity, href: "/live-attendance" },
  { title: "Logs", icon: FileText, href: "/logs" },
  { title: "Settings", icon: Settings, href: "/settings" },
];

export function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { isBackendRunning, isStarting, error, startBackend } =
    useBackendHealth();
  const location = useLocation();
  const navigate = useNavigate();

  // Derive status from backend health
  const serviceStatus = isStarting
    ? "starting"
    : error
    ? "error"
    : isBackendRunning
    ? "running"
    : "stopped";

  const getStatusIcon = () => {
    if (isStarting) {
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    }

    switch (serviceStatus) {
      case "running":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "stopped":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "error":
        return <Circle className="h-4 w-4 text-yellow-500" />;
      default:
        return <Circle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    if (isStarting) {
      return "bg-blue-500";
    }

    switch (serviceStatus) {
      case "running":
        return "bg-green-500";
      case "stopped":
        return "bg-red-500";
      case "error":
        return "bg-yellow-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusText = () => {
    if (isStarting) return "starting";
    if (error) return "error";
    return isBackendRunning ? "running" : "stopped";
  };

  return (
    <div className="h-screen flex bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          "bg-card border-r border-border transition-all duration-300 ease-in-out",
          sidebarOpen ? "w-64" : "w-16"
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              {sidebarOpen && (
                <div>
                  <h1 className="text-lg font-semibold">HAO HOA Time Clock</h1>
                  <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <div
                      className={cn("w-2 h-2 rounded-full", getStatusColor())}
                    />
                    Service {getStatusText()}
                  </div>
                </div>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="h-8 w-8 p-0"
            >
              {sidebarOpen ? (
                <X className="h-4 w-4" />
              ) : (
                <Menu className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 p-2">
          <nav className="space-y-1">
            {navItems.map((item) => {
              const IconComponent = item.icon;
              const isActive = location.pathname === item.href;

              return (
                <Button
                  key={item.href}
                  variant={isActive ? "secondary" : "ghost"}
                  className={cn(
                    "w-full justify-start h-10",
                    !sidebarOpen && "justify-center px-2"
                  )}
                  onClick={() => navigate(item.href)}
                >
                  <IconComponent className="h-4 w-4" />
                  {sidebarOpen && (
                    <span className="ml-2 flex-1 text-left">{item.title}</span>
                  )}
                  {sidebarOpen && item.badge && (
                    <Badge variant="secondary" className="ml-auto">
                      {item.badge}
                    </Badge>
                  )}
                </Button>
              );
            })}
          </nav>
        </ScrollArea>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="bg-card border-b border-border p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">
              {navItems.find((item) => item.href === location.pathname)
                ?.title || "Dashboard"}
            </h2>
            <div className="flex items-center space-x-3">
              <DeviceSelector />
              <Badge
                variant="outline"
                className={cn(
                  "flex items-center gap-1 cursor-pointer transition-colors",
                  !isBackendRunning &&
                    !isStarting &&
                    "hover:bg-red-50 hover:border-red-300"
                )}
                onClick={
                  !isBackendRunning && !isStarting ? startBackend : undefined
                }
                title={
                  !isBackendRunning && !isStarting
                    ? "Click to start backend"
                    : undefined
                }
              >
                <div className={cn("w-2 h-2 rounded-full", getStatusColor())} />
                Backend Service
                {!isBackendRunning && !isStarting && (
                  <span className="text-xs ml-1">(click to start)</span>
                )}
              </Badge>
              <ThemeToggle />
            </div>
          </div>
        </div>

        {/* Page Content */}
        <div className="flex-1 p-6 overflow-auto">{children}</div>
      </div>
    </div>
  );
}

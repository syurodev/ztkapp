import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { DeviceSelector } from "@/components/shared/DeviceSelector";
import { cn } from "@/lib/utils";
import {
  Activity,
  CheckCircle,
  Circle,
  Clock,
  FileText,
  Fingerprint,
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
  { title: "Fingerprint", icon: Fingerprint, href: "/fingerprints" },
  { title: "Settings", icon: Settings, href: "/settings" },
  { title: "Logs", icon: FileText, href: "/logs" },
];

export function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [serviceStatus, _] = useState<"running" | "stopped" | "error">(
    "running",
  );
  const location = useLocation();
  const navigate = useNavigate();

  const getStatusIcon = () => {
    switch (serviceStatus) {
      case "running":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "stopped":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "error":
        return <Circle className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusColor = () => {
    switch (serviceStatus) {
      case "running":
        return "bg-green-500";
      case "stopped":
        return "bg-red-500";
      case "error":
        return "bg-yellow-500";
    }
  };

  return (
    <div className="h-screen flex bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          "bg-card border-r border-border transition-all duration-300 ease-in-out",
          sidebarOpen ? "w-64" : "w-16",
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              {sidebarOpen && (
                <div>
                  <h1 className="text-lg font-semibold">ZKTeco Manager</h1>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <div
                      className={cn("w-2 h-2 rounded-full", getStatusColor())}
                    />
                    Service {serviceStatus}
                  </p>
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
                    !sidebarOpen && "justify-center px-2",
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
              <Badge variant="outline" className="flex items-center gap-1">
                <div className={cn("w-2 h-2 rounded-full", getStatusColor())} />
                Backend Service
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

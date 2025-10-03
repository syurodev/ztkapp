import { useBackendHealth } from "@/hooks/useBackendHealth";
import { useEffect, useState } from "react";
import { Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface AppInitializerProps {
  children: React.ReactNode;
}

export function AppInitializer({ children }: AppInitializerProps) {
  const { isBackendRunning, isStarting, error, startBackend } = useBackendHealth();
  const [initializationComplete, setInitializationComplete] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    
    const initializeApp = async () => {
      try {
        // Wait a moment for initial health check
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        if (!mounted) return;

        if (!isBackendRunning && !isStarting && !error) {
          console.log("Backend not running, attempting to start...");
          const success = await startBackend();
          
          if (!mounted) return;
          
          if (!success) {
            setInitError("Failed to start backend service");
            return;
          }
        }

        if (!mounted) return;
        
        // Additional initialization steps can be added here
        // e.g., check device configurations, validate settings, etc.
        
        setInitializationComplete(true);
      } catch (err) {
        if (!mounted) return;
        
        console.error("App initialization failed:", err);
        setInitError(err instanceof Error ? err.message : "Initialization failed");
      }
    };

    initializeApp();

    return () => {
      mounted = false;
    };
  }, [isBackendRunning, isStarting, error, startBackend]);

  // Show initialization screen while backend is starting or not ready
  if (!initializationComplete || isStarting || (!isBackendRunning && !error && !initError)) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
            </div>
            <CardTitle>Initializing ZKTeco Manager</CardTitle>
            <CardDescription>
              Setting up the application and starting services...
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>
                {isStarting 
                  ? "Starting backend service..." 
                  : "Checking backend status..."
                }
              </span>
            </div>
            
            <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
              <div 
                className="bg-primary h-full transition-all duration-1000 ease-out"
                style={{ 
                  width: isStarting ? "75%" : isBackendRunning ? "100%" : "25%" 
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
            <CardTitle className="text-red-600">Initialization Failed</CardTitle>
            <CardDescription>
              Unable to start the ZKTeco Manager application
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertDescription>
                {initError || error || "Unknown error occurred"}
              </AlertDescription>
            </Alert>
            
            <div className="space-y-2">
              <Button 
                onClick={() => window.location.reload()} 
                className="w-full"
                variant="outline"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry Initialization
              </Button>
              
              <Button 
                onClick={startBackend}
                className="w-full"
                disabled={isStarting}
              >
                {isStarting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Starting Backend...
                  </>
                ) : (
                  "Start Backend Manually"
                )}
              </Button>
            </div>

            <div className="text-xs text-muted-foreground space-y-1">
              <p><strong>Troubleshooting:</strong></p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Check if backend executable exists</li>
                <li>Verify port 57575 is available</li>
                <li>Check system permissions</li>
                <li>Review application logs</li>
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

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useCallback, useEffect, useState } from "react";

export const useTrayBehavior = () => {
    const [minimizeToTray, setMinimizeToTray] = useState(() => {
        const saved = localStorage.getItem("minimizeToTray");
        return saved === "true";
    });

    const handleCloseRequested = useCallback(
        async (event: any) => {
            if (minimizeToTray) {
                event.preventDefault();
                await invoke("hide_to_tray");
            }
            // If minimizeToTray is false, let the default close behavior happen
        },
        [minimizeToTray],
    );

    useEffect(() => {
        const currentWindow = getCurrentWindow();

        const unsubscribe =
            currentWindow.onCloseRequested(handleCloseRequested);

        return () => {
            unsubscribe.then((cleanup) => cleanup());
        };
    }, [minimizeToTray, handleCloseRequested]);

    useEffect(() => {
        invoke("set_minimize_to_tray", { enable: minimizeToTray }).catch((error) => {
            console.error("Failed to update minimize-to-tray preference in backend:", error);
        });
    }, [minimizeToTray]);

    const toggleMinimizeToTray = (enabled: boolean) => {
        setMinimizeToTray(enabled);
        localStorage.setItem("minimizeToTray", enabled.toString());
    };

    const showMainWindow = async () => {
        await invoke("show_main_window");
    };

    const hideToTray = async () => {
        await invoke("hide_to_tray");
    };

    return {
        minimizeToTray,
        toggleMinimizeToTray,
        showMainWindow,
        hideToTray,
    };
};

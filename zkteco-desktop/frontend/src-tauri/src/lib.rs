use tauri_plugin_shell::ShellExt;
use tauri::{
    Manager,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    State,
};
use std::sync::{Arc, Mutex};
use tauri_plugin_shell::process::CommandChild;

// Global state for backend process management
type BackendProcess = Arc<Mutex<Option<CommandChild>>>;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
fn show_main_window(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[tauri::command]
fn hide_to_tray(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

#[tauri::command]
fn cleanup_backend(backend_process: State<BackendProcess>) -> Result<String, String> {
    match backend_process.lock() {
        Ok(mut process_guard) => {
            if let Some(child) = process_guard.take() {
                match child.kill() {
                    Ok(()) => {
                        println!("Backend process terminated successfully");
                        Ok("Backend process terminated successfully".to_string())
                    },
                    Err(e) => {
                        eprintln!("Failed to kill backend process: {}", e);
                        Err(format!("Failed to kill backend process: {}", e))
                    }
                }
            } else {
                Ok("No backend process to terminate".to_string())
            }
        },
        Err(e) => {
            eprintln!("Failed to acquire backend process lock: {}", e);
            Err(format!("Failed to acquire backend process lock: {}", e))
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_process: BackendProcess = Arc::new(Mutex::new(None));
    
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(backend_process.clone())
        .setup(move |app| {
            // Create system tray
            let show_i = MenuItem::with_id(app, "show", "Show App", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide to Tray", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &hide_i, &quit_i])?;

            let backend_process_for_tray = backend_process.clone();
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .tooltip("ZKTeco Desktop")
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.unminimize();
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                    "quit" => {
                        // Cleanup backend before exiting
                        if let Ok(mut process_guard) = backend_process_for_tray.lock() {
                            if let Some(child) = process_guard.take() {
                                if let Err(e) = child.kill() {
                                    eprintln!("Failed to kill backend process on quit: {}", e);
                                } else {
                                    println!("Backend process terminated on app quit");
                                }
                            }
                        }
                        app.exit(0);
                    }
                    _ => {
                        println!("menu item {:?} not handled", event.id());
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.unminimize();
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // Start the backend sidecar
            // Tauri automatically handles platform-specific naming:
            // - macOS: zkteco-backend-aarch64-apple-darwin
            // - Windows: zkteco-backend-x86_64-pc-windows-msvc.exe
            // - Linux: zkteco-backend-x86_64-unknown-linux-gnu
            match app.shell().sidecar("zkteco-backend") {
                Ok(sidecar_command) => {
                    let sidecar_with_env = sidecar_command.env("SECRET_KEY", "your-secret-key-here");
                    match sidecar_with_env.spawn() {
                        Ok((mut rx, child)) => {
                            println!("Backend sidecar started successfully");
                            
                            // Store the child process for later cleanup
                            if let Ok(mut process_guard) = backend_process.lock() {
                                *process_guard = Some(child);
                                println!("Backend process stored for cleanup management");
                            } else {
                                eprintln!("Failed to store backend process reference");
                            }
                            
                            // Listen for sidecar output
                            tauri::async_runtime::spawn(async move {
                                while let Some(event) = rx.recv().await {
                                    match event {
                                        tauri_plugin_shell::process::CommandEvent::Stdout(output) => {
                                            println!("Backend stdout: {}", String::from_utf8_lossy(&output));
                                        },
                                        tauri_plugin_shell::process::CommandEvent::Stderr(output) => {
                                            eprintln!("Backend stderr: {}", String::from_utf8_lossy(&output));
                                        },
                                        tauri_plugin_shell::process::CommandEvent::Error(error) => {
                                            eprintln!("Backend error: {}", error);
                                        },
                                        tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                                            eprintln!("Backend terminated with code: {:?}", payload.code);
                                        },
                                        _ => {
                                            println!("Backend event: {:?}", event);
                                        }
                                    }
                                }
                            });
                        },
                        Err(e) => {
                            eprintln!("Failed to spawn backend sidecar: {}", e);
                        }
                    }
                },
                Err(e) => {
                    eprintln!("Failed to create backend sidecar command: {}", e);
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, show_main_window, hide_to_tray, cleanup_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

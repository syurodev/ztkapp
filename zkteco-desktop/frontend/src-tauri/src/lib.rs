use tauri_plugin_shell::ShellExt;
use tauri::{
    Manager,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    State,
};
use serde::Serialize;
use std::sync::{Arc, Mutex};
use tauri_plugin_shell::process::CommandChild;
use std::collections::HashMap;
use chrono::{DateTime, Utc};

// Global state for backend process management
type BackendProcess = Arc<Mutex<Option<CommandChild>>>;
type ProcessStatus = Arc<Mutex<HashMap<String, String>>>;

#[derive(Debug, Clone, serde::Serialize)]
struct LogEntry {
    timestamp: DateTime<Utc>,
    level: String, // "error", "info", "warning"
    message: String,
    source: String, // "stderr", "stdout", "system"
}

type BackendLogs = Arc<Mutex<Vec<LogEntry>>>;

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

#[tauri::command]
async fn start_backend(app: tauri::AppHandle, backend_process: State<'_, BackendProcess>, process_status: State<'_, ProcessStatus>, backend_logs: State<'_, BackendLogs>) -> Result<String, String> {
    // Check if process is already running
    match backend_process.lock() {
        Ok(process_guard) => {
            if process_guard.is_some() {
                return Ok("Backend is already running".to_string());
            }
        },
        Err(e) => {
            return Err(format!("Failed to acquire backend process lock: {}", e));
        }
    }

    // Clear any previous status
    if let Ok(mut status_guard) = process_status.lock() {
        status_guard.remove("backend_status");
    }

    // Start the backend sidecar
    match app.shell().sidecar("zkteco-backend") {
        Ok(sidecar_command) => {
            let sidecar_with_env = sidecar_command.env("SECRET_KEY", "your-secret-key-here");
            match sidecar_with_env.spawn() {
                Ok((mut rx, child)) => {
                    println!("Backend sidecar started successfully");
                    
                    // Store the child process
                    match backend_process.lock() {
                        Ok(mut process_guard) => {
                            *process_guard = Some(child);
                            println!("Backend process stored for cleanup management");
                        },
                        Err(e) => {
                            eprintln!("Failed to store backend process reference: {}", e);
                            return Err(format!("Failed to store backend process reference: {}", e));
                        }
                    }
                    
                    let status_for_monitor = process_status.inner().clone();
                    let backend_for_monitor = backend_process.inner().clone();
                    let logs_for_monitor = backend_logs.inner().clone();
                    
                    // Log backend start attempt
                    if let Ok(mut logs) = logs_for_monitor.lock() {
                        logs.push(LogEntry {
                            timestamp: Utc::now(),
                            level: "info".to_string(),
                            message: "Starting backend process...".to_string(),
                            source: "system".to_string(),
                        });
                    }
                    
                    // Listen for sidecar output in background
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            match event {
                                tauri_plugin_shell::process::CommandEvent::Stdout(output) => {
                                    let stdout_str = String::from_utf8_lossy(&output).to_string();
                                    println!("Backend stdout: {}", stdout_str);
                                    
                                    // Log stdout messages
                                    if let Ok(mut logs) = logs_for_monitor.lock() {
                                        logs.push(LogEntry {
                                            timestamp: Utc::now(),
                                            level: "info".to_string(),
                                            message: stdout_str,
                                            source: "stdout".to_string(),
                                        });
                                        
                                        // Keep only last 100 log entries
                                        if logs.len() > 100 {
                                            logs.drain(0..logs.len()-100);
                                        }
                                    }
                                },
                                tauri_plugin_shell::process::CommandEvent::Stderr(output) => {
                                    let stderr_str = String::from_utf8_lossy(&output).to_string();
                                    eprintln!("Backend stderr: {}", stderr_str);
                                    
                                    // Log to backend logs
                                    if let Ok(mut logs) = logs_for_monitor.lock() {
                                        let level = if stderr_str.contains("ERROR") || stderr_str.contains("Error") || 
                                                       stderr_str.contains("ModuleNotFoundError") || stderr_str.contains("Failed to execute") {
                                            "error"
                                        } else if stderr_str.contains("WARNING") || stderr_str.contains("Warning") {
                                            "warning"
                                        } else {
                                            "info"
                                        };
                                        
                                        logs.push(LogEntry {
                                            timestamp: Utc::now(),
                                            level: level.to_string(),
                                            message: stderr_str.clone(),
                                            source: "stderr".to_string(),
                                        });
                                        
                                        // Keep only last 100 log entries
                                        if logs.len() > 100 {
                                            logs.drain(0..logs.len()-100);
                                        }
                                    }
                                    
                                    // Check for critical errors
                                    if stderr_str.contains("ModuleNotFoundError") || stderr_str.contains("Failed to execute script") {
                                        if let Ok(mut status_guard) = status_for_monitor.lock() {
                                            status_guard.insert("backend_status".to_string(), format!("Failed to start backend: {}", stderr_str));
                                        }
                                    }
                                },
                                tauri_plugin_shell::process::CommandEvent::Error(error) => {
                                    let error_str = format!("{}", error);
                                    eprintln!("Backend error: {}", error_str);
                                    
                                    // Log error
                                    if let Ok(mut logs) = logs_for_monitor.lock() {
                                        logs.push(LogEntry {
                                            timestamp: Utc::now(),
                                            level: "error".to_string(),
                                            message: error_str.clone(),
                                            source: "system".to_string(),
                                        });
                                    }
                                    
                                    if let Ok(mut status_guard) = status_for_monitor.lock() {
                                        status_guard.insert("backend_status".to_string(), format!("Backend error: {}", error_str));
                                    }
                                },
                                tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                                    let term_msg = format!("Backend terminated with code: {:?}", payload.code);
                                    eprintln!("{}", term_msg);
                                    
                                    // Log termination
                                    if let Ok(mut logs) = logs_for_monitor.lock() {
                                        logs.push(LogEntry {
                                            timestamp: Utc::now(),
                                            level: "error".to_string(),
                                            message: term_msg.clone(),
                                            source: "system".to_string(),
                                        });
                                    }
                                    
                                    // Mark as startup failure if early termination
                                    if let Ok(mut status_guard) = status_for_monitor.lock() {
                                        status_guard.insert("backend_status".to_string(), format!("Backend failed to start - terminated with code: {:?}", payload.code));
                                    }
                                    
                                    // Clear the process from our tracking
                                    if let Ok(mut process_guard) = backend_for_monitor.lock() {
                                        *process_guard = None;
                                    }
                                    break;
                                },
                                _ => {
                                    println!("Backend event: {:?}", event);
                                }
                            }
                        }
                    });

                    // Wait a bit to see if process starts successfully
                    tokio::time::sleep(tokio::time::Duration::from_millis(2000)).await;
                    
                    // Check if there was an early failure
                    if let Ok(status_guard) = process_status.lock() {
                        if let Some(error_msg) = status_guard.get("backend_status") {
                            return Err(error_msg.clone());
                        }
                    }
                    
                    // Check if process is still alive
                    if let Ok(process_guard) = backend_process.lock() {
                        if process_guard.is_none() {
                            return Err("Backend process terminated unexpectedly during startup".to_string());
                        }
                    }

                    Ok("Backend started successfully".to_string())
                },
                Err(e) => {
                    eprintln!("Failed to spawn backend sidecar: {}", e);
                    Err(format!("Failed to spawn backend sidecar: {}", e))
                }
            }
        },
        Err(e) => {
            eprintln!("Failed to create backend sidecar command: {}", e);
            Err(format!("Failed to create backend sidecar command: {}", e))
        }
    }
}

#[tauri::command]
fn stop_backend(backend_process: State<BackendProcess>) -> Result<String, String> {
    match backend_process.lock() {
        Ok(mut process_guard) => {
            if let Some(child) = process_guard.take() {
                match child.kill() {
                    Ok(()) => {
                        println!("Backend process stopped successfully");
                        Ok("Backend process stopped successfully".to_string())
                    },
                    Err(e) => {
                        eprintln!("Failed to stop backend process: {}", e);
                        Err(format!("Failed to stop backend process: {}", e))
                    }
                }
            } else {
                Err("No backend process is running".to_string())
            }
        },
        Err(e) => {
            eprintln!("Failed to acquire backend process lock: {}", e);
            Err(format!("Failed to acquire backend process lock: {}", e))
        }
    }
}

#[tauri::command]
async fn restart_backend(app: tauri::AppHandle, backend_process: State<'_, BackendProcess>, process_status: State<'_, ProcessStatus>, backend_logs: State<'_, BackendLogs>) -> Result<String, String> {
    // Stop first
    let _ = stop_backend(backend_process.clone());
    
    // Wait a moment for cleanup
    tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;
    
    // Start again
    start_backend(app, backend_process, process_status, backend_logs).await
}

#[tauri::command]
fn is_backend_running(backend_process: State<BackendProcess>) -> bool {
    match backend_process.lock() {
        Ok(process_guard) => process_guard.is_some(),
        Err(_) => false,
    }
}

#[tauri::command]
fn get_backend_logs(backend_logs: State<BackendLogs>) -> Result<Vec<LogEntry>, String> {
    match backend_logs.lock() {
        Ok(logs) => Ok(logs.clone()),
        Err(e) => Err(format!("Failed to get backend logs: {}", e)),
    }
}

#[tauri::command]
fn clear_backend_logs(backend_logs: State<BackendLogs>) -> Result<String, String> {
    match backend_logs.lock() {
        Ok(mut logs) => {
            logs.clear();
            Ok("Backend logs cleared".to_string())
        },
        Err(e) => Err(format!("Failed to clear backend logs: {}", e)),
    }
}

#[tauri::command]
fn get_backend_error_logs(backend_logs: State<BackendLogs>) -> Result<Vec<LogEntry>, String> {
    match backend_logs.lock() {
        Ok(logs) => {
            let error_logs: Vec<LogEntry> = logs.iter()
                .filter(|log| log.level == "error")
                .cloned()
                .collect();
            Ok(error_logs)
        },
        Err(e) => Err(format!("Failed to get backend error logs: {}", e)),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_process: BackendProcess = Arc::new(Mutex::new(None));
    let process_status: ProcessStatus = Arc::new(Mutex::new(HashMap::new()));
    let backend_logs: BackendLogs = Arc::new(Mutex::new(Vec::new()));
    
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(backend_process.clone())
        .manage(process_status.clone())
        .manage(backend_logs.clone())
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
        .invoke_handler(tauri::generate_handler![greet, show_main_window, hide_to_tray, cleanup_backend, start_backend, stop_backend, restart_backend, is_backend_running, get_backend_logs, clear_backend_logs, get_backend_error_logs])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

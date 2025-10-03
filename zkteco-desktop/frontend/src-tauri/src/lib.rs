use chrono::{DateTime, Local, Utc};
use dirs::data_local_dir;
use std::collections::HashMap;
use std::env;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, State,
};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

#[cfg(target_os = "windows")]
use std::os::windows::fs::OpenOptionsExt;
#[cfg(target_os = "windows")]
use std::io::Read;

// Global state for backend process management
type BackendProcess = Arc<Mutex<Option<CommandChild>>>;
type ProcessStatus = Arc<Mutex<HashMap<String, String>>>;
type MinimizeToTraySetting = Arc<Mutex<bool>>;

#[derive(Debug, Clone, serde::Serialize)]
struct LogEntry {
    timestamp: DateTime<Utc>,
    level: String, // "error", "info", "warning"
    message: String,
    source: String, // "stderr", "stdout", "system"
}

type BackendLogs = Arc<Mutex<Vec<LogEntry>>>;

const BACKEND_STARTING_KEY: &str = "backend_starting";

fn resolve_app_data_dir() -> PathBuf {
    let mut base_dir = data_local_dir().unwrap_or_else(|| env::temp_dir());
    base_dir.push("ZKTeco");

    if let Err(err) = fs::create_dir_all(&base_dir) {
        eprintln!(
            "Failed to create local data directory at {:?}: {}. Falling back to temporary directory.",
            base_dir, err
        );
        let mut fallback_dir = env::temp_dir();
        fallback_dir.push("ZKTeco");
        let _ = fs::create_dir_all(&fallback_dir);
        fallback_dir
    } else {
        base_dir
    }
}

fn resolve_backend_db_path() -> PathBuf {
    let mut db_path = resolve_app_data_dir();
    db_path.push("zkteco_app.db");
    db_path
}

fn append_app_log(message: &str) {
    let mut log_path = resolve_app_data_dir();
    log_path.push("zkteco_app.log");

    match OpenOptions::new().create(true).append(true).open(&log_path) {
        Ok(mut file) => {
            let timestamp = Local::now().format("%Y-%m-%d %H:%M:%S");
            if let Err(err) = writeln!(file, "[{}] {}", timestamp, message) {
                eprintln!(
                    "Failed to write to app log at {:?}: {}",
                    log_path, err
                );
            }
        }
        Err(err) => {
            eprintln!("Failed to open app log at {:?}: {}", log_path, err);
        }
    }
}

#[tauri::command]
fn set_minimize_to_tray(
    enable: bool,
    minimize_setting: State<MinimizeToTraySetting>,
) -> Result<(), String> {
    match minimize_setting.lock() {
        Ok(mut guard) => {
            *guard = enable;
            append_app_log(&format!(
                "Minimize-to-tray preference updated: {}",
                enable
            ));
            Ok(())
        }
        Err(err) => Err(format!("Failed to update minimize_to_tray setting: {}", err)),
    }
}

struct BackendStartupGuard {
    status: ProcessStatus,
    acquired: bool,
}

impl BackendStartupGuard {
    fn try_acquire(status: &ProcessStatus) -> Result<(Self, bool), String> {
        let status_clone = status.clone();
        let mut status_map = status_clone
            .lock()
            .map_err(|err| format!("Failed to lock process status: {}", err))?;

        if status_map
            .get(BACKEND_STARTING_KEY)
            .map(|value| value == "true")
            .unwrap_or(false)
        {
            drop(status_map);
            return Ok((BackendStartupGuard {
                status: status_clone,
                acquired: false,
            }, false));
        }

        status_map.insert(BACKEND_STARTING_KEY.to_string(), "true".to_string());
        drop(status_map);

        Ok((BackendStartupGuard {
            status: status_clone,
            acquired: true,
        }, true))
    }
}

impl Drop for BackendStartupGuard {
    fn drop(&mut self) {
        if self.acquired {
            if let Ok(mut status_map) = self.status.lock() {
                status_map.remove(BACKEND_STARTING_KEY);
            }
            self.acquired = false;
        }
    }
}

// Helper function to check if backend is responding via HTTP
async fn check_backend_health() -> bool {
    match reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
    {
        Ok(client) => {
            match client
                .get("http://127.0.0.1:57575/service/status")
                .send()
                .await
            {
                Ok(response) => {
                    let is_healthy = response.status().is_success();
                    println!(
                        "Backend HTTP health check: {}",
                        if is_healthy { "healthy" } else { "unhealthy" }
                    );
                    is_healthy
                }
                Err(e) => {
                    println!("Backend HTTP health check failed: {}", e);
                    false
                }
            }
        }
        Err(e) => {
            println!("Failed to create HTTP client: {}", e);
            false
        }
    }
}

// Helper function to detect existing backend process
async fn detect_existing_backend(backend_process: &BackendProcess) -> bool {
    // First check if we have a process tracked
    let has_tracked_process = {
        match backend_process.lock() {
            Ok(process_guard) => process_guard.is_some(),
            Err(_) => false,
        }
    };

    if has_tracked_process {
        println!(
            "Backend detection - tracked process exists, assuming backend is starting or running",
        );
        return true;
    }

    // Then check HTTP health
    let is_http_healthy = check_backend_health().await;

    println!(
        "Backend detection - no tracked process, HTTP healthy: {}",
        is_http_healthy
    );

    // Backend is considered existing if either:
    // 1. We have a tracked process AND it's HTTP healthy
    // 2. We don't have a tracked process BUT HTTP is healthy (orphaned process)
    is_http_healthy
}

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
    append_app_log("cleanup_backend command invoked");
    match backend_process.lock() {
        Ok(mut process_guard) => {
            if let Some(child) = process_guard.take() {
                match child.kill() {
                    Ok(()) => {
                        println!("Backend process terminated successfully");
                        append_app_log("cleanup_backend terminated backend process successfully");
                        Ok("Backend process terminated successfully".to_string())
                    }
                    Err(e) => {
                        eprintln!("Failed to kill backend process: {}", e);
                        append_app_log(&format!(
                            "cleanup_backend failed to kill backend process: {}",
                            e
                        ));
                        Err(format!("Failed to kill backend process: {}", e))
                    }
                }
            } else {
                append_app_log("cleanup_backend found no backend process to terminate");
                Ok("No backend process to terminate".to_string())
            }
        }
        Err(e) => {
            eprintln!("Failed to acquire backend process lock: {}", e);
            append_app_log(&format!(
                "cleanup_backend failed to acquire backend process lock: {}",
                e
            ));
            Err(format!("Failed to acquire backend process lock: {}", e))
        }
    }
}

#[tauri::command]
async fn start_backend(
    app: tauri::AppHandle,
    backend_process: State<'_, BackendProcess>,
    process_status: State<'_, ProcessStatus>,
    backend_logs: State<'_, BackendLogs>,
) -> Result<String, String> {
    println!("Start backend command called");
    append_app_log("start_backend command invoked");

    let (startup_guard, acquired) = match BackendStartupGuard::try_acquire(&process_status) {
        Ok(result) => result,
        Err(err) => {
            append_app_log(&format!(
                "start_backend failed to acquire startup guard: {}",
                err
            ));
            return Err(err);
        }
    };

    if !acquired {
        append_app_log("start_backend ignored - backend startup already in progress");
        return Ok("Backend startup already in progress".to_string());
    }

    let _startup_guard = startup_guard;

    // Check for existing backend (comprehensive detection)
    if detect_existing_backend(&backend_process).await {
        println!("Backend already exists - skipping startup");
        append_app_log("start_backend skipped - backend already running");
        return Ok("Backend is already running".to_string());
    }

    println!("No existing backend detected - proceeding with startup");

    let db_path = resolve_backend_db_path();
    let db_path_str = db_path.to_string_lossy().to_string();
    if let Some(parent) = db_path.parent() {
        if let Err(err) = fs::create_dir_all(parent) {
            eprintln!(
                "Failed to ensure database directory at {:?}: {}",
                parent, err
            );
            append_app_log(&format!(
                "Failed to ensure database directory at {:?}: {}",
                parent, err
            ));
        }
    }
    println!("Using backend database at: {}", db_path_str);
    append_app_log(&format!("start_backend proceeding - DB path {}", db_path_str));

    // Clear any previous status
    if let Ok(mut status_guard) = process_status.lock() {
        status_guard.remove("backend_status");
    }

    // Start the backend sidecar
    match app.shell().sidecar("zkteco-backend") {
        Ok(sidecar_command) => {
            let sidecar_with_env = sidecar_command
                .env("SECRET_KEY", "b7ad3ec8a8262756372175c8d4f83cdce82d9bc85878ff0b4258ca91a3a1e641")
                .env("LOG_LEVEL", "INFO")
                .env("FLASK_DEBUG", "0")
                .env("FLASK_ENV", "production")
                .env("ZKTECO_DB_PATH", &db_path_str);
            match sidecar_with_env.spawn() {
                Ok((mut rx, child)) => {
                    println!("Backend sidecar started successfully");
                    append_app_log("start_backend succeeded in spawning backend sidecar");

                    // Store the child process
                    match backend_process.lock() {
                        Ok(mut process_guard) => {
                            *process_guard = Some(child);
                            println!("Backend process stored for cleanup management");
                        }
                        Err(e) => {
                            eprintln!("Failed to store backend process reference: {}", e);
                            return Err(format!(
                                "Failed to store backend process reference: {}",
                                e
                            ));
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
                                        let len = logs.len();
                                        if len > 100 {
                                            logs.drain(0..len - 100);
                                        }
                                    }
                                }
                                tauri_plugin_shell::process::CommandEvent::Stderr(output) => {
                                    let stderr_str = String::from_utf8_lossy(&output).to_string();
                                    eprintln!("Backend stderr: {}", stderr_str);

                                    // Log to backend logs
                                    if let Ok(mut logs) = logs_for_monitor.lock() {
                                        let level = if stderr_str.contains("ERROR")
                                            || stderr_str.contains("Error")
                                            || stderr_str.contains("ModuleNotFoundError")
                                            || stderr_str.contains("Failed to execute")
                                        {
                                            "error"
                                        } else if stderr_str.contains("WARNING")
                                            || stderr_str.contains("Warning")
                                        {
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
                                        let len = logs.len();
                                        if len > 100 {
                                            logs.drain(0..len - 100);
                                        }
                                    }

                                    // Check for critical errors
                                    if stderr_str.contains("ModuleNotFoundError")
                                        || stderr_str.contains("Failed to execute script")
                                    {
                                        if let Ok(mut status_guard) = status_for_monitor.lock() {
                                            status_guard.insert(
                                                "backend_status".to_string(),
                                                format!("Failed to start backend: {}", stderr_str),
                                            );
                                        }
                                    }
                                }
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
                                        status_guard.insert(
                                            "backend_status".to_string(),
                                            format!("Backend error: {}", error_str),
                                        );
                                    }
                                }
                                tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                                    let term_msg =
                                        format!("Backend terminated with code: {:?}", payload.code);
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
                                }
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
                            append_app_log(&format!(
                                "start_backend detected early failure: {}",
                                error_msg
                            ));
                            return Err(error_msg.clone());
                        }
                    }

                    // Check if process is still alive
                    if let Ok(process_guard) = backend_process.lock() {
                        if process_guard.is_none() {
                            append_app_log(
                                "start_backend aborted - backend process terminated during startup",
                            );
                            return Err("Backend process terminated unexpectedly during startup"
                                .to_string());
                        }
                    }

                    append_app_log("start_backend completed verification successfully");
                    Ok("Backend started successfully".to_string())
                }
                Err(e) => {
                    let error_msg = format!("Failed to spawn backend sidecar: {}. This may be due to permission issues or missing dependencies.", e);
                    eprintln!("{}", error_msg);
                    append_app_log(&format!("start_backend failed to spawn backend sidecar: {}", e));
                    Err(error_msg)
                }
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to create backend sidecar command: {}. Make sure the backend executable exists in the bundle.", e);
            eprintln!("{}", error_msg);
            append_app_log(&format!(
                "start_backend failed to create sidecar command: {}",
                e
            ));
            Err(error_msg)
        }
    }
}

#[tauri::command]
fn stop_backend(backend_process: State<BackendProcess>) -> Result<String, String> {
    append_app_log("stop_backend command invoked");
    match backend_process.lock() {
        Ok(mut process_guard) => {
            if let Some(child) = process_guard.take() {
                match child.kill() {
                    Ok(()) => {
                        println!("Backend process stopped successfully");
                        append_app_log("stop_backend terminated backend process successfully");
                        Ok("Backend process stopped successfully".to_string())
                    }
                    Err(e) => {
                        eprintln!("Failed to stop backend process: {}", e);
                        append_app_log(&format!(
                            "stop_backend failed to terminate backend process: {}",
                            e
                        ));
                        Err(format!("Failed to stop backend process: {}", e))
                    }
                }
            } else {
                append_app_log("stop_backend found no running backend process");
                Err("No backend process is running".to_string())
            }
        }
        Err(e) => {
            eprintln!("Failed to acquire backend process lock: {}", e);
            append_app_log(&format!(
                "stop_backend failed to acquire backend process lock: {}",
                e
            ));
            Err(format!("Failed to acquire backend process lock: {}", e))
        }
    }
}

#[tauri::command]
async fn restart_backend(
    app: tauri::AppHandle,
    backend_process: State<'_, BackendProcess>,
    process_status: State<'_, ProcessStatus>,
    backend_logs: State<'_, BackendLogs>,
) -> Result<String, String> {
    append_app_log("restart_backend command invoked");
    // Stop first
    let _ = stop_backend(backend_process.clone());

    // Wait a moment for cleanup
    tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;

    // Start again
    let result = start_backend(app, backend_process, process_status, backend_logs).await;
    if let Err(ref err) = result {
        append_app_log(&format!("restart_backend failed to restart backend: {}", err));
    } else {
        append_app_log("restart_backend completed successfully");
    }
    result
}

#[tauri::command]
async fn is_backend_running(backend_process: State<'_, BackendProcess>) -> Result<bool, String> {
    let is_running = detect_existing_backend(&backend_process).await;
    println!("Backend running check: {}", is_running);
    Ok(is_running)
}

#[tauri::command]
async fn check_backend_http_health() -> bool {
    check_backend_health().await
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
        }
        Err(e) => Err(format!("Failed to clear backend logs: {}", e)),
    }
}

#[tauri::command]
fn get_backend_error_logs(backend_logs: State<BackendLogs>) -> Result<Vec<LogEntry>, String> {
    match backend_logs.lock() {
        Ok(logs) => {
            let error_logs: Vec<LogEntry> = logs
                .iter()
                .filter(|log| log.level == "error")
                .cloned()
                .collect();
            Ok(error_logs)
        }
        Err(e) => Err(format!("Failed to get backend error logs: {}", e)),
    }
}

// Helper function to get log file path
fn get_log_file_path() -> Result<PathBuf, String> {
    let home_dir = dirs::home_dir().ok_or("Failed to get home directory")?;

    // Try multiple possible locations in order
    let possible_paths = vec![
        // macOS/Linux: ~/.local/share/ZKTeco/app.log
        home_dir
            .join(".local")
            .join("share")
            .join("ZKTeco")
            .join("app.log"),
        // Windows: %LOCALAPPDATA%\ZKTeco\app.log
        dirs::data_local_dir()
            .unwrap_or_else(|| home_dir.clone())
            .join("ZKTeco")
            .join("app.log"),
        // Fallback: ~/zkteco_logs/app.log
        home_dir.join("zkteco_logs").join("app.log"),
        // Last resort: current directory
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join("app.log"),
    ];

    // Return first existing path
    for path in &possible_paths {
        if path.exists() {
            return Ok(path.clone());
        }
    }

    // If no file exists, return the first path (default location)
    Ok(possible_paths[0].clone())
}

#[derive(Debug, Clone, serde::Serialize)]
struct FileLogEntry {
    line_number: usize,
    timestamp: String,
    level: String,
    module: String,
    message: String,
}

#[tauri::command]
fn get_log_file_path_command() -> Result<String, String> {
    match get_log_file_path() {
        Ok(path) => Ok(path.to_string_lossy().to_string()),
        Err(e) => Err(e),
    }
}

#[tauri::command]
fn read_log_file(lines: Option<usize>) -> Result<Vec<FileLogEntry>, String> {
    let log_path = get_log_file_path()?;

    if !log_path.exists() {
        return Ok(Vec::new());
    }

    let content = read_log_file_content(&log_path)?;

    let all_lines: Vec<&str> = content.lines().collect();
    let lines_to_read = lines.unwrap_or(500); // Default to last 500 lines

    // Take last N lines
    let start_idx = if all_lines.len() > lines_to_read {
        all_lines.len() - lines_to_read
    } else {
        0
    };

    let mut entries = Vec::new();

    for (idx, line) in all_lines[start_idx..].iter().enumerate() {
        // Parse log line format: [timestamp] LEVEL in module: message
        // Example: [2025-10-01 15:46:31,029] INFO in zkteco.logger: Message here

        if let Some(log_entry) = parse_log_line(line, start_idx + idx + 1) {
            entries.push(log_entry);
        }
    }

    Ok(entries)
}

#[cfg(target_os = "windows")]
fn read_log_file_content(path: &Path) -> Result<String, String> {
    const FILE_SHARE_READ: u32 = 0x00000001;
    const FILE_SHARE_WRITE: u32 = 0x00000002;
    const FILE_SHARE_DELETE: u32 = 0x00000004;

    let mut file = OpenOptions::new()
        .read(true)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)
        .open(path)
        .map_err(|e| format!("Failed to open log file: {}", e))?;

    let mut buffer = Vec::new();
    file.read_to_end(&mut buffer)
        .map_err(|e| format!("Failed to read log file: {}", e))?;

    Ok(String::from_utf8_lossy(&buffer).to_string())
}

#[cfg(not(target_os = "windows"))]
fn read_log_file_content(path: &Path) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| format!("Failed to read log file: {}", e))
}

fn parse_log_line(line: &str, line_number: usize) -> Option<FileLogEntry> {
    // Try to parse: [timestamp] LEVEL in module: message
    if !line.starts_with('[') {
        return None;
    }

    let parts: Vec<&str> = line.splitn(2, "] ").collect();
    if parts.len() != 2 {
        return None;
    }

    let timestamp = parts[0].trim_start_matches('[').to_string();
    let rest = parts[1];

    // Parse "LEVEL in module: message"
    let level_parts: Vec<&str> = rest.splitn(2, " in ").collect();
    if level_parts.len() != 2 {
        return Some(FileLogEntry {
            line_number,
            timestamp,
            level: "INFO".to_string(),
            module: "unknown".to_string(),
            message: rest.to_string(),
        });
    }

    let level = level_parts[0].to_string();

    let module_message: Vec<&str> = level_parts[1].splitn(2, ": ").collect();
    if module_message.len() != 2 {
        return Some(FileLogEntry {
            line_number,
            timestamp,
            level,
            module: "unknown".to_string(),
            message: level_parts[1].to_string(),
        });
    }

    Some(FileLogEntry {
        line_number,
        timestamp,
        level,
        module: module_message[0].to_string(),
        message: module_message[1].to_string(),
    })
}

#[tauri::command]
fn clear_log_file() -> Result<String, String> {
    let log_path = get_log_file_path()?;

    if !log_path.exists() {
        return Ok("Log file does not exist".to_string());
    }

    fs::write(&log_path, "").map_err(|e| format!("Failed to clear log file: {}", e))?;

    Ok("Log file cleared successfully".to_string())
}

#[tauri::command]
fn export_log_file(destination: String) -> Result<String, String> {
    let log_path = get_log_file_path()?;

    if !log_path.exists() {
        return Err("Log file does not exist".to_string());
    }

    let dest_path = PathBuf::from(destination);

    fs::copy(&log_path, &dest_path).map_err(|e| format!("Failed to export log file: {}", e))?;

    Ok(format!("Log file exported to: {}", dest_path.display()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    append_app_log("Tauri application run() invoked");
    let backend_process: BackendProcess = Arc::new(Mutex::new(None));
    let process_status: ProcessStatus = Arc::new(Mutex::new(HashMap::new()));
    let backend_logs: BackendLogs = Arc::new(Mutex::new(Vec::new()));
    let minimize_to_tray_setting: MinimizeToTraySetting = Arc::new(Mutex::new(false));

    let backend_process_for_run = backend_process.clone();
    let minimize_setting_for_run = minimize_to_tray_setting.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(backend_process.clone())
        .manage(process_status.clone())
        .manage(backend_logs.clone())
        .manage(minimize_to_tray_setting.clone())
        .setup(move |app| {
            append_app_log("Tauri setup hook executing");
            // Create system tray
            let show_i = MenuItem::with_id(app, "show", "Show App", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide to Tray", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &hide_i, &quit_i])?;

            let backend_process_for_tray = backend_process.clone();
            let minimize_setting_for_window = minimize_to_tray_setting.clone();
            let backend_process_for_window = backend_process.clone();
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
                                    append_app_log(&format!(
                                        "Failed to kill backend process on quit: {}",
                                        e
                                    ));
                                } else {
                                    println!("Backend process terminated on app quit");
                                    append_app_log("Backend process terminated on app quit");
                                }
                            }
                        }
                        append_app_log("Tauri application exiting via tray quit");
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
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.unminimize();
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // Check for existing backend first
            let backend_process_for_setup = backend_process.clone();
            let app_for_startup = app.handle().clone();

            tauri::async_runtime::spawn(async move {
                // Wait a moment for system to settle
                tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;

                // Check if backend already exists
                if detect_existing_backend(&backend_process_for_setup).await {
                    println!("Backend already running - skipping startup backend launch");
                    append_app_log("Startup check found existing backend - skipping auto launch");
                    return;
                }

                println!("No existing backend detected during startup - launching backend");
                append_app_log("Auto-starting backend during app setup");

                // Start the backend sidecar
                // Tauri automatically handles platform-specific naming:
                // - macOS: zkteco-backend-aarch64-apple-darwin
                // - Windows: zkteco-backend-x86_64-pc-windows-msvc.exe
                // - Linux: zkteco-backend-x86_64-unknown-linux-gnu
                startup_backend_sidecar(
                    app_for_startup,
                    backend_process_for_setup,
                    process_status.clone(),
                )
                .await;
            });

            // Set up window close behavior - minimize to tray instead of closing
            let main_window = app.get_webview_window("main");
            if let Some(window) = main_window {
                let window_clone = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        let minimize_enabled = minimize_setting_for_window
                            .lock()
                            .map(|guard| *guard)
                            .unwrap_or(false);

                        if minimize_enabled {
                            api.prevent_close();
                            let _ = window_clone.hide();
                            println!("Window minimized to tray instead of closing");
                            append_app_log(
                                "Window close intercepted - minimized to tray",
                            );
                        } else {
                            println!("Window close requested - shutting down backend");
                            append_app_log(
                                "Window close requested - shutting down backend before exit",
                            );

                            if let Ok(mut process_guard) = backend_process_for_window.lock() {
                                if let Some(child) = process_guard.take() {
                                    if let Err(err) = child.kill() {
                                        eprintln!(
                                            "Failed to kill backend process on window close: {}",
                                            err
                                        );
                                        append_app_log(&format!(
                                            "Failed to kill backend process on window close: {}",
                                            err
                                        ));
                                    } else {
                                        println!(
                                            "Backend process terminated due to window close"
                                        );
                                        append_app_log(
                                            "Backend process terminated due to window close",
                                        );
                                    }
                                }
                            }
                        }
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            show_main_window,
            hide_to_tray,
            cleanup_backend,
            start_backend,
            stop_backend,
            restart_backend,
            is_backend_running,
            check_backend_http_health,
            get_backend_logs,
            clear_backend_logs,
            get_backend_error_logs,
            get_log_file_path_command,
            read_log_file,
            clear_log_file,
            export_log_file,
            set_minimize_to_tray
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |app_handle, event| {
            if let tauri::RunEvent::Reopen { .. } = event {
                let minimize_enabled = minimize_setting_for_run
                    .lock()
                    .map(|guard| *guard)
                    .unwrap_or(false);

                if let Some(window) = app_handle.get_webview_window("main") {
                    if minimize_enabled {
                        let _ = window.unminimize();
                        let _ = window.show();
                        let _ = window.set_focus();
                        append_app_log(
                            "Application reactivated - showing main window",
                        );
                    }
                }
            } else if let tauri::RunEvent::ExitRequested { .. } = event {
                append_app_log("Exit requested - terminating backend");
                if let Ok(mut process_guard) = backend_process_for_run.lock() {
                    if let Some(child) = process_guard.take() {
                        if let Err(err) = child.kill() {
                            eprintln!(
                                "Failed to kill backend process on exit: {}",
                                err
                            );
                            append_app_log(&format!(
                                "Failed to kill backend process on exit: {}",
                                err
                            ));
                        } else {
                            println!("Backend process terminated on app exit");
                            append_app_log(
                                "Backend process terminated on app exit",
                            );
                        }
                    }
                }
            }
        });
}

// Helper function to start backend sidecar (extracted from setup)
async fn startup_backend_sidecar(
    app: tauri::AppHandle,
    backend_process: BackendProcess,
    process_status: ProcessStatus,
) {
    match app.shell().sidecar("zkteco-backend") {
        Ok(sidecar_command) => {
            append_app_log("startup_backend_sidecar invoked");

            let (startup_guard, acquired) = match BackendStartupGuard::try_acquire(&process_status)
            {
                Ok(result) => result,
                Err(err) => {
                    append_app_log(&format!(
                        "startup_backend_sidecar failed to acquire startup guard: {}",
                        err
                    ));
                    return;
                }
            };

            if !acquired {
                append_app_log(
                    "startup_backend_sidecar skipped - backend startup already in progress",
                );
                return;
            }

            let _startup_guard = startup_guard;

            let db_path = resolve_backend_db_path();
            let db_path_str = db_path.to_string_lossy().to_string();
            if let Some(parent) = db_path.parent() {
                if let Err(err) = fs::create_dir_all(parent) {
                    eprintln!(
                        "Failed to ensure database directory at {:?}: {}",
                        parent, err
                    );
                    append_app_log(&format!(
                        "startup_backend_sidecar failed to ensure database directory at {:?}: {}",
                        parent, err
                    ));
                }
            }
            println!("Using backend database at startup: {}", db_path_str);
            append_app_log(&format!(
                "startup_backend_sidecar using DB path {}",
                db_path_str
            ));

            let sidecar_with_env = sidecar_command
                .env("SECRET_KEY", "your-secret-key-here")
                .env("LOG_LEVEL", "INFO")
                .env("FLASK_DEBUG", "0")
                .env("FLASK_ENV", "production")
                .env("ZKTECO_DB_PATH", &db_path_str);
            match sidecar_with_env.spawn() {
                Ok((mut rx, child)) => {
                    println!("Backend sidecar started successfully during startup");
                    append_app_log(
                        "startup_backend_sidecar spawned backend sidecar successfully",
                    );

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
                                    println!(
                                        "Backend stdout: {}",
                                        String::from_utf8_lossy(&output)
                                    );
                                }
                                tauri_plugin_shell::process::CommandEvent::Stderr(output) => {
                                    eprintln!(
                                        "Backend stderr: {}",
                                        String::from_utf8_lossy(&output)
                                    );
                                }
                                tauri_plugin_shell::process::CommandEvent::Error(error) => {
                                    eprintln!("Backend error: {}", error);
                                }
                                tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                                    eprintln!("Backend terminated with code: {:?}", payload.code);
                                    break;
                                }
                                _ => {
                                    println!("Backend event: {:?}", event);
                                }
                            }
                        }
                    });
                }
                Err(e) => {
                    eprintln!("Failed to spawn backend sidecar during startup: {}. This may indicate permission issues or missing dependencies.", e);
                    append_app_log(&format!(
                        "startup_backend_sidecar failed to spawn backend sidecar: {}",
                        e
                    ));
                }
            }
        }
        Err(e) => {
            eprintln!("Failed to create backend sidecar command during startup: {}. The backend executable might be missing from the bundle.", e);
            append_app_log(&format!(
                "startup_backend_sidecar failed to create sidecar command: {}",
                e
            ));
        }
    }
}

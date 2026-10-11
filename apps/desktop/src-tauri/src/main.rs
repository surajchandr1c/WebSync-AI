// WebSync AI Tauri Desktop Main
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::VecDeque;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use serde::{Deserialize, Serialize};
use tauri::State;

const MAX_LOG_LINES: usize = 1000;

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct WorkerBinaryInfo {
    pub found: bool,
    pub path: Option<String>,
    pub version: Option<String>,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct LocalWorkerStatus {
    pub running: bool,
    pub pid: Option<u32>,
    pub coordinator_url: Option<String>,
    pub worker_id: Option<String>,
    pub exit_code: Option<i32>,
    pub binary_path: Option<String>,
}

struct WorkerDaemonState {
    child: Option<Child>,
    pid: Option<u32>,
    coordinator_url: Option<String>,
    worker_id: Option<String>,
    binary_path: Option<String>,
    exit_code: Option<i32>,
    logs: VecDeque<String>,
}

pub struct AppState {
    daemon: Arc<Mutex<WorkerDaemonState>>,
}

fn find_worker_binary() -> Option<PathBuf> {
    let binary_name = if cfg!(target_os = "windows") {
        "websync-worker.exe"
    } else {
        "websync-worker"
    };

    // 1. Current executable directory
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let candidate = exe_dir.join(binary_name);
            if candidate.exists() {
                return Some(candidate);
            }
            let candidate_res = exe_dir.join("resources").join(binary_name);
            if candidate_res.exists() {
                return Some(candidate_res);
            }
        }
    }

    // 2. Relative paths from workspace
    let candidates = [
        PathBuf::from("worker/dist").join(binary_name),
        PathBuf::from("../../worker/dist").join(binary_name),
        PathBuf::from("../worker/dist").join(binary_name),
        PathBuf::from("../../../worker/dist").join(binary_name),
        PathBuf::from("dist").join(binary_name),
    ];

    for candidate in &candidates {
        if candidate.exists() {
            if let Ok(canon) = candidate.canonicalize() {
                return Some(canon);
            }
            return Some(candidate.clone());
        }
    }

    // 3. Search in system PATH
    if let Ok(path_var) = env::var("PATH") {
        for path_entry in env::split_paths(&path_var) {
            let candidate = path_entry.join(binary_name);
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }

    None
}

fn validate_coordinator_url(url_str: &str) -> Result<(), String> {
    let trimmed = url_str.trim();
    if trimmed.is_empty() {
        return Err("Coordinator URL cannot be empty".to_string());
    }

    let is_https = trimmed.starts_with("https://") || trimmed.starts_with("wss://");
    let is_http = trimmed.starts_with("http://") || trimmed.starts_with("ws://");

    if !is_https && !is_http {
        return Err("Coordinator URL must use HTTP, HTTPS, WS, or WSS protocol".to_string());
    }

    // Extract host
    let without_proto = if let Some(idx) = trimmed.find("://") {
        &trimmed[idx + 3..]
    } else {
        trimmed
    };

    let host_part = without_proto
        .split('/')
        .next()
        .unwrap_or("")
        .split(':')
        .next()
        .unwrap_or("");

    let is_localhost = host_part.eq_ignore_ascii_case("localhost")
        || host_part == "127.0.0.1"
        || host_part == "::1"
        || host_part.starts_with("127.");

    if !is_localhost && !is_https {
        return Err(
            "Security Policy Violation: Remote coordinator URLs must use HTTPS or WSS. Plain HTTP/WS is only permitted for localhost development.".to_string(),
        );
    }

    Ok(())
}

#[tauri::command]
fn get_worker_binary_status() -> WorkerBinaryInfo {
    if let Some(path) = find_worker_binary() {
        WorkerBinaryInfo {
            found: true,
            path: Some(path.to_string_lossy().to_string()),
            version: Some("0.3.0".to_string()),
        }
    } else {
        WorkerBinaryInfo {
            found: false,
            path: None,
            version: None,
        }
    }
}

#[tauri::command]
fn get_local_worker_status(state: State<'_, AppState>) -> Result<LocalWorkerStatus, String> {
    let mut daemon = state.daemon.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = daemon.child {
        match child.try_wait() {
            Ok(Some(status)) => {
                let code = status.code().unwrap_or(-1);
                daemon.exit_code = Some(code);
                daemon.logs.push_back(format!(
                    "[{}] [Local Daemon] Process exited with code {}",
                    chrono_like_timestamp(),
                    code
                ));
                daemon.child = None;
            }
            Ok(None) => {
                // Still running
            }
            Err(e) => {
                daemon.logs.push_back(format!(
                    "[{}] [Local Daemon] Error checking child status: {}",
                    chrono_like_timestamp(),
                    e
                ));
            }
        }
    }

    let is_running = daemon.child.is_some();

    Ok(LocalWorkerStatus {
        running: is_running,
        pid: daemon.pid,
        coordinator_url: daemon.coordinator_url.clone(),
        worker_id: daemon.worker_id.clone(),
        exit_code: daemon.exit_code,
        binary_path: daemon.binary_path.clone(),
    })
}

#[tauri::command]
fn start_local_worker(
    state: State<'_, AppState>,
    coordinator_url: String,
    worker_id: Option<String>,
    worker_name: Option<String>,
    auth_token: Option<String>,
) -> Result<LocalWorkerStatus, String> {
    validate_coordinator_url(&coordinator_url)?;

    let mut daemon = state.daemon.lock().map_err(|e| e.to_string())?;

    // Check if already running
    if let Some(ref mut child) = daemon.child {
        if let Ok(None) = child.try_wait() {
            return Err("Local worker agent daemon is already running".to_string());
        }
    }

    let binary_path = find_worker_binary().ok_or_else(|| {
        "websync-worker executable not found. Please build or install the worker agent binary first."
            .to_string()
    })?;

    let binary_str = binary_path.to_string_lossy().to_string();

    daemon.logs.push_back(format!(
        "[{}] [Local Daemon] Spawning worker binary: {}",
        chrono_like_timestamp(),
        binary_str
    ));

    let mut cmd = Command::new(&binary_path);
    cmd.arg("--coordinator-url").arg(&coordinator_url);

    let assigned_worker_id = worker_id.unwrap_or_else(|| {
        format!("worker-desktop-{}", std::process::id())
    });

    cmd.arg("--worker-id").arg(&assigned_worker_id);

    if let Some(name) = worker_name {
        cmd.arg("--worker-name").arg(name);
    }

    if let Some(token) = auth_token {
        cmd.env("WEBSYNC_WORKER_AUTH_TOKEN", &token);
        cmd.arg("--token").arg(token);
    }

    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn worker agent binary: {}", e))?;

    let pid = child.id();
    daemon.pid = Some(pid);
    daemon.coordinator_url = Some(coordinator_url.clone());
    daemon.worker_id = Some(assigned_worker_id.clone());
    daemon.binary_path = Some(binary_str);
    daemon.exit_code = None;

    daemon.logs.push_back(format!(
        "[{}] [Local Daemon] Worker agent process started (PID: {}) connecting to {}",
        chrono_like_timestamp(),
        pid,
        coordinator_url
    ));

    // Capture stdout
    if let Some(stdout) = child.stdout.take() {
        let daemon_clone = Arc::clone(&state.daemon);
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if let Ok(mut lock) = daemon_clone.lock() {
                        if lock.logs.len() >= MAX_LOG_LINES {
                            lock.logs.pop_front();
                        }
                        lock.logs.push_back(format!("[OUT] {}", l));
                    }
                }
            }
        });
    }

    // Capture stderr
    if let Some(stderr) = child.stderr.take() {
        let daemon_clone = Arc::clone(&state.daemon);
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if let Ok(mut lock) = daemon_clone.lock() {
                        if lock.logs.len() >= MAX_LOG_LINES {
                            lock.logs.pop_front();
                        }
                        lock.logs.push_back(format!("[ERR] {}", l));
                    }
                }
            }
        });
    }

    daemon.child = Some(child);

    Ok(LocalWorkerStatus {
        running: true,
        pid: Some(pid),
        coordinator_url: Some(coordinator_url),
        worker_id: Some(assigned_worker_id),
        exit_code: None,
        binary_path: daemon.binary_path.clone(),
    })
}

#[tauri::command]
fn stop_local_worker(state: State<'_, AppState>) -> Result<LocalWorkerStatus, String> {
    let mut daemon = state.daemon.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = daemon.child.take() {
        let _ = child.kill();
        let status = child.wait().ok();
        let code = status.and_then(|s| s.code()).unwrap_or(0);
        daemon.exit_code = Some(code);
        daemon.logs.push_back(format!(
            "[{}] [Local Daemon] Worker agent stopped (Exit code: {})",
            chrono_like_timestamp(),
            code
        ));
    } else {
        daemon.logs.push_back(format!(
            "[{}] [Local Daemon] Worker agent was not running.",
            chrono_like_timestamp()
        ));
    }

    Ok(LocalWorkerStatus {
        running: false,
        pid: daemon.pid,
        coordinator_url: daemon.coordinator_url.clone(),
        worker_id: daemon.worker_id.clone(),
        exit_code: daemon.exit_code,
        binary_path: daemon.binary_path.clone(),
    })
}

#[tauri::command]
fn get_local_worker_logs(state: State<'_, AppState>, limit: Option<usize>) -> Vec<String> {
    if let Ok(daemon) = state.daemon.lock() {
        let max_items = limit.unwrap_or(200);
        let count = daemon.logs.len();
        let start = if count > max_items { count - max_items } else { 0 };
        daemon.logs.iter().skip(start).cloned().collect()
    } else {
        Vec::new()
    }
}

fn chrono_like_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    let total_secs = now.as_secs();
    let secs = total_secs % 60;
    let mins = (total_secs / 60) % 60;
    let hours = (total_secs / 3600) % 24;
    format!("{:02}:{:02}:{:02}Z", hours, mins, secs)
}

fn main() {
    let initial_logs = VecDeque::from(vec![
        format!("[{}] [WebSync Desktop] Initialized native process shell.", chrono_like_timestamp()),
    ]);

    let app_state = AppState {
        daemon: Arc::new(Mutex::new(WorkerDaemonState {
            child: None,
            pid: None,
            coordinator_url: None,
            worker_id: None,
            binary_path: None,
            exit_code: None,
            logs: initial_logs,
        })),
    };

    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_worker_binary_status,
            get_local_worker_status,
            start_local_worker,
            stop_local_worker,
            get_local_worker_logs,
        ])
        .run(tauri::generate_context!())
        .expect("error while running WebSync AI desktop application");
}

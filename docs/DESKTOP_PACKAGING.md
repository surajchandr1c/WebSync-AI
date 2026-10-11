# WebSync AI — Desktop & Worker Packaging Guide

This document describes the cross-platform packaging architecture, native build instructions, runtime requirements, and security configurations for the **WebSync AI Desktop Application** and the **Standalone Worker Agent**.

---

## 1. Architectural Architecture & Process Separation

WebSync AI is engineered with a strict logical separation between distributed components:

```
┌─────────────────────────────────────────────────────────────┐
│                   WebSync AI Desktop UI                     │
│         (Tauri 2 Native Webview Shell + React 19)           │
│                                                             │
│  - Cluster Overview          - Resource Telemetry           │
│  - Worker Fleet Monitoring   - Activity Event Feed          │
│  - Distributed Job Dispatch  - Security & Settings          │
└──────────────┬───────────────────────────────┬──────────────┘
               │ HTTPS / WSS                   │ Native Commands
               │ (Strict Security Policy)      │ (IPC via Tauri)
               ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│     FastAPI Coordinator       │ │ Local Worker Daemon (opt) │
│ (Remote Cluster Orchestration)│ │ (websync-worker.exe / elf)│
│                               │ │                           │
│ - Node Registry & Telemetry   │ │ - Real CPU/RAM/GPU Detect │
│ - Adaptive Scheduler          │ │ - Sandboxed Task Executor │
│ - Token Revocation & Auth     │ │ - Streaming Console Out   │
└───────────────────────────────┘ └───────────────────────────┘
```

### Key Principles
1. **No Embedded Coordinator**: The desktop application functions purely as a native monitoring and control client. It does **not** bundle a mandatory local coordinator, preventing port conflicts and memory bloat.
2. **Configurable Endpoints**: The user configures their target coordinator endpoint. Remote connections **strictly require HTTPS / WSS**; plain HTTP / WS is rejected with security violations unless targeting `localhost` / `127.0.0.1`.
3. **Optional Local Worker Management**: The desktop client detects and can spawn/stop the standalone `websync-worker` binary as an independent child process, capturing live stdout/stderr streams into a ring-buffer console.

---

## 2. Desktop Application Configuration & Hardening

### Tauri 2 Configuration (`apps/desktop/src-tauri/tauri.conf.json`)
- **Product Name**: `WebSync AI`
- **Identifier**: `com.websyncai.desktop`
- **Version**: `0.3.0`
- **Window Specs**: 1200x800 minimum 900x600, resizable.
- **Content Security Policy (CSP)**:
  ```http
  default-src 'self';
  connect-src 'self' http: https: ws: wss:;
  img-src 'self' data: https:;
  style-src 'self' 'unsafe-inline';
  font-src 'self';
  script-src 'self';
  ```
- **Permission Boundaries**: Minimal native capabilities; file system access is constrained, and child process execution is mediated entirely through validated Rust IPC commands.

---

## 3. Native Tauri Commands & Local Worker Daemon

The Rust backend (`apps/desktop/src-tauri/src/main.rs`) exposes safe IPC commands:

| Command | Signature | Description |
|---|---|---|
| `get_worker_binary_status` | `() -> WorkerBinaryInfo` | Detects presence, path, and version of `websync-worker.exe` |
| `get_local_worker_status` | `() -> Result<LocalWorkerStatus, String>` | Queries whether local worker process is alive, PID, and exit code |
| `start_local_worker` | `(coordinator_url, worker_id, worker_name, auth_token)` | Validates URL security, spawns worker process, captures stdout/stderr threads |
| `stop_local_worker` | `() -> Result<LocalWorkerStatus, String>` | Gracefully terminates child process via SIGTERM/kill |
| `get_local_worker_logs` | `(limit: Option<usize>) -> Vec<String>` | Retrieves recent console output lines from in-memory ring buffer |

---

## 4. Standalone Worker Agent Packaging (PyInstaller)

The Python worker agent is packaged into a self-contained single-file executable requiring no local Python installation.

### Specification: `worker/websync-worker.spec`
- Bundles Python 3.12/3.13 runtime, `httpx`, `websockets`, `psutil`, `pydantic`, `pydantic_settings`.
- Dynamic hardware telemetry detection intact (including NVIDIA NVML CUDA detection).

### Build Command
```powershell
pyinstaller worker/websync-worker.spec
```
Output: `worker/dist/websync-worker.exe` (Windows) or `worker/dist/websync-worker` (Linux / macOS).

### CLI Arguments
```text
websync-worker [OPTIONS]

Options:
  --coordinator-url TEXT  Base URL of the coordinator [default: http://localhost:8000]
  --worker-id TEXT        Unique worker ID [default: auto-generated hostname-uuid]
  --worker-name TEXT      Human-readable display name
  --token TEXT            Authentication token for enrollment
  --inspect               Print local hardware specs (CPU/RAM/GPU) and exit
  --once                  Perform single heartbeat check and exit
  --help                  Show help message
```

### Verification
```powershell
.\worker\dist\websync-worker.exe --inspect
```
Sample verified output:
```json
{
  "hostname": "DESKTOP-SURAJ",
  "platform": "windows",
  "cpu_cores_physical": 8,
  "cpu_cores_logical": 12,
  "total_memory_gb": 15.68,
  "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
  "gpu_memory_gb": 4.0
}
```

---

## 5. Platform Requirements & Prerequisites

### Windows
- **Operating System**: Windows 10 (Build 19041+) or Windows 11.
- **WebView2 Runtime**: EverGreen WebView2 Runtime (pre-installed on Windows 10/11).
- **C++ Linker**: Visual Studio 2022 C++ Build Tools or MSYS2 MinGW-w64 (UCRT64 `gcc.exe`).
- **Rust**: `stable-x86_64-pc-windows-gnu` or `stable-x86_64-pc-windows-msvc`.

### Linux
- **Operating System**: Ubuntu 22.04 LTS+, Debian 12+, Fedora 38+.
- **Packages**:
  ```bash
  sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
  ```

### macOS
- **Operating System**: macOS 12 (Monterey) or later (Apple Silicon M1/M2/M3 or Intel x86_64).
- **Prerequisites**: Xcode Command Line Tools (`xcode-select --install`).

---

## 6. Code Signing & Release Gateways

### Windows SmartScreen
- **Requirement**: Microsoft Authenticode Digital Signature (`.pfx` certificate).
- **Signing Command**:
  ```powershell
  signtool sign /f websync_cert.pfx /p $CERT_PASSWORD /tr http://timestamp.digicert.com /td sha256 /fd sha256 apps\desktop\src-tauri\target\release\bundle\msi\WebSync-AI_0.3.0_x64.msi
  ```
- **Unsigned Behavior**: Windows SmartScreen displays "Unknown Publisher" prompt until reputation builds or certificate is attached.

### macOS Gatekeeper & Notarization
- **Requirement**: Apple Developer ID Application Certificate and Apple Notary Service credentials.
- **Signing Command**:
  ```bash
  codesign --deep --force --verify --verbose --sign "Developer ID Application: ..." "WebSync AI.app"
  xcrun notarytool submit "WebSync AI.dmg" --keychain-profile "AC_PASSWORD" --wait
  xcrun stapler staple "WebSync AI.dmg"
  ```
- **Unsigned Behavior**: Gatekeeper blocks app with "WebSync AI cannot be opened because it is from an unidentified developer."

### Linux Distribution Packages
- **Debian (`.deb`)**: Package created using `ar` / `tar.xz` standard structure.
- **AppImage**: Executable runtime bundling all system libraries (except glibc).
- **GPG Signing**: Detached signature `.asc` generated via `gpg --detach-sign -a <package>`.

---

## 7. Multi-Platform CI/CD Pipeline

The repository includes a complete GitHub Actions matrix workflow at `.github/workflows/desktop-release.yml` triggering on version tags (`v*`):

1. **`build-worker` Matrix**:
   - `windows-latest` -> `websync-worker-windows-amd64.exe`
   - `ubuntu-22.04` -> `websync-worker-linux-amd64`
   - `macos-latest` -> `darwin-arm64` universal worker binary
2. **`build-desktop` Matrix**:
   - `windows-latest` -> `.msi` and `.exe` installers
   - `ubuntu-22.04` -> `.deb` and `.AppImage` packages
   - `macos-latest` -> `.dmg` disk image and `.app` bundle

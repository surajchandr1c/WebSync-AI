# WebSync AI — Hackathon Demonstration Guide

This guide provides a reproducible, step-by-step 5-minute live demonstration script for WebSync AI, designed for hackathon judges and technical evaluators.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │          WebSync AI Next.js Dashboard        │
                      │         & Tauri Cross-Platform Desktop       │
                      └──────────────────────▲───────────────────────┘
                                             │ WebSocket Event Stream
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │          WebSync AI Coordinator              │
                      │   (FastAPI + SQLite/Postgres + Scheduler)    │
                      └──────────────▲────────────────▲──────────────┘
                                     │                │
           WebSocket + Heartbeat     │                │ WebSocket + Heartbeat
                                     │                │
            ┌────────────────────────┴───┐        ┌───┴────────────────────────┐
            │       Worker Node Alpha    │        │       Worker Node Beta     │
            │   (Windows + RTX 3050 GPU) │        │     (Secondary Compute)    │
            └────────────────────────────┘        └────────────────────────────┘
```

---

## Prerequisites & Pre-Flight Check

Ensure you are in the repository root `WebSync_AI` and the Python virtual environment is active:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
$env:PATH = "C:\Users\Suraj\AppData\Roaming\npm;C:\Program Files\nodejs;" + $env:PATH
```

---

## 10-Step Live Demonstration Script

### Step 1: Launch the Coordinator Service
Open **Terminal 1** and start the FastAPI Coordinator:
```powershell
python -m uvicorn coordinator.main:app --host 127.0.0.1 --port 8000 --reload
```
*Expected Output:*
`[INFO] Initializing WebSync AI Coordinator v0.2.0 in 'development' mode`
`[INFO] Database schemas initialized successfully.`
`[INFO] Uvicorn running on http://127.0.0.1:8000`

---

### Step 2: Launch the Next.js Dashboard / Tauri Desktop Application
Open **Terminal 2** and start the real-time Dashboard:
```powershell
pnpm --filter @websync/dashboard dev
```
Navigate your browser to `http://localhost:3000`. You will see the WebSync AI Cluster Overview, active workers count (0), and real-time WebSocket connection indicator.

*(Optional Native Desktop Shell):*
```powershell
cd apps/desktop
pnpm tauri dev
```

---

### Step 3: Launch Worker Node Alpha (Primary GPU Node)
Open **Terminal 3** and run the first worker agent (or standalone executable):
```powershell
python -m worker.agent.main --coordinator-url http://127.0.0.1:8000 --worker-id worker-alpha --display-name "Alpha (RTX 3050)"
```
*Key Highlights for Judges:*
- Demonstrates authentic NVIDIA NVML hardware discovery.
- Registers with coordinator and establishes real-time WebSocket stream (`/ws/worker`).
- Live Dashboard immediately animates and displays Worker Alpha online with CPU/RAM gauges.

---

### Step 4: Launch Worker Node Beta (Secondary Compute Node)
Open **Terminal 4** and launch a second concurrent worker:
```powershell
python -m worker.agent.main --coordinator-url http://127.0.0.1:8000 --worker-id worker-beta --display-name "Beta (Compute Node)"
```
*Key Highlights for Judges:*
- Dashboard now displays **2 Active Nodes** with heterogeneous hardware specs.

---

### Step 5: Submit Verifiable Numerical Matrix Workload ($A \times B$)
Open **Terminal 5** (or use the Dashboard "Submit Workload" UI). Submit a verifiable matrix multiplication task:
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/jobs `
  -H "Content-Type: application/json" `
  -d '{
    "name": "matrix-demo-mult",
    "job_type": "matrix_multiply",
    "input_payload": {
      "matrix_a": [[1.0, 2.0], [3.0, 4.0]],
      "matrix_b": [[5.0, 6.0], [7.0, 8.0]]
    },
    "requirements": { "min_ram_mb": 512 }
  }'
```
*Expected Mathematical Computation:*
$$A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}, \quad B = \begin{pmatrix} 5 & 6 \\ 7 & 8 \end{pmatrix} \implies C = \begin{pmatrix} 19 & 22 \\ 43 & 50 \end{pmatrix}$$
$$\text{Trace} = 19 + 50 = 69.0, \quad C_{0,0} = 19.0$$

---

### Step 6: Verify Computation Output & Latency
Fetch the verified execution result:
```powershell
curl http://127.0.0.1:8000/api/v1/jobs/latest/result
# or query by returned job_id:
curl http://127.0.0.1:8000/api/v1/jobs/<JOB_ID>/result
```
*Key Highlights for Judges:*
- Demonstrates sub-100ms end-to-end distributed dispatch, execution, and result ingestion.
- Shows real numerical output: `Trace checksum: 69.0. Sample element c[0][0]: 19.0`.

---

### Step 7: Demonstrate Adaptive Resource-Aware Load Diversion
Simulate a high-load condition on Worker Alpha by sending an artificial heartbeat with 95% CPU utilization:
```powershell
# Worker Alpha reports 95% CPU
curl -X POST http://127.0.0.1:8000/api/v1/workers/heartbeat `
  -H "Authorization: Bearer <ALPHA_WORKER_TOKEN>" `
  -H "Content-Type: application/json" `
  -d '{"cpu_utilization": 95.0, "available_ram_bytes": 10737418240, "active_job_count": 0}'

# Submit a new job
curl -X POST http://127.0.0.1:8000/api/v1/jobs `
  -H "Content-Type: application/json" `
  -d '{
    "name": "load-diversion-job",
    "job_type": "data_processing",
    "input_payload": {"records": [{"id": 1, "val": 42}]},
    "requirements": {"min_ram_mb": 256}
  }'
```
*Key Highlights for Judges:*
- Coordinator Adaptive Scheduler evaluates both workers, penalizes Alpha for high CPU (95%), and automatically diverts the job to Worker Beta.
- Decision breakdown is visible in `placement_reason`.

---

### Step 8: Hardware Constraint Enforcement (GPU Workload)
Submit a workload with `"gpu_required": true`:
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/jobs `
  -H "Content-Type: application/json" `
  -d '{
    "name": "gpu-accelerated-job",
    "job_type": "matrix_multiply",
    "input_payload": {"dimension": 10},
    "requirements": { "gpu_required": true, "min_ram_mb": 512 }
  }'
```
*Key Highlights for Judges:*
- The scheduler automatically excludes CPU-only nodes and routes exclusively to Worker Alpha (which detected NVIDIA RTX 3050 hardware).

---

### Step 9: Simulate Network Fault & Automatic Job Recovery
Submit a long-running or queued job, then immediately simulate worker disconnection:
```powershell
# Disconnect Worker Beta
curl -X POST http://127.0.0.1:8000/api/v1/workers/worker-beta/disconnect `
  -H "Authorization: Bearer <BETA_WORKER_TOKEN>"
```
*Key Highlights for Judges:*
- The Coordinator detects disconnection immediately.
- Scheduled jobs are automatically recovered, placed back in `QUEUED` state, and reassigned to online nodes.
- Shows distributed system resilience and zero job loss.

---

### Step 10: Security Controls & Administrative Node Revocation
Demonstrate Phase 7 administrative revocation:
```powershell
# Login as Administrator
$loginRes = curl -X POST http://127.0.0.1:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username": "admin", "password": "AdminPassword123!"}' | ConvertFrom-Json
$adminToken = $loginRes.access_token

# Administratively revoke Worker Beta
curl -X POST http://127.0.0.1:8000/api/v1/workers/worker-beta/revoke `
  -H "Authorization: Bearer $adminToken"
```
*Key Highlights for Judges:*
- Worker credentials are permanently marked `is_revoked: true`.
- WebSocket connection is forcibly terminated with code 1008.
- Subsequent heartbeats are rejected with `403 Forbidden ("Worker credentials have been revoked.")`.

---

## Live Demo Fallback & Automated Replay

In case live network conditions or time constraints during a hackathon pitch prevent multi-terminal setup, run the **Single-Command Automated Live Validation**:

```powershell
python scripts/phase9_system_validation.py
```
This runs the entire 10-step distributed pipeline against a live in-process server in **under 3 seconds**, printing verified mathematical execution output, latencies, and security assertions directly in the terminal.

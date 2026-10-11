# WebSync AI — API Specification

## Base URL
- Production: `https://<coordinator-host>/api/v1`
- Local Development: `http://localhost:8000/api/v1`
- WebSocket Endpoint: `ws://localhost:8000/ws`

All request and response bodies use standard `application/json` format unless streaming logs or binary job artifacts.

---

## 1. System & Health

### `GET /api/v1/health`
Returns the operational health and environment metadata of the coordinator.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "service": "coordinator",
  "version": "0.1.0",
  "timestamp": "2026-10-11T17:10:00Z",
  "uptime_seconds": 124.5,
  "database": "connected"
}
```

---

## 2. Worker Lifecycle & Telemetry

### `POST /api/v1/workers/register`
Invoked by a worker node upon startup to register itself with the coordinator.

**Request Body**:
```json
{
  "worker_id": "worker-linux-01",
  "hostname": "arch-desktop",
  "platform": "Linux",
  "platform_version": "6.12.1-zen",
  "cpu_count_logical": 16,
  "cpu_count_physical": 8,
  "total_memory_bytes": 34359738368,
  "gpu_info": [
    {
      "name": "NVIDIA GeForce RTX 4070",
      "memory_total_bytes": 12884901888
    }
  ],
  "supported_runtimes": ["python", "shell"]
}
```

**Response `201 Created`**:
```json
{
  "status": "registered",
  "worker_id": "worker-linux-01",
  "heartbeat_interval_seconds": 10,
  "assigned_token": "jwt-or-session-token"
}
```

### `POST /api/v1/workers/{worker_id}/heartbeat`
Periodic ping sent by active workers providing real-time hardware telemetry.

**Request Body**:
```json
{
  "timestamp": "2026-10-11T17:10:10Z",
  "cpu_percent": 18.4,
  "memory_used_bytes": 8589934592,
  "memory_available_bytes": 25769803776,
  "disk_free_bytes": 429496729600,
  "active_jobs_count": 1,
  "gpu_metrics": [
    {
      "utilization_percent": 42.0,
      "memory_used_bytes": 4294967296
    }
  ]
}
```

### `GET /api/v1/workers`
Returns a list of all registered workers and their current statuses. Query parameters support filtering by status (`online`, `busy`, `offline`).

---

## 3. Distributed Job Lifecycle

### `POST /api/v1/jobs`
Submits a computational workload for scheduling.

**Request Body**:
```json
{
  "name": "data-crunch-batch-01",
  "runtime": "python",
  "entrypoint": "main.py",
  "payload_url": null,
  "script_content": "import math; print(math.factorial(500))",
  "requirements": {
    "min_cpu_cores": 2,
    "min_ram_mb": 1024,
    "gpu_required": false
  },
  "timeout_seconds": 300
}
```

**Response `202 Accepted`**:
```json
{
  "job_id": "job-7b89f2a4",
  "status": "queued",
  "created_at": "2026-10-11T17:10:15Z"
}
```

### `GET /api/v1/jobs/{job_id}`
Retrieves job status, assigned worker, start/completion times, exit code, and execution summary.

### `GET /api/v1/jobs/{job_id}/logs`
Fetches real-time or completed standard output and error streams.

---

## 4. WebSocket Real-Time Feeds

### `ws://localhost:8000/ws/dashboard`
Stream for web dashboard clients. Pushes:
- `worker_connected`
- `worker_heartbeat`
- `worker_disconnected`
- `job_submitted`
- `job_dispatched`
- `job_completed`
- `cluster_metrics`

### `ws://localhost:8000/ws/worker/{worker_id}`
Bi-directional control channel between coordinator and worker node:
- Worker -> Coordinator: Heartbeat & live job stdout/stderr frames.
- Coordinator -> Worker: Task dispatch commands (`dispatch_job`, `cancel_job`).

# WebSync AI — Coordinator API Specification (Phase 2)

## Base URL
- Production: `https://<coordinator-host>/api/v1`
- Local Development: `http://localhost:8000/api/v1`
- WebSocket Endpoint: `ws://localhost:8000/ws/dashboard`

All request and response bodies use standard `application/json` format.

---

## 1. System Health

### `GET /api/v1/health`
Returns real-time service uptime, API version, and live database connectivity status.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "service": "WebSync AI Coordinator",
  "version": "0.2.0",
  "timestamp": "2026-10-11T17:35:00Z",
  "uptime_seconds": 128.4,
  "python_version": "3.13.5",
  "environment": "development",
  "database": "healthy"
}
```

---

## 2. Authentication & User Management

### `POST /api/v1/auth/register`
Registers an operator or admin user account.

**Request Body**:
```json
{
  "username": "operator1",
  "email": "operator1@websync.ai",
  "password": "secure_password_123",
  "role": "operator"
}
```

**Response `201 Created`**:
```json
{
  "id": "e81d7d08-4d51-40be-a006-2c5e53303666",
  "username": "operator1",
  "email": "operator1@websync.ai",
  "role": "operator",
  "is_active": true,
  "created_at": "2026-10-11T17:35:10Z"
}
```

### `POST /api/v1/auth/login`
Authenticates user credentials and issues a short-lived Bearer JWT token.

**Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in_seconds": 3600
}
```

### `GET /api/v1/auth/me`
Retrieves authenticated profile. Requires `Authorization: Bearer <user_token>`.

---

## 3. Worker Node Lifecycle & Telemetry

### `POST /api/v1/workers/register`
Registers a worker node with the coordinator and issues a scoped worker token.
**Headers**: `X-Worker-Auth-Token: <dev-token>` or `Authorization: Bearer <token>`

**Request Body**:
```json
{
  "worker_id": "worker-linux-01",
  "display_name": "Lab Arch Workstation",
  "hostname": "arch-desktop",
  "platform": "Linux",
  "platform_version": "6.12.1-zen",
  "cpu_utilization": 14.2,
  "total_ram_bytes": 34359738368,
  "available_ram_bytes": 28991029248,
  "supported_workloads": ["matrix_multiply", "data_processing", "image_processing"],
  "gpu_available": true,
  "gpu_metadata": [
    {
      "name": "NVIDIA GeForce RTX 4070",
      "memory_total_bytes": 12884901888
    }
  ]
}
```

**Response `201 Created`**:
```json
{
  "worker_id": "worker-linux-01",
  "display_name": "Lab Arch Workstation",
  "hostname": "arch-desktop",
  "platform": "Linux",
  "connection_status": "online",
  "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "heartbeat_interval_seconds": 10
}
```

### `POST /api/v1/workers/heartbeat`
Updates real-time resource telemetry and refreshes online status.
**Headers**: `Authorization: Bearer <worker_token>`

**Request Body**:
```json
{
  "cpu_utilization": 22.8,
  "available_ram_bytes": 25769803776,
  "active_job_count": 0,
  "gpu_metadata": []
}
```

**Response `200 OK`**: returns updated `WorkerResponse`.

### `GET /api/v1/workers`
Returns a paginated list of registered workers. Dynamic status evaluation marks nodes as `offline` if their heartbeat exceeds `WORKER_HEARTBEAT_TIMEOUT_SECONDS`.

**Query Parameters**:
- `status`: optional filter (`online`, `busy`, `draining`, `offline`, `disconnected`)
- `page`: default `1`
- `page_size`: default `50` (max 100)

### `GET /api/v1/workers/{worker_id}`
Returns details for a single worker node.

### `POST /api/v1/workers/{worker_id}/disconnect`
Sets worker status to `disconnected` and broadcasts `worker.disconnected` event.

---

## 4. Job Management

### Approved Workload Types
1. `matrix_multiply`: Distributed linear algebra computations.
2. `data_processing`: Large dataset transforms and aggregations.
3. `image_processing`: Batch image transformations and resizing.

### Job State Lifecycle
```text
  ┌─────────┐       ┌───────────┐       ┌─────────┐       ┌───────────┐
  │ QUEUED  │ ───>  │ SCHEDULED │ ───>  │ RUNNING │ ───>  │ COMPLETED │
  └─────────┘       └───────────┘       └─────────┘       └───────────┘
       │                  │                  │
       v                  v                  v
  ┌───────────┐      ┌───────────┐      ┌─────────┐
  │ CANCELLED │      │ CANCELLED │      │ FAILED  │
  └───────────┘      └───────────┘      └─────────┘
```

### `POST /api/v1/jobs`
Submits a computational workload.

**Request Body**:
```json
{
  "name": "matrix-benchmark-1000",
  "job_type": "matrix_multiply",
  "input_payload": {
    "dimension": 1000,
    "seed": 42
  },
  "requirements": {
    "min_cpu_cores": 4,
    "min_ram_mb": 2048,
    "gpu_required": false
  }
}
```

**Response `201 Created`**:
```json
{
  "job_id": "97e6820c-99c0-43b9-913a-a5f1a5472856",
  "name": "matrix-benchmark-1000",
  "job_type": "matrix_multiply",
  "status": "QUEUED",
  "input_payload": { "dimension": 1000, "seed": 42 },
  "requirements": { "min_cpu_cores": 4, "min_ram_mb": 2048, "gpu_required": false },
  "created_at": "2026-10-11T17:35:30Z"
}
```

### `GET /api/v1/jobs`
List submitted jobs with pagination and optional filters (`status`, `job_type`).

### `GET /api/v1/jobs/{job_id}`
Get job details, assignment, and status.

### `POST /api/v1/jobs/{job_id}/cancel`
Requests cancellation of a non-terminal job.

### `GET /api/v1/jobs/{job_id}/result`
Retrieves completion output and execution summary for `COMPLETED` or `FAILED` jobs.

### `PATCH /api/v1/jobs/{job_id}/status`
Transitions job execution state according to the valid state machine.

---

## 5. WebSocket Real-Time Events

### `WS /ws/dashboard`
Connect to receive real-time JSON frames emitted when coordinator state changes:

```json
{
  "event": "worker.updated",
  "timestamp": "2026-10-11T17:35:45.123456Z",
  "data": {
    "worker_id": "worker-linux-01",
    "cpu_utilization": 34.5,
    "available_ram_bytes": 22000000000,
    "active_job_count": 1,
    "status": "busy"
  }
}
```

**Published Events**:
- `worker.connected`
- `worker.updated`
- `worker.disconnected`
- `job.created`
- `job.updated`
- `job.completed`
- `job.failed`

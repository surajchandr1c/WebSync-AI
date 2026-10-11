# WebSync AI — Security Findings & Architecture Review (Phase 7)

**Audit Date**: 2026-10-12  
**Scope**: FastAPI Coordinator, Python Worker Agent, Real-Time WebSocket Protocol, Scheduler Engine, API Endpoints  
**Status**: Resolved / Hardened in Phase 7  

---

## 1. Executive Summary

A comprehensive application security and distributed systems review of WebSync AI was conducted across authentication, authorization, communication transport, workload execution, resource enforcement, and failure recovery.

Ten security and reliability findings were identified, ranging from Critical to Low severity. All critical, high, and medium vulnerabilities have been directly remediated in the codebase with automated regression tests.

---

## 2. Findings Matrix

| Finding ID | Severity | Component | Summary | Status |
| :--- | :---: | :--- | :--- | :---: |
| **WS-SEC-01** | **CRITICAL** | Coordinator Auth (`routes/auth.py`) | Privilege Escalation: Self-Service Admin Assignment | **FIXED** |
| **WS-SEC-02** | **HIGH** | Coordinator Jobs (`routes/jobs.py`) | Missing Object-Level Ownership Checks on Jobs & Results | **FIXED** |
| **WS-SEC-03** | **HIGH** | Coordinator Workers (`routes/workers.py`) | Cross-Worker Action Spoofing & Unauthenticated Disconnect | **FIXED** |
| **WS-SEC-04** | **HIGH** | Coordinator Core (`core/auth.py`, `config.py`) | Permissive Pre-Shared Development Token in Production | **FIXED** |
| **WS-SEC-05** | **MEDIUM** | Coordinator Auth & Worker (`routes/auth.py`, `routes/workers.py`) | Missing Rate Limiting on Authentication & Registration | **FIXED** |
| **WS-SEC-06** | **MEDIUM** | Coordinator & Worker (`schemas/job.py`, `executor.py`) | Unbounded Input Payload and Result Output Sizes | **FIXED** |
| **WS-SEC-07** | **MEDIUM** | Coordinator Workers (`routes/workers.py`) | Missing Administrative Worker Revocation Endpoint | **FIXED** |
| **WS-SEC-08** | **MEDIUM** | Coordinator Lifecycle (`main.py`, `scheduler/engine.py`) | Unrecovered In-Flight Jobs on Coordinator Restart | **FIXED** |
| **WS-SEC-09** | **LOW** | Logging (`coordinator`, `worker`) | Exposure of JWTs and Bearer Tokens in Logs | **FIXED** |
| **WS-SEC-10** | **LOW** | Worker Agent (`worker/agent/config.py`, `main.py`) | Missing Computer-Owner Resource-Sharing Controls | **FIXED** |

---

## 3. Detailed Findings & Remediation

### WS-SEC-01: Privilege Escalation via Self-Service Admin Role
- **Severity**: Critical
- **Affected**: `services/coordinator/src/coordinator/api/routes/auth.py`
- **Vulnerability**: The public user registration endpoint (`POST /api/v1/auth/register`) accepted a client-supplied `role` field. Any unauthenticated caller could register with `role: "admin"`.
- **Remediation**:
  - Public registration is strictly restricted to `role="user"`.
  - The `admin` role can only be assigned by existing authenticated administrators via administrative management, or via an initial bootstrap initialization when no users exist in the database.

### WS-SEC-02: Missing Object-Level Authorization on Jobs and Results
- **Severity**: High
- **Affected**: `services/coordinator/src/coordinator/api/routes/jobs.py`
- **Vulnerability**: Endpoints `GET /jobs/{job_id}`, `GET /jobs/{job_id}/result`, and `GET /jobs/{job_id}/events` lacked user ownership validation. Any caller knowing a `job_id` could inspect job parameters, execution output, and audit history.
- **Remediation**:
  - Enforced authentication and ownership checks on all job inspection endpoints.
  - Non-admin users are restricted to jobs they created (`job.created_by_user_id == current_user.id`).
  - Admins retain cluster-wide audit and inspection access.

### WS-SEC-03: Cross-Worker Action Spoofing & Unauthenticated Disconnect
- **Severity**: High
- **Affected**: `services/coordinator/src/coordinator/api/routes/workers.py`
- **Vulnerability**:
  1. `POST /workers/{worker_id}/disconnect` was completely unauthenticated.
  2. Endpoints `/{worker_id}/jobs/{job_id}/ack`, `start`, and `result` accepted `worker_id` as a path parameter without verifying that it matched `current_worker.worker_id` from the bearer token.
- **Remediation**:
  - Added verification requiring `current_worker.worker_id == worker_id` for all worker job actions.
  - Restricted worker disconnection to the authenticated worker itself or an administrator.

### WS-SEC-04: Permissive Development Token in Production
- **Severity**: High
- **Affected**: `services/coordinator/src/coordinator/config.py`, `coordinator/core/auth.py`
- **Vulnerability**: `WORKER_DEV_AUTH_TOKEN` allowed worker registration without checking if `ENVIRONMENT == "production"`.
- **Remediation**:
  - In `production` mode, `WORKER_DEV_AUTH_TOKEN` is deactivated.
  - Added startup configuration validator ensuring that in production, weak secrets raise an immediate fatal error preventing coordinator boot.

### WS-SEC-05: Missing Rate Limiting on Authentication Endpoints
- **Severity**: Medium
- **Affected**: `services/coordinator/src/coordinator/api/routes/auth.py`, `routes/workers.py`
- **Vulnerability**: Authentication endpoints `/auth/login`, `/auth/register`, and `/workers/register` had no rate limiting, leaving them susceptible to brute-force credential stuffing and DoS attacks.
- **Remediation**:
  - Implemented an in-memory sliding-window rate limiter in `coordinator/core/rate_limit.py`.
  - Rate limits applied: 10 attempts/minute for login; 20 attempts/minute for worker registration. Returns HTTP 429 Too Many Requests with `Retry-After` header.

### WS-SEC-06: Unbounded Input Payload and Result Output Sizes
- **Severity**: Medium
- **Affected**: `coordinator/schemas/job.py`, `worker/agent/executor.py`, `coordinator/api/routes/ws.py`
- **Vulnerability**: Clients could submit multi-megabyte input payloads or generate unbounded output buffers, inducing out-of-memory crashes.
- **Remediation**:
  - Capped `input_payload` serialized size at 2MB (`MAX_JOB_INPUT_BYTES`).
  - Capped maximum job execution timeout at 3600 seconds.
  - Bounded executor output size at 100KB with truncation markers.
  - Enforced a 2MB maximum frame limit on incoming WebSocket messages.

### WS-SEC-07: Missing Administrative Worker Revocation Endpoint
- **Severity**: Medium
- **Affected**: `services/coordinator/src/coordinator/api/routes/workers.py`
- **Vulnerability**: Administrators could not revoke compromised worker nodes via the API.
- **Remediation**:
  - Implemented `POST /api/v1/workers/{worker_id}/revoke` (admin only).
  - Immediately marks `is_revoked = True`, cleans up assigned jobs, terminates the worker's WebSocket connection with code 1008, and broadcasts the revocation event.

### WS-SEC-08: Unrecovered In-Flight Jobs on Coordinator Restart
- **Severity**: Medium
- **Affected**: `services/coordinator/src/coordinator/main.py`
- **Vulnerability**: When the coordinator service restarted, jobs in `SCHEDULED` or `RUNNING` state remained stranded indefinitely because active WebSocket worker connections were lost.
- **Remediation**:
  - Added `recover_jobs_on_coordinator_startup` during FastAPI lifespan startup.
  - `SCHEDULED` jobs are re-queued to `QUEUED`; `RUNNING` jobs with lost workers are marked `FAILED` with explicit recovery audit events.

### WS-SEC-09: Sensitive Token Exposure in Log Output
- **Severity**: Low
- **Affected**: `services/coordinator/src/coordinator/main.py`, `worker/agent/logging_config.py`
- **Vulnerability**: Logging statements could capture raw bearer tokens or authorization headers in transit.
- **Remediation**:
  - Implemented `SensitiveDataRedactingFilter` masking JWTs (`Bearer eyJ...`), passwords, and tokens with `[REDACTED]`.

### WS-SEC-10: Computer-Owner Resource-Sharing Controls
- **Severity**: Low
- **Affected**: `worker/agent/config.py`, `worker/agent/main.py`, `worker/agent/executor.py`
- **Vulnerability**: Worker agents lacked local controls for the host owner to pause sharing or restrict CPU and RAM consumption.
- **Remediation**:
  - Added `WORKER_MAX_CPU_PERCENT` (default 90%), `WORKER_MIN_AVAILABLE_RAM_MB` (default 512MB), and `WORKER_PAUSE_SHARING` (boolean toggle).
  - Workers evaluate host health before accepting tasks and reject dispatches if host utilization exceeds limits.

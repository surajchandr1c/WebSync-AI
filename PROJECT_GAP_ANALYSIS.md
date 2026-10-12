# WebSync AI — Project Gap Analysis & Architecture Audit

**Date:** October 12, 2026  
**Auditor:** Senior Distributed Systems Architect & DevOps Specialist  
**Repository:** WebSync AI — Distributed AI Computing Platform  

---

## 1. Existing Implemented Features

The following features were verified directly against the committed source code:

### A. Central Coordinator (FastAPI)
- **Authentication & RBAC:**
  - Operator/Admin registration (`POST /api/v1/auth/register`), login (`POST /api/v1/auth/login`), profile (`GET /api/v1/auth/me`).
  - Passwords hashed with `bcrypt` with work factor verification; standard JWT tokens (HMAC-SHA256).
- **Worker Management:**
  - Registration (`POST /api/v1/workers/register`) validating platform, RAM, CPU, GPU hardware metadata, and workloads.
  - Heartbeat ingest (`POST /api/v1/workers/heartbeat`) updating CPU utilization, available RAM, active jobs, and GPU telemetry.
  - Listing (`GET /api/v1/workers`), single worker inspection (`GET /api/v1/workers/{id}`), administrative revocation (`POST /api/v1/workers/{id}/revoke`), and graceful disconnect (`POST /api/v1/workers/{id}/disconnect`).
- **Distributed Job Management:**
  - Workload submission (`POST /api/v1/jobs`), paginated queries (`GET /api/v1/jobs`), single job query (`GET /api/v1/jobs/{id}`), cancellation (`POST /api/v1/jobs/{id}/cancel`), result retrieval (`GET /api/v1/jobs/{id}/result`).
  - Strict job lifecycle state machine: `QUEUED` -> `SCHEDULED` -> `RUNNING` -> `COMPLETED` / `FAILED` / `CANCELLED`.
  - Terminal state protection: Completed, failed, and cancelled jobs are immutable.
  - Granular audit trail events logged to `job_events` table for each state transition.
- **Adaptive Resource-Aware Scheduler:**
  - Mathematical multi-criteria scoring balancing CPU headroom ($w_{cpu}=0.35$), available memory ($w_{ram}=0.45$), concurrency utilization ($w_{job}=0.20$), and GPU capability bonus.
  - Filtering by non-revocation, online/busy status, heartbeat freshness threshold, telemetry metric sanity, workload support, memory threshold, and GPU requirement.
  - Worker target constraint enforcement (`target_worker_id`).
  - Startup recovery: Coordinator resets stranded `SCHEDULED` jobs to `QUEUED` and in-flight `RUNNING` jobs to `FAILED` upon restart.
- **Real-Time Communication:**
  - Dashboard WebSocket (`/ws/dashboard`): broadcasts real-time cluster telemetry, worker connections, job dispatches, completions, and cancellations.
  - Worker WebSocket (`/ws/worker`): bidirectional authenticated WebSocket channel for immediate job dispatch, start confirmation, heartbeat, and result delivery.
- **Persistence & Database:**
  - SQLAlchemy 2.0 async engine supporting both SQLite (local development) and PostgreSQL (production).
  - Alembic migrations: `001_initial_schema`, `002_phase4_scheduler_schema`, `003_add_supported_models`.

### B. Python Worker Agent
- **Telemetry & Hardware Detection:**
  - Non-blocking CPU measurement and RAM inspection using `psutil`.
  - GPU hardware detection via `NvidiaGPUProvider` (pynvml) and `AppleSiliconGPUProvider`.
  - Dynamic local AI inference detection via Ollama (`GET http://localhost:11434/api/tags`), advertising model tags.
- **Execution Engine:**
  - `ModularJobExecutor` running pure safe handlers: `matrix_multiply`, `data_processing`, `image_processing`, and `llm_prompt`.
  - Host threshold protection: Pauses job acceptance if host CPU exceeds configured maximum (default 90%) or RAM drops below 512MB.
  - Strict payload size limits (2MB input, 100KB output) and configurable timeouts.
- **Networking & Resilience:**
  - Dual-transport: Real-time WebSocket connection with automatic exponential backoff reconnection (1s to 30s jittered) and HTTP fallback polling.

### C. Web Dashboard (Next.js)
- Responsive dark-mode dashboard built with React 19, Next.js 15 App Router, Tailwind CSS, and Lucide icons.
- 6 comprehensive views:
  1. **Overview (`/`)**: Pool compute status, node count, active workloads gauge, pooled RAM, CPU load.
  2. **Workers (`/workers`)**: Real-time worker cards, hardware specs, live CPU/RAM gauges, installed AI models, search and status filter.
  3. **Jobs (`/jobs`)**: Workload table, status badges, submit workload modal, result inspector modal.
  4. **Resource Monitor (`/monitor`)**: CPU trend chart, pooled memory gauge, GPU inventory, heartbeat freshness table.
  5. **Activity Logs (`/logs`)**: Chronological audit trail stream with filtering by event type.
  6. **Settings (`/settings`)**: Coordinator endpoint configurator with ping test, system info, worker start commands.
- Interactive Modals:
  - `SubmitJobModal`: Supports `matrix_multiply`, `data_processing`, `image_processing`, and `llm_prompt` with dynamic worker and model dropdowns.
  - `JobResultModal`: Dedicated AI inference card showing prompt, model tag, token count, execution latency, formatted response text, and copy-to-clipboard button.

---

## 2. Partially Implemented Features

1. **Continuous Watchdog for Stale Workers & Job Deadlines:**
   - `WorkerService.check_and_mark_stale_workers(db)` exists but is currently invoked only on demand when an operator queries `GET /api/v1/workers`.
   - If the dashboard is inactive, offline workers and expired jobs remain in `RUNNING` or `SCHEDULED` state until a query is executed. A continuous background task running in coordinator lifespan is needed.
2. **Result Ownership & Result Verification:**
   - In `DispatcherService.process_job_result`, the coordinator currently accepts a job result without explicitly verifying that the submitting `worker_id` matches `job.assigned_worker_id`. A rogue or misconfigured worker could submit a result for another worker's job.
3. **Safe Bounded Retries for Non-AI Workloads:**
   - When a worker disconnects before execution, `SCHEDULED` jobs are re-queued. However, if a job fails due to an unhandled worker crash, there is no automatic retry with exponential backoff for deterministic batch workloads (e.g., `matrix_multiply`). For AI prompt jobs, retries must remain opt-in and bound to an attempt ID to prevent duplicate token costs.

---

## 3. Missing Features

1. **Autonomous Coordinator Background Watchdog Loop:**
   - Continuous background task running inside FastAPI's lifespan to sweep deadlined jobs and stale workers every 5–10 seconds.
2. **Modular RAG Interface:**
   - An interface allowing optional context retrieval from trusted, authorized local documents or text stores, formatting retrieved snippets securely into prompt context without mixing with untrusted instructions.
3. **Task Decomposition & Subtask Planning:**
   - Modular workflow planner allowing complex composite workloads to be split into independent subtasks with dependency tracking and partial result aggregation.
4. **End-to-End Two-PC Networking Documentation:**
   - A dedicated guide (`TWO_PC_CONNECTION_GUIDE.md`) explaining cross-network topology, worker outbound NAT traversal, Railway deployment, and Ollama configuration.

---

## 4. Features That Exist But Require Hardening

1. **Coordinator Heartbeat Sweep:**
   - Verified in unit tests via explicit invocation, but requires continuous background execution in production.
2. **Long-Running Ollama Generation Timeouts:**
   - The worker agent has a 300s timeout on Ollama calls, but coordinator deadline monitoring must independently fail jobs if a worker PC goes to sleep mid-generation.
3. **PostgreSQL Production Constraints:**
   - Verified with SQLite locally; production requires explicit verification of PostgreSQL connection pooling and JSON column compatibility.

---

## 5. Current Architectural Assessment

- **Transport Architecture:** The existing outbound-only WebSocket architecture from worker nodes to the coordinator is sound and eliminates the need for inbound port forwarding on home or corporate routers.
- **Authoritative Coordinator:** The coordinator is the single source of truth for job states, scheduling, and database persistence. No secondary message broker (like Redis or Kafka) is needed at the current scale.
- **Tauri Desktop Shell:** The desktop app is a lightweight client container. It should not be deployed as a server container on Railway.

---

## 6. Security and Reliability Risks

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Worker spoofing result submission** | High | Enforce `job.assigned_worker_id == worker_id` in `process_job_result`. |
| **Silent job stall if worker crashes** | High | Implement continuous coordinator deadline watchdog loop. |
| **Duplicate LLM execution on network retry** | Medium | Disallow blind retries on `llm_prompt` jobs; require explicit attempt IDs. |
| **Ollama API exposure** | Critical | Worker connects strictly to `http://localhost:11434`; never bind Ollama to `0.0.0.0`. |
| **Prompt injection into system prompt** | Medium | Separate user prompt and system prompt in distinct API fields and Ollama request keys. |

---

## 7. Railway Deployment Blockers

1. **Nixpacks `pnpm` Executable Resolution:**
   - The previous deployment failed with `The executable 'pnpm' could not be found`.
   - Root cause: In `nixpacks.toml`, specifying `nixPkgs = ["nodejs_22", "pnpm"]` failed to make `pnpm` available in the container runtime path.
   - Solution: Explicitly run `npm install -g pnpm@9.15.4` in `[phases.setup]`, or use Corepack, and pin `pnpm` globally.
2. **Multi-Service Architecture Configuration:**
   - Railway users often confuse repository root `railway.json` (which points to `Dockerfile.coordinator`) with dashboard deployment.
   - Separate services must be defined: Service 1 for Dashboard (using `Dockerfile.dashboard` or updated `nixpacks.toml`), Service 2 for Coordinator (using `Dockerfile.coordinator`), and Service 3 for PostgreSQL.

---

## 8. Prioritized Implementation Plan

1. **Watchdog & Deadline Monitoring:** Add `check_and_fail_timed_out_jobs` to `JobService` and spawn a continuous background loop in coordinator `lifespan`.
2. **Result Ownership Verification:** Validate `job.assigned_worker_id == worker_id` in `DispatcherService.process_job_result`.
3. **Safe Bounded Retries & Idempotency:** Add retry counter and attempt IDs for safe workload re-queueing.
4. **Modular RAG & Task Decomposition Interface:** Add `coordinator/rag` and `coordinator/planner` modules.
5. **Railway Deployment Hardening:** Update `nixpacks.toml`, Dockerfiles, `.env.example`, and `RAILWAY_DEPLOYMENT.md`.
6. **Cross-PC Connection Guide:** Create `TWO_PC_CONNECTION_GUIDE.md` covering all 11 required sections.
7. **Testing & Verification:** Run full test suite, build dashboard, and document live verification status.

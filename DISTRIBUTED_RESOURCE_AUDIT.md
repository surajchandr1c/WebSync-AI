# WebSync AI — Distributed Resource Utilization & Architecture Audit

**Date:** October 12, 2026  
**Auditor:** Senior Distributed Systems Architect  
**Repository:** WebSync AI — Distributed AI Computing Platform  
**Scope:** Worker Agent, Coordinator API, Scheduler Engine, Workload Handlers, AI Inference Pipeline, Resource Telemetry, and Storage Isolation  

---

## 1. Executive Summary

This audit evaluates whether **WebSync AI** genuinely distributes computation across connected physical PCs or merely routes requests to a single machine.

### Key Audit Findings at a Glance

| Architectural Dimension | Current Status | Verification & Evidence |
| :--- | :--- | :--- |
| **Compute Execution Location** | **Genuine Remote Execution** | Workload computations (`matrix_multiply`, `data_processing`, `image_processing`, `llm_prompt`) execute inside the remote worker's Python process or local Ollama engine. The coordinator does **not** perform the calculation; it solely schedules, tracks state, and persists results. |
| **CPU & RAM Utilization** | **Target Worker Host** | The assigned worker's CPU performs the calculation; that worker's RAM holds the matrices, datasets, or in-memory buffers. |
| **Remote AI Prompt Inference** | **Single-Worker Local Model** | The AI prompt runs entirely on the single assigned worker via that worker's local Ollama instance (or Ollama Cloud API). Multiple workers enable **horizontal throughput scaling** (concurrent prompts across machines), but **do not split a single model's weights or inference graph across multiple PCs**. |
| **Resource-Aware Scheduling** | **Partially Enforced** | The scheduler filters candidates by `cpu_utilization`, `available_ram_bytes`, `gpu_available`, `supported_workloads`, and `supported_models`, and ranks them by load and available RAM. However, resource reservations were previously tracked solely as a coarse integer slot count (`active_job_count < max_concurrent_jobs`) without reserving requested RAM/CPU megabytes against an in-flight reservation ledger. |
| **Workload Decomposition & Aggregation** | **Previously Disconnected** | A theoretical `decomposer.py` existed in `coordinator/planner/`, but was completely disconnected from the coordinator execution pipeline. Jobs in `JobService` were handled solely as atomic single tasks with no database-level `parent_job_id` or automated child task distribution. |
| **Storage Architecture** | **Physically Isolated Disks** | Each worker possesses its own local filesystem and storage capacity. Disk capacity is **not** shared automatically across workers. |

---

## 2. In-Depth Component Analysis with Source Code Evidence

### 2.1 Which PC Runs Each Job & Performs the Computation?

* **Coordinator Role:** The FastAPI coordinator receives job submissions via `POST /api/v1/jobs` ([`services/coordinator/src/coordinator/api/routes/jobs.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/api/routes/jobs.py)), writes the record to SQLite/PostgreSQL, and invokes `DispatcherService.try_dispatch_job(db, job)`.
* **Worker Role:** When a job is scheduled to worker node $W$, the coordinator transmits a `job.dispatch` message over the persistent WebSocket connection ([`services/coordinator/src/coordinator/ws/manager.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/ws/manager.py)).
* **Execution Engine:** Inside [`worker/agent/executor.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/worker/agent/executor.py), the worker's `ModularJobExecutor` receives the payload and executes the designated handler:
  * `_run_matrix_multiply(payload)`: Multiplies $N \times M$ matrices in pure Python on the worker machine's CPU cores, computing arithmetic products and trace checksums.
  * `_run_data_processing(payload)`: Iterates over array records, computing aggregate sum, mean, min, and max using the worker's CPU and memory.
  * `_run_image_processing(payload)`: Allocates image pixel buffers using Pillow (`PIL.Image`) on the worker machine.
  * `_run_llm_prompt(payload)`: Makes an HTTP request to the local Ollama daemon (`http://localhost:11434/api/generate`) running on that worker machine.

**Conclusion:** Remote workers perform genuine, non-trivial computation on their local CPU and RAM. The coordinator is strictly an orchestrator.

---

### 2.2 Which PC's RAM Holds the Workload and Model?

* For numerical and data workloads (`matrix_multiply`, `data_processing`), matrix data structures and record lists are deserialized from JSON directly into Python heap memory on the **assigned worker PC**.
* For `llm_prompt`, the weights of the requested model (e.g. `gemma4:31b` or `llama3.2`) are loaded from that worker's local storage (`~/.ollama/models`) into that **worker machine's system RAM or GPU VRAM**. The coordinator's memory footprint is negligible (just the database row and JSON metadata).

---

### 2.3 Does AI Inference Run Locally on One Worker or Support Distributed Inference?

* **Verified Behavior:** AI inference executes on **a single worker node**. The worker makes a local loopback request to its local Ollama daemon:
  ```python
  # worker/agent/executor.py lines 324-325
  async with httpx.AsyncClient(timeout=timeout_seconds) as client:
      response = await client.post(gen_url, json=req_body)
  ```
* **No Tensor/Pipeline Parallelism:** WebSync AI does **not** partition model layers across multiple physical PCs (such as via DeepSpeed pipeline parallelism or Petals peer-to-peer sharding). If Machine 1 has 8 GB RAM and Machine 2 has 8 GB RAM, WebSync AI cannot combine them into 16 GB to run a 14B model that requires 12 GB.
* **Horizontal Throughput:** Multiple workers allow *independent prompts to execute concurrently on different machines*, increasing cluster throughput, but each individual prompt is atomic to one machine.

---

### 2.4 Does the Scheduler Use Real Resource Telemetry or Merely Display It?

* **Evaluation Loop:** In [`services/coordinator/src/coordinator/scheduler/evaluator.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/scheduler/evaluator.py), candidate workers are filtered against:
  1. `worker.connection_status in ("online", "busy")`
  2. `worker.last_heartbeat` freshness ($< 30\text{s}$)
  3. `worker.cpu_utilization` validity ($0\% \le \text{cpu} \le 100\%$)
  4. `worker.available_ram_bytes >= required_ram`
  5. `job.job_type in worker.supported_workloads`
  6. `worker.active_job_count < worker.max_concurrent_jobs`
* **Scoring:** In [`services/coordinator/src/coordinator/scheduler/scoring.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/scheduler/scoring.py), eligible workers are ranked with weighted scores combining CPU utilization, memory pressure, active load, and network latency.
* **Identified Gap / Limitation:**
  * While `available_ram_bytes` was checked, the scheduler previously lacked a **dynamic reservation ledger**. If a job required 2 GB RAM and was scheduled on Worker 1, `worker.active_job_count` incremented by 1, but `worker.available_ram_bytes` in the database remained unchanged until the next heartbeat (up to 10s later). If a second job arrived 1 second later, it would see the old `available_ram_bytes` and could be double-booked, exceeding physical memory limits.

---

### 2.5 Do Distributed Job Decomposition and Result Aggregation Exist?

* **Codebase Gap:**
  * [`services/coordinator/src/coordinator/planner/decomposer.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/planner/decomposer.py) defined Pydantic models `SubTask` and `TaskPlan` with sample splitting functions for prompts and record chunks.
  * **However**, it was never wired into [`services/coordinator/src/coordinator/services/job_service.py`](file:///c:/Users/Suraj/Desktop/Practice/Hackathone/WebSync_AI/services/coordinator/src/coordinator/services/job_service.py).
  * The `Job` model lacked `parent_job_id` and relationship attributes.
  * When a user submitted a job, it was always handled as a single monolithic unit. There was no capability to divide a large dataset into 4 chunks, send 2 chunks to PC 1 and 2 chunks to PC 2, collect the chunk results, and merge them into a single coherent parent job.

---

### 2.6 Storage Isolation and Behavior

* **Physical Isolation:** Each connected PC has its own physical drive. A file on PC 1's `C:\` drive cannot be directly accessed by PC 2.
* **Transmission Mechanism:** All job inputs and outputs are transmitted as JSON payloads through the authenticated coordinator WebSocket/REST channel.
* **Limitation:** There is no shared Network File System (NFS/SMB) or distributed object store (S3/MinIO). Large binary files cannot be assumed to exist on remote workers without explicit chunking or signed transfer manifests.

---

## 3. Summary of Gaps to be Implemented

1. **Hardware Telemetry Enhancement:**
   * Extend `worker/agent/metrics.py` to capture:
     * Logical and physical CPU core counts.
     * Host total, used, and available RAM.
     * Distinct WebSync AI available RAM (deducting the node's configured minimum safety buffer `WORKER_MIN_AVAILABLE_RAM_MB`).
     * Real root disk capacity (`disk_total_bytes`, `disk_used_bytes`, `disk_free_bytes`).
     * Configured worker concurrency and CPU thresholds.
2. **Scheduler Resource Reservation Ledger:**
   * Implement explicit logical resource reservations (`reserved_ram_bytes`, `reserved_cpu_cores`) in `SchedulerEngine`.
   * Deduct in-flight reservations from candidate worker RAM during scheduling.
   * Atomically release reservations upon job completion, failure, cancellation, or worker disconnection.
3. **True Distributed Decomposition & Parallel Aggregation Pipeline:**
   * Add `parent_job_id` to the `Job` database model and schemas.
   * Implement automated workload decomposition for partitionable jobs (e.g. `parallel_compute` / chunked `data_processing`).
   * Dispatch child tasks to distinct connected workers simultaneously.
   * Collect child task completions, compute deterministic aggregations (global sum, weighted mean, min, max, checksum), and mark parent job completed.
   * Provide complete execution traceability: record the exact worker node ID that computed each child partition.
4. **Dashboard Resource & Subtask Visibility:**
   * Update the UI to surface logical core counts, disk storage, memory headroom, child task progress, per-worker execution times, and aggregated results.

# WebSync AI — Distributed Resource Utilization & Multi-PC Guide

This document describes how WebSync AI genuinely utilizes and distributes computational resources across connected worker PCs, how workloads are decomposed and aggregated, how safety reserves and in-flight reservations prevent overcommit, and the physical reality of local storage and AI inference.

---

## 1. Architecture Overview

WebSync AI is a distributed computing platform designed to coordinate heterogenous hardware across private networks. Rather than pretending multiple machines share a single physical CPU, RAM pool, or disk drive, WebSync AI operates with **hardware truth**:

```
                                  +------------------------------------+
                                  |      WebSync AI Coordinator        |
                                  |   - REST API & WebSocket Server    |
                                  |   - In-Flight Reservation Ledger   |
                                  |   - Decomposition & Aggregator     |
                                  +-----------------+------------------+
                                                    |
                         +--------------------------+--------------------------+
                         | (HTTP / WebSocket)                                  | (HTTP / WebSocket)
                         v                                                     v
          +-----------------------------+                       +-----------------------------+
          |   Worker Node 1 (PC 1)      |                       |   Worker Node 2 (PC 2)      |
          | - CPU: Cores & Utilization  |                       | - CPU: Cores & Utilization  |
          | - RAM: Host vs WebSync Free |                       | - RAM: Host vs WebSync Free |
          | - Disk: Isolated Local C:\  |                       | - Disk: Isolated Local C:\  |
          | - Ollama: Local Model/Cloud |                       | - Ollama: Local Model/Cloud |
          +-----------------------------+                       +-----------------------------+
```

---

## 2. Resource Telemetry: Host vs. WebSync Allocatable Resources

Each worker agent periodically monitors its physical system state using `psutil` and sends authentic telemetry during enrollment and heartbeats (every 10 seconds).

### 2.1 CPU Metrics
- **Logical CPU Cores (`cpu_count_logical`)**: Total hyperthreaded/logical cores available on the worker CPU.
- **Physical CPU Cores (`cpu_count_physical`)**: Total distinct silicon cores.
- **CPU Utilization (`cpu_utilization`)**: Non-blocking sampled processor utilization.
- **CPU Safety Threshold (`configured_max_cpu_percent`)**: Configurable threshold (default `90.0%`). If host CPU exceeds this limit, the worker will refuse new workloads to protect host stability.

### 2.2 Memory Metrics
- **Host Total RAM (`total_ram_bytes`)**: Total installed physical memory.
- **Host Available RAM (`available_ram_bytes`)**: Unused or reclaimable memory reported by OS.
- **Host Used RAM (`used_ram_bytes`)**: Active RAM held by host operating system and background software.
- **Host Safety Reserve (`configured_min_available_ram_mb`)**: Configurable buffer (default `512 MB`) reserved exclusively for the host operating system.
- **WebSync Allocatable RAM (`websync_available_ram_bytes`)**: Actual memory available for WebSync workloads:
  $$\text{WebSync Allocatable RAM} = \max(0, \text{Host Available RAM} - \text{Host Safety Reserve})$$

### 2.3 Storage Metrics (Physical Isolation)
- **Disk Total (`disk_total_bytes`)**: Physical capacity of the worker's primary partition (`C:\` on Windows, `/` on Linux).
- **Disk Free (`disk_free_bytes`)**: Unallocated free storage on the worker's physical disk.
- **Disk Percent (`disk_percent`)**: Utilization percentage of the local storage drive.
- **Physical Boundary**: **Each PC has its own physical drive.** WebSync AI does not fabricate a shared cluster network volume. Workloads that read or write files operate on the isolated disk of the executing worker.

---

## 3. Resource-Aware Scheduling & In-Flight Reservation Ledger

Worker heartbeats arrive periodically (every 10 seconds). In a distributed system, relying solely on cached heartbeats creates a **race condition** where multiple workloads dispatched in the same 10-second window could overcommit a worker's CPU cores or RAM.

### 3.1 The In-Flight Reservation Ledger
The WebSync AI scheduler maintains an in-memory transactional reservation ledger:

```python
class ResourceReservation:
    job_id: str
    worker_id: str
    reserved_ram_bytes: int
    reserved_cpu_cores: int
```

When evaluating candidate workers for a queued job:
1. **Effective Available RAM** is calculated by subtracting existing in-flight reservations:
   $$\text{Effective RAM} = \text{Worker Available RAM} - \text{Safety Buffer} - \sum \text{In-Flight Reserved RAM}$$
2. **Effective Available Cores** is calculated by deducting in-flight core allocations:
   $$\text{Effective Cores} = \text{Worker Logical Cores} - \sum \text{In-Flight Reserved Cores}$$
3. If $\text{Effective RAM} < \text{Job Required RAM}$ or $\text{Effective Cores} < \text{Job Required Cores}$, the candidate is rejected.
4. If candidate host CPU is above `configured_max_cpu_percent`, the candidate is rejected.
5. If the candidate does not have the requested workload or model installed, the candidate is rejected.

### 3.2 Atomicity & Release Guarantee
When a worker is selected:
- `worker.active_job_count` is incremented.
- The job's RAM and CPU core requirements are recorded in the reservation ledger.
- If `active_job_count >= max_concurrent_jobs`, the worker status transitions to `busy`.

When the job reaches a terminal state (`COMPLETED`, `FAILED`, `CANCELLED`) or if the worker disconnects:
- `scheduler_engine.release_capacity(db, worker_id, job_id)` is called.
- The reservation ledger entry is cleared.
- `worker.active_job_count` is decremented.
- If slots are now open, connection status reverts to `online`.

---

## 4. Distributed Job Decomposition & Result Aggregation

WebSync AI supports genuine distributed map-reduce computation via the `distributed_data_processing` workload.

### 4.1 Job Submission & Slicing
When a client submits a `distributed_data_processing` job:
1. The coordinator creates the **Parent Job** (`status: RUNNING`, `started_at: now`).
2. The coordinator slices the dataset of $N$ records into $K$ chunks (partitions, default: 2).
3. The coordinator instantiates $K$ **Child Jobs** (`job_type: data_processing`, `parent_job_id: parent.job_id`).
4. The coordinator dispatches each child job independently through the scheduler engine.

### 4.2 Multi-Worker Parallel Execution
- If 2 or more worker machines are connected, the scheduler dispatches Chunk 1 to Worker 1 and Chunk 2 to Worker 2.
- Each worker executes its assigned chunk concurrently inside its local process.
- Each worker posts its execution output containing:
  ```json
  {
    "status": "success",
    "partition_index": 0,
    "total_partitions": 2,
    "record_count": 4000,
    "sum": 1040086.2,
    "mean": 260.02,
    "min": 0.0,
    "max": 522.7
  }
  ```

### 4.3 Automated Aggregation
When any subtask finishes, the coordinator checks if all sibling tasks have finished:
- **Failure Handling**: If any subtask fails, the parent job transitions to `FAILED` with details identifying the failing subtask and worker node.
- **Success Aggregation**: When all $K$ child tasks are `COMPLETED`, the coordinator aggregates:
  - Total records processed: $\sum \text{record\_count}$
  - Global sum: $\sum \text{chunk\_sum}$
  - Global mean: $\frac{\text{Global Sum}}{\text{Total Records}}$
  - Global minimum and maximum bounds
  - List of contributing worker hardware IDs
  - Wall-clock parallel execution duration
- The parent job transitions to `COMPLETED`, persists the aggregated JSON report, and broadcasts `job.completed` over WebSocket.

---

## 5. Remote AI Prompt Execution: The Single-Worker Reality

WebSync AI supports remote AI prompt execution (`llm_prompt`) via local Ollama instances or Ollama Cloud API.

### 5.1 No Fake Model Sharding
> [!IMPORTANT]
> **AI prompts run on a single worker node.** WebSync AI does **not** claim to split a single 70-billion-parameter neural network across consumer PCs over private Wi-Fi (which would require gigabit-per-second tensor-parallel interconnects like NVLink). 
> 
> Instead, the scheduler routes the entire prompt to a specific worker that has the requested model weights installed in its local Ollama instance (or valid Cloud credentials).

### 5.2 Capability Matching
When an AI prompt request arrives:
- The scheduler checks the `supported_models` list transmitted by each worker.
- If a worker does not have the requested model installed, the scheduler rejects that worker with:
  `Requested model '<model>' not available on worker (available: [...])`
- The workload is placed strictly on an eligible machine with the required weights.

---

## 6. How to Run Multi-Worker Distributed Benchmark

### Step 1: Start the Coordinator
In your workspace:
```powershell
$env:PYTHONPATH = "services/coordinator/src"
.venv\Scripts\python.exe -m uvicorn coordinator.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Start Worker 1 (Main Rig)
In a separate terminal:
```powershell
.venv\Scripts\python.exe -m worker.agent.main --coordinator-url http://localhost:8000 --worker-id node-primary-pc1 --worker-name "PC1-Compute-Rig" --token dev-worker-secret-token
```

### Step 3: Start Worker 2 (Secondary Worker or Second PC)
On a second PC on the LAN (or a second terminal on the same machine):
```powershell
.venv\Scripts\python.exe -m worker.agent.main --coordinator-url http://<PC1_LAN_IP>:8000 --worker-id node-secondary-pc2 --worker-name "PC2-Secondary-Worker" --token dev-worker-secret-token
```

### Step 4: Run Verification Benchmark
Execute the automated test script:
```powershell
.venv\Scripts\python.exe scripts\verify_distributed_cluster.py
```

The script will:
1. Verify both workers are online with authentic CPU cores, allocatable RAM, and disk storage metrics.
2. Run a single-worker baseline job and record duration.
3. Submit a distributed pipeline (`distributed_data_processing`, 8,000 records, 2 chunks).
4. Verify Chunk 1 is executed on `node-primary-pc1` and Chunk 2 on `node-secondary-pc2`.
5. Verify parent job aggregates both results into a unified global dataset summary.
6. Verify AI prompt execution against Ollama inference.

---

## 7. Viewing Distributed Operations in the WebSync Dashboard

1. Open `http://localhost:3000` (or `http://<PC1_LAN_IP>:3000` from PC 2).
2. Navigate to **Workers**:
   - Inspect individual worker cards showing physical and logical core counts, host physical RAM vs. WebSync allocatable RAM, and local isolated disk storage.
   - Click any worker to view live CPU utilization, safety reserve buffer, and threshold rejection limits.
3. Navigate to **Jobs**:
   - Filter by `distributed_data_processing`.
   - Click the parent job to inspect the **Distributed Parallel Execution & Decomposition** panel.
   - Observe the **Contributing Worker Hardware** pills showing all worker nodes engaged.
   - Inspect the **Decomposed Parallel Tasks** table displaying chunk IDs, assigned worker node IDs, execution statuses, and per-chunk durations.

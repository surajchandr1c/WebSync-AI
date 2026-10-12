# WebSync AI — Production Deployment Guide for Railway

This guide walks you through deploying **WebSync AI** to [Railway](https://railway.com) in high-availability production mode.

---

## Architecture on Railway

```mermaid
flowchart TD
    subgraph Workstations["Distributed User Computers (Outside Cloud)"]
        Worker1["Node Alpha (Windows 11 + NVIDIA RTX)"]
        Worker2["Node Beta (Linux / macOS)"]
    end

    subgraph BrowserClient["End Users"]
        Browser["Next.js Web Dashboard\n(Browser / Phone / Desktop)"]
    end

    subgraph RailwayCloud["Railway Project"]
        subgraph FrontService["Service 1: Frontend"]
            NextJS["Next.js 15 SSR/Static\nDomain: websync-dashboard.up.railway.app"]
        end

        subgraph CoordService["Service 2: Coordinator"]
            FastAPI["FastAPI + Uvicorn (0.0.0.0:$PORT)\nDomain: websync-coordinator.up.railway.app\nEndpoints: /api/v1/*, /ws/dashboard, /ws/worker"]
            Scheduler["Adaptive Resource-Aware Scheduler"]
            FastAPI --> Scheduler
        end

        subgraph DBService["Service 3: PostgreSQL"]
            PG[(PostgreSQL 16 Database\nInternal TCP: postgres.railway.internal:5432)]
        end

        NextJS -.->|REST / WebSocket| FastAPI
        FastAPI -->|Connection Pool (asyncpg)| PG
    end

    Browser -->|HTTPS| NextJS
    Worker1 -->|WSS & HTTPS Outbound| FastAPI
    Worker2 -->|WSS & HTTPS Outbound| FastAPI
```

> [!IMPORTANT]
> **Understanding the Architecture:**
> - **Railway Cloud Hosts:** The Next.js dashboard, the FastAPI coordinator, and the PostgreSQL database.
> - **Worker Agents Run On Physical Computers:** Workers execute on users' actual hardware (Windows, Linux, macOS) across the internet and connect outbound to Railway's public coordinator domain over secure TLS (`https://` and `wss://`). Workers are **never** deployed as serverless functions.

---

## Service Overview & Resource Sizing

| Service Name | Source / Type | Port / Target | Recommended Plan |
| :--- | :--- | :--- | :--- |
| **`websync-postgres`** | Railway Plugin | Internal 5432 | Default Starter / Developer |
| **`websync-coordinator`** | Dockerfile (`infra/docker/Dockerfile.coordinator`) | Injected `$PORT` | 512 MB – 1 GB RAM, 1 vCPU |
| **`websync-dashboard`** | Dockerfile (`infra/docker/Dockerfile.dashboard`) | Injected `$PORT` | 512 MB RAM, 1 vCPU |

---

## Step-by-Step Deployment Instructions

### Step 1: Push Code to GitHub
Ensure your repository is up to date:
```bash
git add .
git commit -m "chore: prepare WebSync AI for Railway production deployment"
git push origin main
```

---

### Step 2: Create a New Project on Railway
1. Log in to [Railway](https://railway.com).
2. Click **"+ New Project"**.
3. Select **"Deploy from GitHub repo"** and choose your `WebSync-AI` repository.
4. When prompted, select **"Empty Project"** or add services incrementally as outlined below.

---

### Step 3: Add PostgreSQL Database Service
1. In your Railway project canvas, click **"+ Create"** $\to$ **"Database"** $\to$ **"Add PostgreSQL"**.
2. Railway creates a managed PostgreSQL 16 container and automatically generates the internal `DATABASE_URL`.
3. Click on the PostgreSQL service card, navigate to **Variables**, and note the variable name: `DATABASE_URL`.

---

### Step 4: Configure & Deploy the Coordinator Service (`websync-coordinator`)
1. In the Railway canvas, click **"+ Create"** $\to$ **"GitHub Repo"** $\to$ select your `WebSync-AI` repository.
2. Click the newly created service card and rename it to **`websync-coordinator`**.
3. Go to **Settings**:
   - **Build:**
     - **Builder:** `Dockerfile`
     - **Dockerfile Path:** `infra/docker/Dockerfile.coordinator`
   - **Networking:**
     - Click **"Generate Domain"** under Public Networking (e.g. `websync-coordinator-production.up.railway.app`).
   - **Deploy:**
     - **Custom Start Command:** Leave empty (automatically handled by `railway.json` as `uvicorn coordinator.main:app --host 0.0.0.0 --port ${PORT:-8000}`).
     - **Healthcheck Path:** `/health`
     - **Healthcheck Timeout:** `100` seconds
     - **Restart Policy:** `On Failure` (5 retries)
4. Go to **Variables** and configure:

| Environment Variable | Recommended Production Value | Notes |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enforces production security checks. |
| `LOG_LEVEL` | `INFO` | Structured logging with sensitive token redaction. |
| `COORDINATOR_HOST` | `0.0.0.0` | Binds to all network interfaces. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Select Railway reference variable from your PostgreSQL service. |
| `COORDINATOR_SECRET_KEY` | *(Generate 32+ random characters)* | Cryptographic JWT signing key. |
| `WORKER_DEV_AUTH_TOKEN` | *(Generate 24+ random characters)* | Unique worker token for authenticated sessions. |
| `WORKER_ENROLLMENT_SECRET` | *(Generate 24+ random characters)* | Pre-shared secret required for physical node enrollment. |
| `CORS_ORIGINS` | `https://<YOUR-FRONTEND-DOMAIN>,tauri://localhost` | Comma-separated allowlist. |
| `FRONTEND_URL` | `https://<YOUR-FRONTEND-DOMAIN>` | Domain of the dashboard (Step 5). |

> [!TIP]
> **Generate Secure Secrets Locally:**
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

---

### Step 5: Configure & Deploy the Frontend Service (`websync-dashboard`)
1. In the Railway canvas, click **"+ Create"** $\to$ **"GitHub Repo"** $\to$ select your `WebSync-AI` repository again.
2. Rename this service to **`websync-dashboard`**.
3. Go to **Settings**:
   - **Build:**
     - **Builder:** `Dockerfile`
     - **Dockerfile Path:** `infra/docker/Dockerfile.dashboard`
   - **Networking:**
     - Click **"Generate Domain"** (e.g. `websync-dashboard-production.up.railway.app`).
   - **Deploy:**
     - **Custom Start Command:** Leave empty (automatically handled by `apps/dashboard/railway.json` and `Dockerfile.dashboard`).
     - **Healthcheck Path:** `/`
     - **Healthcheck Timeout:** `100` seconds
4. Go to **Variables** and configure:

| Environment Variable | Recommended Production Value | Notes |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://<YOUR-COORDINATOR-DOMAIN>` | E.g. `https://websync-coordinator-production.up.railway.app` |
| `NEXT_PUBLIC_WS_URL` | `wss://<YOUR-COORDINATOR-DOMAIN>/ws/dashboard` | Public WebSocket endpoint for real-time live events. |
| `PORT` | `3000` | Railway automatically maps container port. |

> [!NOTE]
> Once your frontend domain is generated, ensure you add it to the `CORS_ORIGINS` variable in the `websync-coordinator` service!

---

### Step 6: Run Database Migrations
WebSync AI automatically initializes tables on startup via SQLAlchemy. To apply Alembic migrations against Railway PostgreSQL:

#### Option A: One-Off Railway CLI Command
Install the [Railway CLI](https://docs.railway.com/guides/cli):
```bash
railway login
railway link
railway run --service websync-coordinator alembic -c services/coordinator/alembic.ini upgrade head
```

#### Option B: Automatic Startup Initialization
The coordinator's lifespan handler calls `init_db()` at container startup, creating all tables (`users`, `workers`, `jobs`, `job_events`) safely and idempotently without downtime or data loss.

---

### Step 7: Connecting Real Worker Workstations Over the Internet

On any physical computer (e.g., your Windows laptop with NVIDIA RTX GPU, or a Linux workstation):

#### On Windows (PowerShell):
```powershell
.\.venv\Scripts\python -m worker.agent.main `
  --coordinator-url https://websync-coordinator-production.up.railway.app `
  --worker-id node-laptop-windows `
  --worker-name "Laptop-RTX-Node"
```

#### On Linux / macOS (Bash):
```bash
python3 -m worker.agent.main \
  --coordinator-url https://websync-coordinator-production.up.railway.app \
  --worker-id node-compute-linux \
  --worker-name "Linux-Node-01"
```

The worker agent will:
1. Connect via outbound HTTPS to `/api/v1/workers/register`.
2. Inspect local hardware via non-blocking `psutil` and NVML (`nvidia-ml-py`).
3. Establish a persistent bidirectional WebSocket connection over `wss://`.
4. Transmit periodic heartbeats every 10 seconds.
5. Await dispatched workloads from the coordinator's adaptive scheduler.

---

### Step 8: Verifying End-to-End Execution in Production

1. Open your Railway dashboard URL: `https://websync-dashboard-production.up.railway.app`.
2. Navigate to **Connected Nodes (`/workers`)** — verify your physical computer appears with genuine CPU, RAM, and GPU accelerator tags.
3. Click **"Submit Job"**:
   - Workload: `matrix_multiply`
   - Matrix Dimension: `100`
   - Requirements: `Min CPU: 1`, `Min RAM: 512 MB`
4. Watch the job lifecycle in real-time:
   `QUEUED` $\to$ `SCHEDULED` $\to$ `RUNNING` (dispatched over WSS) $\to$ `COMPLETED`.
5. Click **"Inspect"** to verify stdout, execution duration (typically $<50$ ms), and the trace checksum.

---

## Troubleshooting & FAQ

### 1. Coordinator Logs: "Production environment error: SQLite is not permitted..."
- **Cause:** `ENVIRONMENT=production` was set, but `DATABASE_URL` is pointing to local SQLite or missing.
- **Remediation:** Link the Railway PostgreSQL database variable: `DATABASE_URL=${{Postgres.DATABASE_URL}}`.

### 2. Frontend shows "Coordinator unreachable"
- **Cause:** `NEXT_PUBLIC_API_URL` is pointing to localhost or has trailing slashes.
- **Remediation:** In the `websync-dashboard` service settings, set `NEXT_PUBLIC_API_URL` to `https://<YOUR-COORDINATOR-DOMAIN>` without trailing slashes. You can also configure the endpoint live in the dashboard at `/settings`.

### 3. Worker fails with 401 Unauthorized during enrollment
- **Cause:** The worker's `--token` does not match the coordinator's `WORKER_ENROLLMENT_SECRET`.
- **Remediation:** Set `WEB_SYNC_WORKER_TOKEN=<YOUR_SECRET>` matching the coordinator's `WORKER_ENROLLMENT_SECRET`.

### 4. Healthcheck returns 503 Service Unavailable
- **Cause:** The coordinator container started, but cannot connect to the PostgreSQL database.
- **Remediation:** Check that the PostgreSQL service in Railway is healthy and accessible via the internal private network (`postgres.railway.internal`).

### 5. Build Error: `sh: 1: pnpm: not found (exit code: 127)` or `The executable 'pnpm' could not be found`
- **Cause 1 (Dockerfile Builder):** A custom **Build Command** (such as `pnpm --filter @websync/dashboard build`) or **Start Command** was entered into Railway's service settings on a service building with `infra/docker/Dockerfile.coordinator` (Python), where Node/pnpm is not installed.
  - **Remediation:** Leave the **Build Command** field **EMPTY / BLANK** in Railway service settings because the Dockerfiles already encapsulate all dependency installation and compilation steps.
  - Ensure **Dockerfile Path** points to `infra/docker/Dockerfile.dashboard` for the dashboard service and `infra/docker/Dockerfile.coordinator` for the coordinator service.
- **Cause 2 (Nixpacks Builder):** If using Railway's default Nixpacks builder without Dockerfiles, Nixpacks uses `nixpacks.toml`. Previously, `nixPkgs = ["nodejs_22", "pnpm"]` failed because `pnpm` is not a standalone top-level nix package.
  - **Remediation:** In `nixpacks.toml`, `[phases.setup]` now executes `cmds = ["npm install -g pnpm@9.15.4"]` which globally installs and links the pinned pnpm executable into `/usr/local/bin` for both build and runtime stages.
- **Cause 3 (Accidental Desktop App Deployment):** Trying to deploy `apps/desktop` (Tauri desktop app) to Railway as a server. The desktop app is meant to be run natively on client workstations, not hosted on Railway.

---

## Railway Pricing & Resource Limits Notice
- Railway provides an included monthly usage tier and pay-as-you-go pricing for CPU/RAM utilization.
- Because physical compute worker agents execute on your own workstation hardware and not on Railway containers, coordinator and dashboard resource consumption remains minimal ($\approx 100$ MB RSS idle).

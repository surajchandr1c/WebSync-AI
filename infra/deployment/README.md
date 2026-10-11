# WebSync AI — Deployment Guide

This directory contains infrastructure specifications and deployment guides for running WebSync AI across private local networks or cloud environments.

## Local Docker Deployment

To spin up the PostgreSQL persistence database, Coordinator, and Dashboard with Docker Compose:

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
```

- Coordinator REST & WebSocket API: `http://localhost:8000`
- Coordinator Health Check: `http://localhost:8000/api/v1/health`
- Web Dashboard: `http://localhost:3000`

## Worker Node Deployment

On client machines contributing compute:

1. Clone or copy the `worker/` package.
2. Install Python 3.12+ and dependencies (`pip install -e worker/`).
3. Set the target coordinator URL in environment or CLI:
   ```bash
   WORKER_COORDINATOR_URL="http://<coordinator-ip>:8000" python worker/agent/main.py
   ```
4. Verify genuine telemetry reporting:
   ```bash
   python worker/agent/main.py --inspect
   ```

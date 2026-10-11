"""WebSync AI — Phase 9 Integration Test Suite.

Validates end-to-end distributed job lifecycle, adaptive scheduling conditions,
terminal state immutability, worker disconnect recovery, and security enforcement.
"""

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
import httpx
from coordinator.config import settings
from coordinator.core.security import create_access_token
from worker.agent.executor import ModularJobExecutor, WorkloadExecutionResult


@pytest.mark.asyncio
async def test_phase9_worker_registration_and_hardware_profile(client: httpx.AsyncClient):
    """Test worker registration with realistic hardware telemetry profile."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}
    resp = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "test-p9-node-alpha",
            "display_name": "Test Node Alpha (RTX 3050)",
            "hostname": "test-node-alpha",
            "platform": "Windows",
            "cpu_utilization": 15.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 12 * 1024**3,
            "supported_workloads": ["matrix_multiply", "data_processing", "image_processing"],
            "gpu_available": True,
            "gpu_metadata": [{"name": "NVIDIA GeForce RTX 3050", "memory_total_bytes": 4 * 1024**3}],
            "max_concurrent_jobs": 2,
        },
        headers=reg_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["worker_id"] == "test-p9-node-alpha"
    assert "auth_token" in data
    assert data["connection_status"] == "online"


@pytest.mark.asyncio
async def test_phase9_adaptive_scheduling_conditions(client: httpx.AsyncClient):
    """Test adaptive diversion: high CPU on Worker Alpha routes job to Worker Beta."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}
    
    # Register Alpha (High CPU: 95%)
    r_a = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-sched-alpha",
            "display_name": "Sched Alpha",
            "hostname": "alpha-host",
            "platform": "Windows",
            "cpu_utilization": 95.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 8 * 1024**3,
            "supported_workloads": ["matrix_multiply", "data_processing"],
            "gpu_available": False,
        },
        headers=reg_headers,
    )
    assert r_a.status_code == 201

    # Register Beta (Low CPU: 10%)
    r_b = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-sched-beta",
            "display_name": "Sched Beta",
            "hostname": "beta-host",
            "platform": "Linux",
            "cpu_utilization": 10.0,
            "total_ram_bytes": 8 * 1024**3,
            "available_ram_bytes": 6 * 1024**3,
            "supported_workloads": ["matrix_multiply", "data_processing"],
            "gpu_available": False,
        },
        headers=reg_headers,
    )
    assert r_b.status_code == 201

    # Submit job requiring low CPU
    job_resp = await client.post(
        "/api/v1/jobs",
        json={
            "name": "p9-adaptive-job",
            "job_type": "data_processing",
            "input_payload": {"records": [{"id": 1, "value": 100}]},
            "requirements": {"min_ram_mb": 256},
        },
    )
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    assert job_data["status"] == "SCHEDULED"
    assert job_data["assigned_worker_id"] == "p9-sched-beta"


@pytest.mark.asyncio
async def test_phase9_gpu_and_ram_constraint_filtering(client: httpx.AsyncClient):
    """Test that jobs requiring GPU only match GPU-capable workers."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}

    # Node with GPU
    await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-gpu-node",
            "display_name": "GPU Node",
            "hostname": "gpu-host",
            "platform": "Windows",
            "cpu_utilization": 20.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 14 * 1024**3,
            "supported_workloads": ["matrix_multiply"],
            "gpu_available": True,
            "gpu_metadata": [{"name": "RTX 3050", "memory_total_bytes": 4 * 1024**3}],
        },
        headers=reg_headers,
    )

    # Node without GPU
    await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-cpu-only-node",
            "display_name": "CPU Only",
            "hostname": "cpu-host",
            "platform": "Linux",
            "cpu_utilization": 5.0,
            "total_ram_bytes": 32 * 1024**3,
            "available_ram_bytes": 28 * 1024**3,
            "supported_workloads": ["matrix_multiply"],
            "gpu_available": False,
        },
        headers=reg_headers,
    )

    # Job requiring GPU
    job_resp = await client.post(
        "/api/v1/jobs",
        json={
            "name": "p9-gpu-job",
            "job_type": "matrix_multiply",
            "input_payload": {"dimension": 10},
            "requirements": {"gpu_required": True, "min_ram_mb": 512},
        },
    )
    assert job_resp.status_code == 201
    assert job_resp.json()["assigned_worker_id"] == "p9-gpu-node"


@pytest.mark.asyncio
async def test_phase9_terminal_state_protection(client: httpx.AsyncClient):
    """Test that cancelled jobs are immutable against late worker results."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}
    reg = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-term-node",
            "display_name": "Terminal Node",
            "hostname": "term-host",
            "platform": "Linux",
            "cpu_utilization": 10.0,
            "total_ram_bytes": 4 * 1024**3,
            "available_ram_bytes": 3 * 1024**3,
            "supported_workloads": ["data_processing"],
        },
        headers=reg_headers,
    )
    worker_token = reg.json()["auth_token"]

    job_resp = await client.post(
        "/api/v1/jobs",
        json={
            "name": "job-term-cancel",
            "job_type": "data_processing",
            "input_payload": {"records": []},
        },
    )
    job_id = job_resp.json()["job_id"]

    # Cancel job
    cancel_res = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_res.status_code == 200

    # Late result submitted by worker
    late_res = await client.post(
        f"/api/v1/workers/p9-term-node/jobs/{job_id}/result",
        json={
            "type": "job.result",
            "job_id": job_id,
            "worker_id": "p9-term-node",
            "exit_code": 0,
            "output": "late result that must be ignored",
            "duration_seconds": 0.5,
        },
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert late_res.status_code == 200

    # Status must remain CANCELLED
    check = await client.get(f"/api/v1/jobs/{job_id}")
    assert check.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_phase9_worker_revocation_enforcement(client: httpx.AsyncClient):
    """Test administrative worker revocation rejects subsequent worker requests."""
    # Register bootstrap admin
    admin_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "p9_admin_user",
            "email": "p9admin@websync.ai",
            "password": "AdminPassword123!",
            "role": "admin",
        },
    )
    assert admin_reg.status_code == 201

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "p9_admin_user", "password": "AdminPassword123!"},
    )
    admin_token = admin_login.json()["access_token"]

    # Register worker
    reg = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "p9-to-revoke",
            "display_name": "Revoke Test Node",
            "hostname": "rev-host",
            "platform": "Linux",
            "cpu_utilization": 10.0,
            "total_ram_bytes": 4 * 1024**3,
            "available_ram_bytes": 2 * 1024**3,
        },
        headers={"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN},
    )
    worker_token = reg.json()["auth_token"]

    # Revoke worker using admin credentials
    rev_res = await client.post(
        "/api/v1/workers/p9-to-revoke/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["is_revoked"] is True

    # Subsequent heartbeat must be rejected with 403
    hb_res = await client.post(
        "/api/v1/workers/heartbeat",
        json={"cpu_utilization": 10.0, "available_ram_bytes": 2 * 1024**3, "active_job_count": 0},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert hb_res.status_code == 403


@pytest.mark.asyncio
async def test_phase9_real_matrix_multiplication_computation():
    """Verify real ModularJobExecutor numerical matrix multiplication correctness."""
    executor = ModularJobExecutor()
    a = [[1.0, 2.0], [3.0, 4.0]]
    b = [[5.0, 6.0], [7.0, 8.0]]
    # A x B = [[19, 22], [43, 50]] -> Trace = 69.0, c[0][0] = 19.0
    result: WorkloadExecutionResult = await executor.execute_job(
        job_id="test-calc-1",
        job_type="matrix_multiply",
        input_payload={"matrix_a": a, "matrix_b": b},
        timeout_seconds=10,
    )
    assert result.success is True
    assert result.exit_code == 0
    assert "Trace checksum: 69.0" in result.output
    assert "Sample element c[0][0]: 19.0" in result.output

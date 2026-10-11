from datetime import datetime, timezone
import pytest
import httpx
from coordinator.config import settings


@pytest.mark.asyncio
async def test_end_to_end_job_dispatch_and_execution_lifecycle(client: httpx.AsyncClient):
    """Verify complete dispatch flow: submission -> scheduling -> ack -> start -> result -> capacity release."""
    worker_id = "node-dispatch-01"
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}

    # 1. Register worker
    reg_res = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": worker_id,
            "display_name": "Dispatcher Worker",
            "hostname": "host-1",
            "platform": "Linux",
            "cpu_utilization": 15.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 12 * 1024**3,
            "supported_workloads": ["matrix_multiply", "data_processing"],
            "max_concurrent_jobs": 2,
        },
        headers=reg_headers,
    )
    assert reg_res.status_code == 201
    worker_jwt = reg_res.json()["auth_token"]
    worker_headers = {"Authorization": f"Bearer {worker_jwt}"}

    # 2. Submit a matrix multiply job
    job_payload = {
        "name": "matrix-job-1",
        "job_type": "matrix_multiply",
        "input_payload": {"dimension": 20},
        "requirements": {"min_ram_mb": 512, "gpu_required": False},
    }
    job_res = await client.post("/api/v1/jobs", json=job_payload)
    assert job_res.status_code == 201
    job_data = job_res.json()
    job_id = job_data["job_id"]

    # Verify job was automatically scheduled and assigned to node-dispatch-01
    assert job_data["status"] == "SCHEDULED"
    assert job_data["assigned_worker_id"] == worker_id
    assert job_data["placement_reason"] is not None
    assert job_data["placement_reason"]["worker_id"] == worker_id

    # Verify worker active_job_count was reserved
    worker_check = await client.get(f"/api/v1/workers/{worker_id}")
    assert worker_check.json()["active_job_count"] == 1

    # 3. Worker polls for pending jobs
    poll_res = await client.get(f"/api/v1/workers/{worker_id}/jobs/pending", headers=worker_headers)
    assert poll_res.status_code == 200
    pending_items = poll_res.json()
    assert len(pending_items) == 1
    assert pending_items[0]["job_id"] == job_id

    # 4. Worker acknowledges job
    ack_res = await client.post(
        f"/api/v1/workers/{worker_id}/jobs/{job_id}/ack",
        json={"type": "job.ack", "job_id": job_id, "worker_id": worker_id, "accepted": True},
        headers=worker_headers,
    )
    assert ack_res.status_code == 200

    # 5. Worker signals execution start
    start_res = await client.post(
        f"/api/v1/workers/{worker_id}/jobs/{job_id}/start",
        headers=worker_headers,
    )
    assert start_res.status_code == 200
    job_running = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_running.json()["status"] == "RUNNING"
    assert job_running.json()["started_at"] is not None

    # 6. Worker submits completed result
    result_res = await client.post(
        f"/api/v1/workers/{worker_id}/jobs/{job_id}/result",
        json={
            "type": "job.result",
            "job_id": job_id,
            "worker_id": worker_id,
            "exit_code": 0,
            "output": "Multiplied 20x20 matrices. Trace checksum: 1250",
            "duration_seconds": 0.045,
            "error": None,
        },
        headers=worker_headers,
    )
    assert result_res.status_code == 200

    # 7. Verify job COMPLETED and capacity released
    job_completed = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_completed.json()["status"] == "COMPLETED"
    assert job_completed.json()["completed_at"] is not None

    result_check = await client.get(f"/api/v1/jobs/{job_id}/result")
    assert result_check.json()["result_exit_code"] == 0
    assert "checksum: 1250" in result_check.json()["result_output"]

    # Verify worker active_job_count was released
    worker_after = await client.get(f"/api/v1/workers/{worker_id}")
    assert worker_after.json()["active_job_count"] == 0


@pytest.mark.asyncio
async def test_scheduler_selects_second_worker_when_first_busy(client: httpx.AsyncClient):
    """Verify adaptive placement sends job to least busy node."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}

    # Register worker 1 (higher CPU, busy with 1 job)
    w1_res = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-busy-01",
            "display_name": "Busy Node",
            "hostname": "h1",
            "platform": "Linux",
            "cpu_utilization": 85.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 4 * 1024**3,
            "supported_workloads": ["matrix_multiply"],
            "max_concurrent_jobs": 2,
        },
        headers=reg_headers,
    )
    assert w1_res.status_code == 201

    # Register worker 2 (idle, low CPU, plenty of RAM)
    w2_res = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-idle-02",
            "display_name": "Idle Node",
            "hostname": "h2",
            "platform": "Linux",
            "cpu_utilization": 10.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 14 * 1024**3,
            "supported_workloads": ["matrix_multiply"],
            "max_concurrent_jobs": 2,
        },
        headers=reg_headers,
    )
    assert w2_res.status_code == 201

    # Submit job
    job_res = await client.post(
        "/api/v1/jobs",
        json={
            "name": "comparison-job",
            "job_type": "matrix_multiply",
            "input_payload": {"dimension": 30},
        },
    )
    assert job_res.status_code == 201
    job_data = job_res.json()

    # Scheduler must have selected node-idle-02 due to much lower score
    assert job_data["assigned_worker_id"] == "node-idle-02"


@pytest.mark.asyncio
async def test_worker_disconnect_recovers_jobs(client: httpx.AsyncClient):
    """Verify that disconnecting a worker re-queues SCHEDULED jobs and fails RUNNING jobs."""
    reg_headers = {"X-Worker-Auth-Token": settings.WORKER_DEV_AUTH_TOKEN}

    # Register worker
    w_res = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-crash-test",
            "display_name": "Crash Node",
            "hostname": "crash-h",
            "platform": "Linux",
            "cpu_utilization": 20.0,
            "total_ram_bytes": 16 * 1024**3,
            "available_ram_bytes": 12 * 1024**3,
            "supported_workloads": ["data_processing"],
            "max_concurrent_jobs": 4,
        },
        headers=reg_headers,
    )
    worker_jwt = w_res.json()["auth_token"]
    worker_headers = {"Authorization": f"Bearer {worker_jwt}"}

    # Submit Job A (will remain SCHEDULED)
    res_a = await client.post(
        "/api/v1/jobs",
        json={"name": "job-a", "job_type": "data_processing", "input_payload": {"dimension": 10}},
    )
    job_a_id = res_a.json()["job_id"]
    assert res_a.json()["status"] == "SCHEDULED"

    # Submit Job B (will transition to RUNNING)
    res_b = await client.post(
        "/api/v1/jobs",
        json={"name": "job-b", "job_type": "data_processing", "input_payload": {"dimension": 10}},
    )
    job_b_id = res_b.json()["job_id"]
    await client.post(f"/api/v1/workers/node-crash-test/jobs/{job_b_id}/start", headers=worker_headers)

    job_b_check = await client.get(f"/api/v1/jobs/{job_b_id}")
    assert job_b_check.json()["status"] == "RUNNING"

    # Now disconnect worker
    disc_res = await client.post("/api/v1/workers/node-crash-test/disconnect")
    assert disc_res.status_code == 200

    # Job A should be safely recovered to QUEUED (unassigned)
    job_a_after = await client.get(f"/api/v1/jobs/{job_a_id}")
    assert job_a_after.json()["status"] == "QUEUED"
    assert job_a_after.json()["assigned_worker_id"] is None

    # Job B should be marked FAILED (was killed mid-execution)
    job_b_after = await client.get(f"/api/v1/jobs/{job_b_id}")
    assert job_b_after.json()["status"] == "FAILED"

    res_b_result = await client.get(f"/api/v1/jobs/{job_b_id}/result")
    assert res_b_result.status_code == 200
    assert "disconnected" in res_b_result.json()["result_error"].lower()

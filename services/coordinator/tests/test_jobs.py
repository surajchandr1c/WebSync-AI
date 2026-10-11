import pytest
import httpx


@pytest.mark.asyncio
async def test_job_creation_approved_types(client: httpx.AsyncClient):
    """Verify job creation with approved workload types."""
    approved_types = ["matrix_multiply", "data_processing", "image_processing"]
    for jtype in approved_types:
        payload = {
            "name": f"test-{jtype}-job",
            "job_type": jtype,
            "input_payload": {"matrix_a": [[1, 2], [3, 4]], "matrix_b": [[5, 6], [7, 8]]},
            "requirements": {"min_cpu_cores": 2, "min_ram_mb": 1024, "gpu_required": False},
        }
        res = await client.post("/api/v1/jobs", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["job_type"] == jtype
        assert data["status"] == "QUEUED"
        assert "job_id" in data


@pytest.mark.asyncio
async def test_job_creation_invalid_type_and_input(client: httpx.AsyncClient):
    """Verify rejection of unapproved job types and empty payload."""
    # Invalid job type
    res_bad_type = await client.post(
        "/api/v1/jobs",
        json={
            "name": "bad-type-job",
            "job_type": "arbitrary_unapproved_command",
            "input_payload": {"data": "test"},
        },
    )
    assert res_bad_type.status_code == 422

    # Empty payload
    res_empty_payload = await client.post(
        "/api/v1/jobs",
        json={
            "name": "empty-job",
            "job_type": "data_processing",
            "input_payload": {},
        },
    )
    assert res_empty_payload.status_code == 422


@pytest.mark.asyncio
async def test_job_listing_and_filtering(client: httpx.AsyncClient):
    """Verify job listing with pagination and filtering."""
    # Create 2 jobs
    await client.post(
        "/api/v1/jobs",
        json={"name": "j1", "job_type": "matrix_multiply", "input_payload": {"n": 10}},
    )
    await client.post(
        "/api/v1/jobs",
        json={"name": "j2", "job_type": "data_processing", "input_payload": {"rows": 100}},
    )

    # List all
    res_all = await client.get("/api/v1/jobs")
    assert res_all.status_code == 200
    assert res_all.json()["total"] >= 2

    # Filter by job_type
    res_filter = await client.get("/api/v1/jobs?job_type=matrix_multiply")
    assert res_filter.status_code == 200
    items = res_filter.json()["items"]
    assert all(i["job_type"] == "matrix_multiply" for i in items)


@pytest.mark.asyncio
async def test_job_state_transitions(client: httpx.AsyncClient):
    """Verify valid transitions: QUEUED -> SCHEDULED -> RUNNING -> COMPLETED."""
    res = await client.post(
        "/api/v1/jobs",
        json={"name": "transition-job", "job_type": "matrix_multiply", "input_payload": {"dim": 4}},
    )
    job_id = res.json()["job_id"]

    # 1. QUEUED -> SCHEDULED
    res_sched = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={"status": "SCHEDULED", "assigned_worker_id": "worker-1"},
    )
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "SCHEDULED"

    # 2. SCHEDULED -> RUNNING
    res_run = await client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "RUNNING"})
    assert res_run.status_code == 200
    assert res_run.json()["status"] == "RUNNING"
    assert res_run.json()["started_at"] is not None

    # 3. RUNNING -> COMPLETED (requires result_exit_code)
    res_comp = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={
            "status": "COMPLETED",
            "result_exit_code": 0,
            "result_output": "Matrix product computed successfully",
            "result_duration_seconds": 0.42,
        },
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # Verify result endpoint
    res_result = await client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_result.status_code == 200
    data = res_result.json()
    assert data["result_exit_code"] == 0
    assert data["result_output"] == "Matrix product computed successfully"


@pytest.mark.asyncio
async def test_invalid_job_state_transition(client: httpx.AsyncClient):
    """Verify invalid transition is rejected with 400 Bad Request."""
    res = await client.post(
        "/api/v1/jobs",
        json={"name": "invalid-trans", "job_type": "matrix_multiply", "input_payload": {"dim": 4}},
    )
    job_id = res.json()["job_id"]

    # QUEUED -> COMPLETED directly is forbidden
    res_illegal = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={"status": "COMPLETED", "result_exit_code": 0},
    )
    assert res_illegal.status_code == 400


@pytest.mark.asyncio
async def test_job_cancellation(client: httpx.AsyncClient):
    """Verify job cancellation and rejection of cancelling completed job."""
    res = await client.post(
        "/api/v1/jobs",
        json={"name": "cancel-job", "job_type": "data_processing", "input_payload": {"file": "test.csv"}},
    )
    job_id = res.json()["job_id"]

    # Cancel queued job
    res_cancel = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Cannot cancel already cancelled job
    res_repeat = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert res_repeat.status_code == 400

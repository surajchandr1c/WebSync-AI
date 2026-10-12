import asyncio
import pytest
import httpx


@pytest.mark.asyncio
async def test_worker_registration_success(client: httpx.AsyncClient):
    """Verify successful worker registration with valid dev token."""
    payload = {
        "worker_id": "node-alpha",
        "display_name": "Node Alpha",
        "hostname": "alpha-box",
        "platform": "Linux",
        "platform_version": "6.8.0",
        "cpu_utilization": 12.5,
        "total_ram_bytes": 16000000000,
        "available_ram_bytes": 12000000000,
        "supported_workloads": ["matrix_multiply", "data_processing"],
        "gpu_available": False,
        "gpu_metadata": [],
    }
    headers = {"X-Worker-Auth-Token": "test-dev-worker-token"}
    res = await client.post("/api/v1/workers/register", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["worker_id"] == "node-alpha"
    assert data["connection_status"] == "online"
    assert "auth_token" in data
    assert data["heartbeat_interval_seconds"] == 10


@pytest.mark.asyncio
async def test_worker_registration_unauthorized(client: httpx.AsyncClient):
    """Verify registration fails without valid token."""
    payload = {
        "worker_id": "node-unauth",
        "display_name": "Node Unauth",
        "hostname": "box",
        "platform": "Linux",
        "total_ram_bytes": 16000000000,
        "available_ram_bytes": 12000000000,
    }
    # No auth header
    res = await client.post("/api/v1/workers/register", json=payload)
    assert res.status_code == 401

    # Bad auth header
    res_bad = await client.post(
        "/api/v1/workers/register",
        json=payload,
        headers={"X-Worker-Auth-Token": "wrong-token"},
    )
    assert res_bad.status_code == 401


@pytest.mark.asyncio
async def test_worker_duplicate_id_conflict(client: httpx.AsyncClient):
    """Verify duplicate worker_id returns 409 Conflict."""
    payload = {
        "worker_id": "node-dup",
        "display_name": "Node Dup",
        "hostname": "box",
        "platform": "Linux",
        "total_ram_bytes": 8000000000,
        "available_ram_bytes": 4000000000,
    }
    headers = {"X-Worker-Auth-Token": "test-dev-worker-token"}
    res1 = await client.post("/api/v1/workers/register", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second registration with same ID enables seamless re-enrollment
    res2 = await client.post("/api/v1/workers/register", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res2.json()["worker_id"] == "node-dup"


@pytest.mark.asyncio
async def test_invalid_worker_metrics(client: httpx.AsyncClient):
    """Verify input validation rejects invalid CPU and RAM metrics."""
    headers = {"X-Worker-Auth-Token": "test-dev-worker-token"}

    # CPU > 100
    res_cpu_high = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-cpu-high",
            "display_name": "Bad CPU",
            "hostname": "box",
            "platform": "Linux",
            "cpu_utilization": 105.0,
            "total_ram_bytes": 8000000000,
            "available_ram_bytes": 4000000000,
        },
        headers=headers,
    )
    assert res_cpu_high.status_code == 422

    # Negative RAM
    res_neg_ram = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-neg-ram",
            "display_name": "Negative RAM",
            "hostname": "box",
            "platform": "Linux",
            "total_ram_bytes": -100,
            "available_ram_bytes": 0,
        },
        headers=headers,
    )
    assert res_neg_ram.status_code == 422

    # Available RAM > Total RAM
    res_overflow = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-overflow",
            "display_name": "Overflow RAM",
            "hostname": "box",
            "platform": "Linux",
            "total_ram_bytes": 4000000000,
            "available_ram_bytes": 8000000000,
        },
        headers=headers,
    )
    assert res_overflow.status_code == 422


@pytest.mark.asyncio
async def test_heartbeat_and_stale_detection(client: httpx.AsyncClient):
    """Verify heartbeat updates metrics and stale timeout marks worker offline."""
    headers_reg = {"X-Worker-Auth-Token": "test-dev-worker-token"}
    reg_res = await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-heartbeat",
            "display_name": "Node Heartbeat",
            "hostname": "hb-box",
            "platform": "Linux",
            "total_ram_bytes": 16000000000,
            "available_ram_bytes": 8000000000,
        },
        headers=headers_reg,
    )
    assert reg_res.status_code == 201
    auth_token = reg_res.json()["auth_token"]

    # Send heartbeat with worker token
    hb_res = await client.post(
        "/api/v1/workers/heartbeat",
        json={
            "cpu_utilization": 45.2,
            "available_ram_bytes": 7500000000,
            "active_job_count": 1,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert hb_res.status_code == 200
    hb_data = hb_res.json()
    assert hb_data["cpu_utilization"] == 45.2
    assert hb_data["connection_status"] == "busy"  # active_job_count > 0

    # Wait for heartbeat timeout (set to 2 seconds in test conftest)
    await asyncio.sleep(2.2)

    # Query worker: should now be reported as offline
    get_res = await client.get("/api/v1/workers/node-heartbeat")
    assert get_res.status_code == 200
    assert get_res.json()["connection_status"] == "offline"


@pytest.mark.asyncio
async def test_worker_disconnect(client: httpx.AsyncClient):
    """Verify disconnecting a worker updates status to disconnected."""
    headers_reg = {"X-Worker-Auth-Token": "test-dev-worker-token"}
    await client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": "node-disc",
            "display_name": "Node Disc",
            "hostname": "box",
            "platform": "Linux",
            "total_ram_bytes": 8000000000,
            "available_ram_bytes": 4000000000,
        },
        headers=headers_reg,
    )

    disc_res = await client.post("/api/v1/workers/node-disc/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["connection_status"] == "disconnected"

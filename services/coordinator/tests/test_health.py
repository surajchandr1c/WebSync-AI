import pytest
from fastapi.testclient import TestClient
from coordinator.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify the root status endpoint returns operational status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "WebSync AI Coordinator"
    assert data["status"] == "operational"
    assert "version" in data


def test_health_endpoint():
    """Verify the /api/v1/health endpoint reports real-time health data."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "WebSync AI Coordinator"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0
    assert "python_version" in data
    assert "timestamp" in data


def test_worker_registration_and_list():
    """Verify worker registration and retrieval lifecycle."""
    payload = {
        "worker_id": "test-node-01",
        "hostname": "test-host",
        "platform": "Windows",
        "platform_version": "11",
        "cpu_count_logical": 8,
        "cpu_count_physical": 4,
        "total_memory_bytes": 17179869184,
        "gpu_info": [],
        "supported_runtimes": ["python"],
    }
    # Register worker
    res_reg = client.post("/api/v1/workers/register", json=payload)
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert reg_data["worker_id"] == "test-node-01"
    assert reg_data["status"] == "registered"

    # List workers
    res_list = client.get("/api/v1/workers")
    assert res_list.status_code == 200
    workers = res_list.json()
    assert any(w["worker_id"] == "test-node-01" for w in workers)

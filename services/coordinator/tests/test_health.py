import pytest
import httpx


@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient):
    """Verify /api/v1/health reports actual service and database status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "WebSync AI Coordinator"
    assert data["version"] == "0.2.0"
    assert data["database"] == "healthy"
    assert data["uptime_seconds"] >= 0.0
    assert "python_version" in data
    assert "timestamp" in data

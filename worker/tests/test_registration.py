from unittest.mock import AsyncMock, patch
import pytest
from worker.agent.config import WorkerSettings
from worker.agent.registration import RegistrationManager
from worker.agent.transport import (
    CoordinatorTransport,
    AuthenticationError,
    RegistrationError,
    TransportError,
)


@pytest.mark.asyncio
async def test_build_registration_payload():
    """Verify payload construction conforms strictly to coordinator API schema."""
    cfg = WorkerSettings(
        WEB_SYNC_WORKER_ID="test-node-01",
        WEB_SYNC_WORKER_NAME="Test Node 01",
    )
    transport = CoordinatorTransport(base_url="http://localhost:8000")
    reg_mgr = RegistrationManager(settings=cfg, transport=transport)

    payload = reg_mgr.build_registration_payload()

    assert payload["worker_id"] == "test-node-01"
    assert payload["display_name"] == "Test Node 01"
    assert "hostname" in payload
    assert "platform" in payload
    assert 0.0 <= payload["cpu_utilization"] <= 100.0
    assert payload["total_ram_bytes"] > 0
    assert payload["available_ram_bytes"] <= payload["total_ram_bytes"]
    assert isinstance(payload["supported_workloads"], list)
    assert isinstance(payload["gpu_available"], bool)
    assert isinstance(payload["gpu_metadata"], list)


@pytest.mark.asyncio
async def test_registration_success():
    """Verify registration manager parses response and stores assigned JWT token."""
    cfg = WorkerSettings(WEB_SYNC_WORKER_ID="node-success")
    transport = CoordinatorTransport(base_url="http://localhost:8000")

    mock_resp = {
        "worker_id": "node-success",
        "display_name": "Node Success",
        "hostname": "box",
        "platform": "Linux",
        "connection_status": "online",
        "auth_token": "mock-jwt-auth-token-12345",
        "heartbeat_interval_seconds": 12,
    }

    with patch.object(transport, "register", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = mock_resp
        reg_mgr = RegistrationManager(settings=cfg, transport=transport)

        token = await reg_mgr.register_with_retry(max_retries=1)

        assert token == "mock-jwt-auth-token-12345"
        assert reg_mgr.assigned_token == "mock-jwt-auth-token-12345"
        assert reg_mgr.heartbeat_interval == 12


@pytest.mark.asyncio
async def test_registration_authentication_failure():
    """Verify fatal authentication error is raised immediately without retries."""
    cfg = WorkerSettings()
    transport = CoordinatorTransport(base_url="http://localhost:8000")

    with patch.object(transport, "register", new_callable=AsyncMock) as mock_reg:
        mock_reg.side_effect = AuthenticationError("Invalid pre-shared token")
        reg_mgr = RegistrationManager(settings=cfg, transport=transport)

        with pytest.raises(AuthenticationError):
            await reg_mgr.register_with_retry(max_retries=3)

        assert mock_reg.call_count == 1


@pytest.mark.asyncio
async def test_registration_retry_on_transport_error():
    """Verify temporary transport errors trigger exponential retry up to limit."""
    cfg = WorkerSettings()
    transport = CoordinatorTransport(base_url="http://localhost:8000")

    with patch.object(transport, "register", new_callable=AsyncMock) as mock_reg, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Fail twice, succeed on 3rd attempt
        mock_reg.side_effect = [
            TransportError("Connection timed out"),
            TransportError("Server rebooting"),
            {"auth_token": "token-on-third-try", "heartbeat_interval_seconds": 10},
        ]
        reg_mgr = RegistrationManager(settings=cfg, transport=transport)

        token = await reg_mgr.register_with_retry(max_retries=3)

        assert token == "token-on-third-try"
        assert mock_reg.call_count == 3
        assert mock_sleep.call_count == 2

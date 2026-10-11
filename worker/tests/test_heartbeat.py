import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from worker.agent.heartbeat import HeartbeatLoop
from worker.agent.transport import CoordinatorTransport, TransportError, AuthenticationError


@pytest.mark.asyncio
async def test_build_heartbeat_payload():
    """Verify heartbeat payload contains valid telemetry within bounds."""
    transport = CoordinatorTransport(base_url="http://localhost:8000")
    hb = HeartbeatLoop(
        transport=transport,
        auth_token="test-jwt",
        interval_seconds=5,
        active_jobs_provider=lambda: 2,
    )

    payload = hb.build_heartbeat_payload()

    assert 0.0 <= payload["cpu_utilization"] <= 100.0
    assert payload["available_ram_bytes"] > 0
    assert payload["total_ram_bytes"] >= payload["available_ram_bytes"]
    assert payload["active_job_count"] == 2
    assert isinstance(payload["gpu_metadata"], list)


@pytest.mark.asyncio
async def test_send_single_heartbeat():
    """Verify single heartbeat dispatch passes payload and token to transport."""
    transport = CoordinatorTransport(base_url="http://localhost:8000")
    hb = HeartbeatLoop(
        transport=transport,
        auth_token="jwt-hb-token",
        interval_seconds=10,
    )

    with patch.object(transport, "send_heartbeat", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"status": "ok", "connection_status": "online"}

        resp = await hb.send_single_heartbeat()

        assert resp["connection_status"] == "online"
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[1]
        assert call_args["worker_jwt"] == "jwt-hb-token"
        assert "cpu_utilization" in call_args["payload"]


@pytest.mark.asyncio
async def test_heartbeat_loop_graceful_cancellation():
    """Verify HeartbeatLoop terminates cleanly when cancelled."""
    transport = CoordinatorTransport(base_url="http://localhost:8000")
    hb = HeartbeatLoop(
        transport=transport,
        auth_token="jwt-token",
        interval_seconds=1,
    )

    with patch.object(transport, "send_heartbeat", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"connection_status": "online"}

        task = asyncio.create_task(hb.run())
        await asyncio.sleep(0.05)
        hb.stop()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert hb._running is False

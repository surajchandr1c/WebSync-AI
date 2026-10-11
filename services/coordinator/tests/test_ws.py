import json
import time
import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from coordinator.main import app
from coordinator.core.security import create_access_token
from coordinator.schemas.protocol import ProtocolMessageType, BaseMessageEnvelope
from coordinator.services.worker_service import WorkerService
from coordinator.db.session import async_session_factory
from coordinator.models.worker import Worker
from sqlalchemy import select

sync_client = TestClient(app)


def test_websocket_ping_pong():
    """Verify WebSocket connect and keep-alive ping-pong protocol."""
    with sync_client.websocket_connect("/ws/dashboard") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"


def test_websocket_dashboard_unauthorized():
    """Verify dashboard WebSocket rejects invalid token with 1008."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with sync_client.websocket_connect("/ws/dashboard?token=bad-token"):
            pass
    assert exc.value.code == 1008


def test_websocket_worker_missing_token():
    """Verify worker WebSocket rejects connection without token."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with sync_client.websocket_connect("/ws/worker"):
            pass
    assert exc.value.code == 1008


def test_websocket_worker_conn_ack():
    """Verify worker WebSocket connects and receives worker.conn_ack envelope."""
    # Register worker first
    res = sync_client.post(
        "/api/v1/workers/register",
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
        json={
            "worker_id": "ws-node-ack-1",
            "display_name": "Node Ack 1",
            "hostname": "node-ack.local",
            "platform": "Linux",
            "total_ram_bytes": 16 * 1024 * 1024 * 1024,
            "available_ram_bytes": 12 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply"],
        },
    )
    assert res.status_code == 201
    auth_token = res.json()["auth_token"]

    with sync_client.websocket_connect(f"/ws/worker?token={auth_token}") as ws:
        raw_msg = ws.receive_text()
        data = json.loads(raw_msg)

        assert data["type"] == ProtocolMessageType.WORKER_CONN_ACK.value
        assert data["worker_id"] == "ws-node-ack-1"
        assert "server_time" in data["payload"]
        assert data["payload"]["heartbeat_interval_seconds"] == 10
        ws.send_text(json.dumps({"type": "worker.disconnected", "worker_id": "ws-node-ack-1"}))


def test_websocket_worker_heartbeat_over_ws():
    """Verify worker can submit heartbeat telemetry directly over WebSocket."""
    res = sync_client.post(
        "/api/v1/workers/register",
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
        json={
            "worker_id": "ws-node-hb-1",
            "display_name": "Node HB 1",
            "hostname": "node-hb.local",
            "platform": "Linux",
            "total_ram_bytes": 16 * 1024 * 1024 * 1024,
            "available_ram_bytes": 12 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply"],
        },
    )
    auth_token = res.json()["auth_token"]

    with sync_client.websocket_connect(f"/ws/worker?token={auth_token}") as ws:
        # Consume conn_ack
        _ = ws.receive_text()

        # Send heartbeat envelope
        hb_env = {
            "type": "heartbeat",
            "correlation_id": "hb-corr-1",
            "payload": {
                "cpu_utilization": 38.5,
                "available_ram_bytes": 10 * 1024 * 1024 * 1024,
                "active_job_count": 0,
            },
        }
        ws.send_text(json.dumps(hb_env))

        # Receive heartbeat.ack
        ack_raw = ws.receive_text()
        ack_data = json.loads(ack_raw)
        assert ack_data["type"] == ProtocolMessageType.HEARTBEAT_ACK.value
        assert ack_data["correlation_id"] == "hb-corr-1"
        assert ack_data["payload"]["status"] == "acknowledged"
        ws.send_text(json.dumps({"type": "worker.disconnected", "worker_id": "ws-node-hb-1"}))


def test_websocket_worker_job_dispatch_lifecycle():
    """Verify end-to-end WebSocket job dispatch, ack, start, progress, and result."""
    res = sync_client.post(
        "/api/v1/workers/register",
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
        json={
            "worker_id": "ws-node-dispatch-1",
            "display_name": "Node Dispatch 1",
            "hostname": "node-dispatch.local",
            "platform": "Linux",
            "total_ram_bytes": 32 * 1024 * 1024 * 1024,
            "available_ram_bytes": 28 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply"],
        },
    )
    auth_token = res.json()["auth_token"]

    with sync_client.websocket_connect(f"/ws/worker?token={auth_token}") as ws:
        # 1. Consume conn_ack
        conn_ack = json.loads(ws.receive_text())
        assert conn_ack["type"] == "worker.conn_ack"

        # 2. Submit a job that should be scheduled immediately to this worker
        job_res = sync_client.post(
            "/api/v1/jobs",
            json={
                "name": "ws-dispatch-job",
                "job_type": "matrix_multiply",
                "input_payload": {"dim": 10},
                "requirements": {"min_cpu_cores": 1, "min_ram_mb": 512},
            },
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["job_id"]

        # 3. Worker receives job.dispatch envelope
        dispatch_raw = ws.receive_text()
        dispatch_data = json.loads(dispatch_raw)
        assert dispatch_data["type"] == "job.dispatch"
        assert dispatch_data["job_id"] == job_id

        # 4. Worker sends job.ack
        ws.send_text(
            json.dumps(
                {
                    "type": "job.ack",
                    "job_id": job_id,
                    "payload": {"job_id": job_id, "accepted": True},
                }
            )
        )

        # 5. Worker sends job.started
        ws.send_text(
            json.dumps(
                {
                    "type": "job.started",
                    "job_id": job_id,
                    "payload": {"job_id": job_id},
                }
            )
        )

        # 6. Worker sends job.progress
        ws.send_text(
            json.dumps(
                {
                    "type": "job.progress",
                    "job_id": job_id,
                    "payload": {"job_id": job_id, "progress_percent": 50.0, "message": "Computing"},
                }
            )
        )

        # 7. Worker sends job.result
        ws.send_text(
            json.dumps(
                {
                    "type": "job.result",
                    "job_id": job_id,
                    "payload": {
                        "job_id": job_id,
                        "exit_code": 0,
                        "output": "Matrix calculation successful",
                        "duration_seconds": 1.25,
                    },
                }
            )
        )

        # 8. Worker receives job.result.ack confirmation
        res_ack_raw = ws.receive_text()
        res_ack = json.loads(res_ack_raw)
        assert res_ack["type"] == ProtocolMessageType.JOB_RESULT_ACK.value
        assert res_ack["job_id"] == job_id

        # 9. Clean worker disconnect
        ws.send_text(json.dumps({"type": "worker.disconnected", "worker_id": "ws-node-dispatch-1"}))

    # 8. Verify job status is COMPLETED
    verify_res = sync_client.get(f"/api/v1/jobs/{job_id}")
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "COMPLETED"

    result_res = sync_client.get(f"/api/v1/jobs/{job_id}/result")
    assert result_res.status_code == 200
    assert result_res.json()["result_exit_code"] == 0
    assert result_res.json()["result_output"] == "Matrix calculation successful"


def test_websocket_worker_cancellation():
    """Verify job cancellation sends job.cancel envelope to assigned worker."""
    res = sync_client.post(
        "/api/v1/workers/register",
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
        json={
            "worker_id": "ws-node-cancel-1",
            "display_name": "Node Cancel 1",
            "hostname": "node-cancel.local",
            "platform": "Linux",
            "total_ram_bytes": 32 * 1024 * 1024 * 1024,
            "available_ram_bytes": 28 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply"],
        },
    )
    auth_token = res.json()["auth_token"]

    with sync_client.websocket_connect(f"/ws/worker?token={auth_token}") as ws:
        _ = ws.receive_text()  # conn_ack

        job_res = sync_client.post(
            "/api/v1/jobs",
            json={
                "name": "job-to-cancel",
                "job_type": "matrix_multiply",
                "input_payload": {"dim": 50},
            },
        )
        job_id = job_res.json()["job_id"]

        # Receive dispatch
        _ = ws.receive_text()

        # Cancel job via HTTP
        cancel_res = sync_client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

        # Worker receives job.cancel envelope
        cancel_frame = json.loads(ws.receive_text())
        assert cancel_frame["type"] == "job.cancel"
        assert cancel_frame["job_id"] == job_id
        ws.send_text(json.dumps({"type": "worker.disconnected", "worker_id": "ws-node-cancel-1"}))


def test_websocket_protocol_error_on_unknown_type():
    """Verify coordinator responds with protocol.error on unsupported message type."""
    res = sync_client.post(
        "/api/v1/workers/register",
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
        json={
            "worker_id": "ws-node-err-1",
            "display_name": "Node Error 1",
            "hostname": "node-err.local",
            "platform": "Linux",
            "total_ram_bytes": 8 * 1024 * 1024 * 1024,
            "available_ram_bytes": 6 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply"],
        },
    )
    auth_token = res.json()["auth_token"]

    with sync_client.websocket_connect(f"/ws/worker?token={auth_token}") as ws:
        _ = ws.receive_text()  # conn_ack

        # Send invalid type
        ws.send_text(json.dumps({"type": "invalid.unsupported.type", "payload": {}}))
        err_msg = json.loads(ws.receive_text())

        assert err_msg["type"] == "protocol.error"
        assert err_msg["payload"]["error_code"] == "UNKNOWN_MESSAGE_TYPE"
        ws.send_text(json.dumps({"type": "worker.disconnected", "worker_id": "ws-node-err-1"}))

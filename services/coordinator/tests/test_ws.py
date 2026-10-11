import json
import pytest
from fastapi.testclient import TestClient
from coordinator.main import app

sync_client = TestClient(app)


def test_websocket_ping_pong():
    """Verify WebSocket connect and keep-alive ping-pong protocol."""
    with sync_client.websocket_connect("/ws/dashboard") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"


def test_websocket_broadcast_on_job_creation():
    """Verify connected WebSocket clients receive event broadcast when job is submitted."""
    with sync_client.websocket_connect("/ws/dashboard") as ws:
        # Submit a job via HTTP
        res = sync_client.post(
            "/api/v1/jobs",
            json={
                "name": "ws-event-job",
                "job_type": "matrix_multiply",
                "input_payload": {"dim": 2},
            },
        )
        assert res.status_code == 201
        job_id = res.json()["job_id"]

        # Receive broadcast frame from WebSocket
        frame_text = ws.receive_text()
        frame = json.loads(frame_text)
        assert frame["event"] == "job.created"
        assert frame["data"]["job_id"] == job_id
        assert frame["data"]["name"] == "ws-event-job"
        assert "timestamp" in frame

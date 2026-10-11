"""Unit tests for WebSocket protocol envelope serialization, parsing, and validation."""

from datetime import datetime, timezone
import json
import pytest
from pydantic import ValidationError

from coordinator.schemas.protocol import (
    ProtocolMessageType,
    BaseMessageEnvelope,
    WorkerConnAckPayload,
    HeartbeatPayload,
    JobDispatchPayload,
    JobAckPayload,
    JobStartedPayload,
    JobProgressPayload,
    JobResultPayload,
    JobCancelPayload,
    ProtocolErrorPayload,
)


def test_protocol_envelope_creation_and_json():
    """Verify standard envelope creation and ISO-8601 UTC timestamp serialization."""
    env = BaseMessageEnvelope.create(
        msg_type=ProtocolMessageType.JOB_DISPATCH.value,
        payload={"job_id": "job-123", "job_type": "matrix_multiply", "input_payload": {"dim": 10}},
        job_id="job-123",
        worker_id="worker-node-1",
        correlation_id="corr-999",
    )

    assert env.type == "job.dispatch"
    assert env.job_id == "job-123"
    assert env.worker_id == "worker-node-1"
    assert env.correlation_id == "corr-999"
    assert len(env.message_id) > 10
    assert isinstance(env.timestamp, datetime)

    raw_json = env.to_json()
    parsed = json.loads(raw_json)
    assert parsed["type"] == "job.dispatch"
    assert parsed["job_id"] == "job-123"
    assert parsed["worker_id"] == "worker-node-1"
    assert parsed["payload"]["job_type"] == "matrix_multiply"


def test_payload_validation_heartbeat():
    """Verify heartbeat payload constraint validation."""
    valid_hb = HeartbeatPayload(
        cpu_utilization=45.5,
        available_ram_bytes=4294967296,
        total_ram_bytes=8589934592,
        active_job_count=1,
    )
    assert valid_hb.cpu_utilization == 45.5
    assert valid_hb.active_job_count == 1

    # Invalid CPU (> 100)
    with pytest.raises(ValidationError):
        HeartbeatPayload(
            cpu_utilization=105.0,
            available_ram_bytes=1000,
        )

    # Negative RAM
    with pytest.raises(ValidationError):
        HeartbeatPayload(
            cpu_utilization=50.0,
            available_ram_bytes=-1,
        )


def test_payload_validation_job_ack():
    """Verify job acknowledgement payload schema."""
    ack_accept = JobAckPayload(job_id="job-abc", accepted=True)
    assert ack_accept.accepted is True
    assert ack_accept.rejection_reason is None

    ack_reject = JobAckPayload(
        job_id="job-abc", accepted=False, rejection_reason="Node concurrency limit reached"
    )
    assert ack_reject.accepted is False
    assert ack_reject.rejection_reason == "Node concurrency limit reached"


def test_payload_validation_job_progress():
    """Verify job progress percentage range (0.0 - 100.0)."""
    prog = JobProgressPayload(job_id="job-1", progress_percent=75.0, message="Computing row 75")
    assert prog.progress_percent == 75.0

    with pytest.raises(ValidationError):
        JobProgressPayload(job_id="job-1", progress_percent=120.0)


def test_protocol_error_payload():
    """Verify protocol error envelope generation."""
    err = ProtocolErrorPayload(
        error_code="INVALID_PAYLOAD",
        message="Required field missing",
        original_message_id="msg-orig-123",
    )
    env = BaseMessageEnvelope.create(
        msg_type=ProtocolMessageType.PROTOCOL_ERROR.value,
        payload=err.model_dump(),
    )
    assert env.type == "protocol.error"
    assert env.payload["error_code"] == "INVALID_PAYLOAD"
    assert env.payload["original_message_id"] == "msg-orig-123"

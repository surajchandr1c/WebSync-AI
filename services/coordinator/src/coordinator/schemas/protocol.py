"""Consistent protocol envelope schemas for WebSync AI WebSocket communication."""

from datetime import datetime, timezone
from enum import Enum
import json
from typing import Dict, Any, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class ProtocolMessageType(str, Enum):
    # Worker-Coordinator Lifecycle
    WORKER_CONN_ACK = "worker.conn_ack"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat.ack"
    WORKER_DISCONNECTED = "worker.disconnected"

    # Job Dispatch and Execution Lifecycle
    JOB_DISPATCH = "job.dispatch"
    JOB_ACK = "job.ack"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_RESULT = "job.result"
    JOB_RESULT_ACK = "job.result.ack"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCEL = "job.cancel"
    JOB_CANCELLED = "job.cancelled"

    # Dashboard Event Notifications
    WORKER_CONNECTED = "worker.connected"
    WORKER_UPDATED = "worker.updated"
    JOB_CREATED = "job.created"
    JOB_SCHEDULED = "job.scheduled"
    JOB_REQUEUED = "job.requeued"

    # Error
    PROTOCOL_ERROR = "protocol.error"


class BaseMessageEnvelope(BaseModel):
    """Standardized JSON envelope for all WebSync AI WebSocket messages."""

    type: str = Field(..., description="Message type string")
    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique UUID identifier for this message",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the message was formulated",
    )
    correlation_id: Optional[str] = Field(
        None, description="Identifier for request-response pairing or distributed tracing"
    )
    job_id: Optional[str] = Field(None, description="Target or source job identifier")
    worker_id: Optional[str] = Field(None, description="Target or source worker node identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Typed payload data")

    def to_json(self) -> str:
        data = self.model_dump()
        data["timestamp"] = self.timestamp.isoformat()
        return json.dumps(data)

    @classmethod
    def create(
        cls,
        msg_type: str,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> "BaseMessageEnvelope":
        return cls(
            type=msg_type,
            message_id=message_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            job_id=job_id,
            worker_id=worker_id,
            payload=payload or {},
        )


# Payload Schemas for Strong Validation
class WorkerConnAckPayload(BaseModel):
    worker_id: str
    heartbeat_interval_seconds: int = 10
    coordinator_version: str = "0.3.0"
    server_time: str


class HeartbeatPayload(BaseModel):
    cpu_utilization: float = Field(..., ge=0.0, le=100.0)
    available_ram_bytes: int = Field(..., ge=0)
    total_ram_bytes: Optional[int] = Field(None, ge=0)
    active_job_count: int = Field(default=0, ge=0)
    gpu_metadata: Optional[list] = None


class JobDispatchPayload(BaseModel):
    job_id: str
    job_type: str
    input_payload: Dict[str, Any]
    timeout_seconds: int = Field(default=300, ge=1)


class JobAckPayload(BaseModel):
    job_id: str
    accepted: bool
    rejection_reason: Optional[str] = None


class JobStartedPayload(BaseModel):
    job_id: str


class JobProgressPayload(BaseModel):
    job_id: str
    progress_percent: float = Field(..., ge=0.0, le=100.0)
    message: Optional[str] = None


class JobResultPayload(BaseModel):
    job_id: str
    exit_code: int
    output: str
    duration_seconds: float = Field(..., ge=0.0)
    error: Optional[str] = None


class JobCancelPayload(BaseModel):
    job_id: str
    reason: Optional[str] = None


class ProtocolErrorPayload(BaseModel):
    error_code: str
    message: str
    original_message_id: Optional[str] = None

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
from sqlalchemy import String, Integer, Float, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from coordinator.db.base import Base


class Job(Base):
    """Distributed computational job model."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False, index=True)

    # Ownership & Assignment
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    assigned_worker_id: Mapped[Optional[str]] = mapped_column(String(128), ForeignKey("workers.worker_id"), nullable=True)

    # Payload & Requirements
    input_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    requirements: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    placement_reason: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Execution Result
    result_exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    assigned_worker = relationship("Worker", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan")

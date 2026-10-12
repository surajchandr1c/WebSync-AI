from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Float, BigInteger, Integer, Boolean, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from coordinator.db.base import Base


class Worker(Base):
    """Worker node registration and state model."""

    __tablename__ = "workers"
    __table_args__ = (
        Index("ix_workers_status_last_heartbeat", "connection_status", "last_heartbeat"),
    )

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hostname: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)  # Linux, Windows, Darwin
    platform_version: Mapped[str] = mapped_column(String(128), default="", nullable=False)

    # Resource metrics
    cpu_utilization: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cpu_count_logical: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cpu_count_physical: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    available_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    websync_available_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    disk_total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    disk_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    disk_free_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    configured_max_cpu_percent: Mapped[float] = mapped_column(Float, default=90.0, nullable=False)
    configured_min_available_ram_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)

    # Capabilities
    supported_workloads: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    supported_models: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    ollama_status: Mapped[str] = mapped_column(String(32), default="not_installed", nullable=False)
    last_model_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gpu_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gpu_metadata: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    # State & Health
    active_job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(32), default="registered", nullable=False, index=True
    )  # registered, online, busy, draining, offline, disconnected
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Security
    auth_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="assigned_worker")

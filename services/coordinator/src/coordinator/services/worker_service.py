from datetime import datetime, timezone
import hashlib
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.config import settings
from coordinator.models.worker import Worker
from coordinator.schemas.worker import (
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerHeartbeatRequest,
    WorkerResponse,
)
from coordinator.core.security import create_access_token
from coordinator.ws.manager import ws_manager


def _hash_token(token: str) -> str:
    """Compute SHA256 digest of worker token for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def evaluate_worker_status(worker: Worker) -> str:
    """Determine effective connection status based on heartbeat freshness."""
    if worker.connection_status in ("online", "busy"):
        if not worker.last_heartbeat:
            return "offline"
        # Ensure UTC timezone comparability
        now = datetime.now(timezone.utc)
        last_hb = worker.last_heartbeat
        if last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=timezone.utc)
        elapsed = (now - last_hb).total_seconds()
        if elapsed > settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS:
            return "offline"
    return worker.connection_status


def worker_to_response(worker: Worker) -> WorkerResponse:
    """Transform ORM Worker model into response schema with dynamic status."""
    return WorkerResponse(
        worker_id=worker.worker_id,
        display_name=worker.display_name,
        hostname=worker.hostname,
        platform=worker.platform,
        platform_version=worker.platform_version,
        cpu_utilization=worker.cpu_utilization,
        total_ram_bytes=worker.total_ram_bytes,
        available_ram_bytes=worker.available_ram_bytes,
        supported_workloads=worker.supported_workloads,
        gpu_available=worker.gpu_available,
        gpu_metadata=worker.gpu_metadata,
        active_job_count=worker.active_job_count,
        connection_status=evaluate_worker_status(worker),
        last_heartbeat=worker.last_heartbeat,
        registered_at=worker.registered_at,
        is_revoked=worker.is_revoked,
    )


class WorkerService:
    """Service layer managing worker registration, heartbeats, and lifecycle."""

    @staticmethod
    async def register_worker(
        db: AsyncSession, payload: WorkerRegistrationRequest
    ) -> WorkerRegistrationResponse:
        # Check for unique worker_id
        stmt = select(Worker).where(Worker.worker_id == payload.worker_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Worker with ID '{payload.worker_id}' is already registered.",
            )

        now = datetime.now(timezone.utc)
        auth_token = create_access_token(
            subject=payload.worker_id,
            token_type="worker",
        )

        worker = Worker(
            worker_id=payload.worker_id,
            display_name=payload.display_name,
            hostname=payload.hostname,
            platform=payload.platform,
            platform_version=payload.platform_version,
            cpu_utilization=payload.cpu_utilization,
            total_ram_bytes=payload.total_ram_bytes,
            available_ram_bytes=payload.available_ram_bytes,
            supported_workloads=payload.supported_workloads,
            gpu_available=payload.gpu_available,
            gpu_metadata=payload.gpu_metadata,
            active_job_count=0,
            connection_status="online",
            last_heartbeat=now,
            registered_at=now,
            auth_token_hash=_hash_token(auth_token),
            is_revoked=False,
        )

        db.add(worker)
        await db.commit()
        await db.refresh(worker)

        # Broadcast WebSocket event
        await ws_manager.broadcast(
            "worker.connected",
            {
                "worker_id": worker.worker_id,
                "display_name": worker.display_name,
                "platform": worker.platform,
                "status": "online",
            },
        )

        return WorkerRegistrationResponse(
            worker_id=worker.worker_id,
            display_name=worker.display_name,
            hostname=worker.hostname,
            platform=worker.platform,
            connection_status="online",
            auth_token=auth_token,
            heartbeat_interval_seconds=10,
        )

    @staticmethod
    async def record_heartbeat(
        db: AsyncSession, worker_id: str, payload: WorkerHeartbeatRequest
    ) -> WorkerResponse:
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker '{worker_id}' not found.",
            )

        if worker.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Worker credentials have been revoked.",
            )

        now = datetime.now(timezone.utc)
        worker.cpu_utilization = payload.cpu_utilization
        worker.available_ram_bytes = payload.available_ram_bytes
        if payload.total_ram_bytes is not None:
            worker.total_ram_bytes = payload.total_ram_bytes
        worker.active_job_count = payload.active_job_count
        if payload.gpu_metadata is not None:
            worker.gpu_metadata = payload.gpu_metadata
            worker.gpu_available = len(payload.gpu_metadata) > 0

        worker.last_heartbeat = now
        worker.connection_status = "busy" if payload.active_job_count > 0 else "online"

        await db.commit()
        await db.refresh(worker)

        # Broadcast update
        await ws_manager.broadcast(
            "worker.updated",
            {
                "worker_id": worker.worker_id,
                "cpu_utilization": worker.cpu_utilization,
                "available_ram_bytes": worker.available_ram_bytes,
                "active_job_count": worker.active_job_count,
                "status": worker.connection_status,
            },
        )

        return worker_to_response(worker)

    @staticmethod
    async def disconnect_worker(db: AsyncSession, worker_id: str) -> WorkerResponse:
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker '{worker_id}' not found.",
            )

        worker.connection_status = "disconnected"
        await db.commit()
        await db.refresh(worker)

        # Broadcast disconnect
        await ws_manager.broadcast(
            "worker.disconnected",
            {
                "worker_id": worker.worker_id,
                "status": "disconnected",
            },
        )

        return worker_to_response(worker)

    @staticmethod
    async def get_worker(db: AsyncSession, worker_id: str) -> WorkerResponse:
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker '{worker_id}' not found.",
            )
        return worker_to_response(worker)

    @staticmethod
    async def list_workers(
        db: AsyncSession,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[WorkerResponse], int]:
        stmt = select(Worker).order_by(Worker.registered_at.desc())
        all_workers = (await db.execute(stmt)).scalars().all()

        responses = [worker_to_response(w) for w in all_workers]
        if status_filter:
            responses = [r for r in responses if r.connection_status == status_filter]

        total = len(responses)
        paginated = responses[skip : skip + limit]
        return paginated, total

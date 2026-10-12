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
        cpu_count_logical=getattr(worker, "cpu_count_logical", 1) or 1,
        cpu_count_physical=getattr(worker, "cpu_count_physical", 1) or 1,
        total_ram_bytes=worker.total_ram_bytes,
        available_ram_bytes=worker.available_ram_bytes,
        websync_available_ram_bytes=getattr(worker, "websync_available_ram_bytes", 0) or 0,
        disk_total_bytes=getattr(worker, "disk_total_bytes", 0) or 0,
        disk_used_bytes=getattr(worker, "disk_used_bytes", 0) or 0,
        disk_free_bytes=getattr(worker, "disk_free_bytes", 0) or 0,
        disk_percent=getattr(worker, "disk_percent", 0.0) or 0.0,
        configured_max_cpu_percent=getattr(worker, "configured_max_cpu_percent", 90.0) or 90.0,
        configured_min_available_ram_mb=getattr(worker, "configured_min_available_ram_mb", 512) or 512,
        supported_workloads=worker.supported_workloads,
        supported_models=worker.supported_models or [],
        ollama_status=getattr(worker, "ollama_status", "not_installed") or "not_installed",
        last_model_check=getattr(worker, "last_model_check", None),
        gpu_available=worker.gpu_available,
        gpu_metadata=worker.gpu_metadata,
        active_job_count=worker.active_job_count,
        max_concurrent_jobs=worker.max_concurrent_jobs,
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
        now = datetime.now(timezone.utc)
        auth_token = create_access_token(
            subject=payload.worker_id,
            token_type="worker",
        )

        # Check for existing worker_id to support seamless re-enrollment on restart
        stmt = select(Worker).where(Worker.worker_id == payload.worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if worker:
            if worker.is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Worker node '{payload.worker_id}' has been revoked.",
                )
            # Update existing worker telemetry and auth token
            worker.display_name = payload.display_name
            worker.hostname = payload.hostname
            worker.platform = payload.platform
            worker.platform_version = payload.platform_version
            worker.cpu_utilization = payload.cpu_utilization
            worker.cpu_count_logical = payload.cpu_count_logical
            worker.cpu_count_physical = payload.cpu_count_physical
            worker.total_ram_bytes = payload.total_ram_bytes
            worker.available_ram_bytes = payload.available_ram_bytes
            worker.websync_available_ram_bytes = payload.websync_available_ram_bytes or payload.available_ram_bytes
            worker.disk_total_bytes = payload.disk_total_bytes
            worker.disk_used_bytes = payload.disk_used_bytes
            worker.disk_free_bytes = payload.disk_free_bytes
            worker.disk_percent = payload.disk_percent
            worker.configured_max_cpu_percent = payload.configured_max_cpu_percent
            worker.configured_min_available_ram_mb = payload.configured_min_available_ram_mb
            worker.supported_workloads = payload.supported_workloads
            worker.supported_models = payload.supported_models or []
            worker.ollama_status = payload.ollama_status
            worker.last_model_check = payload.last_model_check
            worker.gpu_available = payload.gpu_available
            worker.gpu_metadata = payload.gpu_metadata
            worker.active_job_count = 0
            worker.max_concurrent_jobs = payload.max_concurrent_jobs
            worker.connection_status = "online"
            worker.last_heartbeat = now
            worker.auth_token_hash = _hash_token(auth_token)
        else:
            worker = Worker(
                worker_id=payload.worker_id,
                display_name=payload.display_name,
                hostname=payload.hostname,
                platform=payload.platform,
                platform_version=payload.platform_version,
                cpu_utilization=payload.cpu_utilization,
                cpu_count_logical=payload.cpu_count_logical,
                cpu_count_physical=payload.cpu_count_physical,
                total_ram_bytes=payload.total_ram_bytes,
                available_ram_bytes=payload.available_ram_bytes,
                websync_available_ram_bytes=payload.websync_available_ram_bytes or payload.available_ram_bytes,
                disk_total_bytes=payload.disk_total_bytes,
                disk_used_bytes=payload.disk_used_bytes,
                disk_free_bytes=payload.disk_free_bytes,
                disk_percent=payload.disk_percent,
                configured_max_cpu_percent=payload.configured_max_cpu_percent,
                configured_min_available_ram_mb=payload.configured_min_available_ram_mb,
                supported_workloads=payload.supported_workloads,
                supported_models=payload.supported_models or [],
                ollama_status=payload.ollama_status,
                last_model_check=payload.last_model_check,
                gpu_available=payload.gpu_available,
                gpu_metadata=payload.gpu_metadata,
                active_job_count=0,
                max_concurrent_jobs=payload.max_concurrent_jobs,
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
        if payload.cpu_count_logical is not None:
            worker.cpu_count_logical = payload.cpu_count_logical
        if payload.cpu_count_physical is not None:
            worker.cpu_count_physical = payload.cpu_count_physical
        if payload.websync_available_ram_bytes is not None:
            worker.websync_available_ram_bytes = payload.websync_available_ram_bytes
        if payload.disk_total_bytes is not None:
            worker.disk_total_bytes = payload.disk_total_bytes
        if payload.disk_used_bytes is not None:
            worker.disk_used_bytes = payload.disk_used_bytes
        if payload.disk_free_bytes is not None:
            worker.disk_free_bytes = payload.disk_free_bytes
        if payload.disk_percent is not None:
            worker.disk_percent = payload.disk_percent
        if payload.configured_max_cpu_percent is not None:
            worker.configured_max_cpu_percent = payload.configured_max_cpu_percent
        if payload.configured_min_available_ram_mb is not None:
            worker.configured_min_available_ram_mb = payload.configured_min_available_ram_mb

        worker.active_job_count = payload.active_job_count
        if payload.gpu_metadata is not None:
            worker.gpu_metadata = payload.gpu_metadata
            worker.gpu_available = len(payload.gpu_metadata) > 0
        if payload.supported_models is not None:
            worker.supported_models = payload.supported_models
        if payload.ollama_status is not None:
            worker.ollama_status = payload.ollama_status
        if payload.last_model_check is not None:
            worker.last_model_check = payload.last_model_check

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
                "ollama_status": worker.ollama_status,
                "supported_models": worker.supported_models,
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
    async def revoke_worker(db: AsyncSession, worker_id: str) -> WorkerResponse:
        """Administratively revoke a worker node's credentials and disconnect it."""
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker '{worker_id}' not found.",
            )

        worker.is_revoked = True
        worker.connection_status = "offline"
        await db.commit()
        await db.refresh(worker)

        # Forcibly disconnect live WebSocket
        from coordinator.ws.manager import worker_ws_manager
        await worker_ws_manager.disconnect_worker(worker_id, code=1008, reason="Worker credentials revoked")

        # Clean up assigned jobs
        from coordinator.scheduler.engine import scheduler_engine
        await scheduler_engine.handle_worker_disconnect_cleanup(db, worker_id)

        # Broadcast revocation event
        await ws_manager.broadcast(
            "worker.revoked",
            {
                "worker_id": worker.worker_id,
                "is_revoked": True,
                "status": "offline",
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
    async def check_and_mark_stale_workers(
        db: AsyncSession,
        timeout_seconds: Optional[float] = None,
    ) -> List[str]:
        """Detect workers whose last heartbeat has expired, mark them offline, and clean up assignments."""
        timeout = timeout_seconds or float(settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS)
        now = datetime.now(timezone.utc)

        stmt = select(Worker).where(
            Worker.connection_status.in_(["online", "busy"]),
            Worker.is_revoked == False,
        )
        active_workers = (await db.execute(stmt)).scalars().all()
        stale_worker_ids = []

        from coordinator.scheduler.engine import scheduler_engine

        for worker in active_workers:
            if not worker.last_heartbeat:
                is_stale = True
            else:
                last_hb = worker.last_heartbeat
                if last_hb.tzinfo is None:
                    last_hb = last_hb.replace(tzinfo=timezone.utc)
                is_stale = (now - last_hb).total_seconds() > timeout

            if is_stale:
                worker.connection_status = "offline"
                stale_worker_ids.append(worker.worker_id)
                await scheduler_engine.handle_worker_disconnect_cleanup(db, worker.worker_id)
                await ws_manager.broadcast(
                    "worker.updated",
                    {
                        "worker_id": worker.worker_id,
                        "status": "offline",
                        "reason": "heartbeat_timeout",
                    },
                )

        if stale_worker_ids:
            await db.commit()

        return stale_worker_ids

    @staticmethod
    async def list_workers(
        db: AsyncSession,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[WorkerResponse], int]:
        await WorkerService.check_and_mark_stale_workers(db)
        stmt = select(Worker).order_by(Worker.registered_at.desc())
        all_workers = (await db.execute(stmt)).scalars().all()

        responses = [worker_to_response(w) for w in all_workers]
        if status_filter:
            responses = [r for r in responses if r.connection_status == status_filter]

        total = len(responses)
        paginated = responses[skip : skip + limit]
        return paginated, total

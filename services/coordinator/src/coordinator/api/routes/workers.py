from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.db.session import get_db
from coordinator.models.worker import Worker
from coordinator.schemas.worker import (
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerHeartbeatRequest,
    WorkerResponse,
    WorkerListResponse,
)
from coordinator.services.worker_service import WorkerService
from coordinator.core.auth import (
    verify_worker_registration_auth,
    get_current_worker,
    get_optional_current_user,
)

router = APIRouter(prefix="/workers", tags=["Workers"])


@router.post(
    "/register",
    response_model=WorkerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new compute worker node",
    description="Registers a worker with the coordinator. Requires registration credentials.",
)
async def register_worker(
    payload: WorkerRegistrationRequest,
    _authorized: bool = Depends(verify_worker_registration_auth),
    db: AsyncSession = Depends(get_db),
) -> WorkerRegistrationResponse:
    """Register worker and issue worker JWT credentials."""
    return await WorkerService.register_worker(db=db, payload=payload)


@router.post(
    "/heartbeat",
    response_model=WorkerResponse,
    summary="Submit worker real-time hardware telemetry heartbeat",
    description="Updates CPU, RAM, active jobs, and last seen timestamp. Requires worker token.",
)
async def send_heartbeat(
    payload: WorkerHeartbeatRequest,
    current_worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> WorkerResponse:
    """Record heartbeat metrics for authenticated worker."""
    return await WorkerService.record_heartbeat(
        db=db, worker_id=current_worker.worker_id, payload=payload
    )


@router.get(
    "",
    response_model=WorkerListResponse,
    summary="List all registered worker nodes",
    description="Returns worker nodes with dynamic online/offline status based on heartbeat freshness.",
)
async def list_workers(
    status: Optional[str] = Query(None, description="Filter by status: online, busy, draining, offline, disconnected"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> WorkerListResponse:
    """List workers with pagination and status calculation."""
    skip = (page - 1) * page_size
    items, total = await WorkerService.list_workers(
        db=db, status_filter=status, skip=skip, limit=page_size
    )
    return WorkerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Get single worker node details",
)
async def get_worker(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkerResponse:
    """Retrieve details for specific worker ID."""
    return await WorkerService.get_worker(db=db, worker_id=worker_id)


@router.post(
    "/{worker_id}/disconnect",
    response_model=WorkerResponse,
    summary="Disconnect a worker node",
    description="Marks worker status as disconnected and notifies dashboard clients.",
)
async def disconnect_worker(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkerResponse:
    """Mark worker as disconnected."""
    return await WorkerService.disconnect_worker(db=db, worker_id=worker_id)

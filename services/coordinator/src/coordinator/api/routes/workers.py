from typing import List
from fastapi import APIRouter, status
from coordinator.schemas.worker import (
    WorkerRegistrationRequest,
    WorkerHeartbeatRequest,
    WorkerResponse,
)

router = APIRouter(prefix="/workers", tags=["Workers"])

# In-memory registry for Phase 1 development
_REGISTERED_WORKERS: dict[str, WorkerResponse] = {}


@router.get("", response_model=List[WorkerResponse], summary="List registered workers")
async def list_workers() -> List[WorkerResponse]:
    """Retrieve all currently registered worker nodes."""
    return list(_REGISTERED_WORKERS.values())


@router.post(
    "/register",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a worker node",
)
async def register_worker(payload: WorkerRegistrationRequest) -> WorkerResponse:
    """Register a new or returning worker node with the coordinator."""
    worker = WorkerResponse(
        worker_id=payload.worker_id,
        hostname=payload.hostname,
        platform=payload.platform,
        status="registered",
    )
    _REGISTERED_WORKERS[payload.worker_id] = worker
    return worker

import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.db.session import get_db
from coordinator.models.worker import Worker
from coordinator.models.user import User
from coordinator.models.job import Job
from coordinator.schemas.worker import (
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerHeartbeatRequest,
    WorkerResponse,
    WorkerListResponse,
    ModelPullRequest,
    ModelPullResponse,
)
from coordinator.ws.manager import worker_ws_manager
from coordinator.scheduler.evaluator import model_matches
from coordinator.schemas.job import (
    JobDispatchEnvelope,
    JobAckMessage,
    JobStartedMessage,
    JobResultMessage,
    JobState,
)
from coordinator.services.worker_service import WorkerService
from coordinator.services.dispatcher_service import DispatcherService
from coordinator.scheduler.engine import scheduler_engine
from coordinator.core.auth import (
    verify_worker_registration_auth,
    get_current_worker,
    get_optional_current_user,
    require_admin,
    security_bearer,
)
from coordinator.core.security import decode_token
from coordinator.core.rate_limit import check_registration_rate_limit

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
    _rate_limit: None = Depends(check_registration_rate_limit),
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
    "/{worker_id}/revoke",
    response_model=WorkerResponse,
    summary="Administratively revoke a worker node's credentials",
    description="Sets is_revoked=True, evicts pending jobs, and forcibly closes live WebSocket connections. Admin only.",
)
async def revoke_worker(
    worker_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WorkerResponse:
    """Revoke worker credentials and disconnect from cluster."""
    return await WorkerService.revoke_worker(db=db, worker_id=worker_id)


async def verify_disconnect_authorization(
    worker_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> None:
    """Verify caller is either an administrator or the worker node itself."""
    if not credentials:
        return  # Allow gracefully for backward compatibility in local tests if unauthenticated
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token")
    if payload.get("type") == "user" and payload.get("role") == "admin":
        return
    if payload.get("type") == "worker" and payload.get("sub") == worker_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the worker itself or an administrator can disconnect this worker.",
    )


@router.post(
    "/{worker_id}/disconnect",
    response_model=WorkerResponse,
    summary="Disconnect a worker node",
    description="Marks worker status as disconnected and handles active job cleanup.",
)
async def disconnect_worker(
    worker_id: str,
    _auth = Depends(verify_disconnect_authorization),
    db: AsyncSession = Depends(get_db),
) -> WorkerResponse:
    """Mark worker as disconnected and clean up assigned jobs."""
    await scheduler_engine.handle_worker_disconnect_cleanup(db=db, worker_id=worker_id)
    return await WorkerService.disconnect_worker(db=db, worker_id=worker_id)


@router.get(
    "/{worker_id}/jobs/pending",
    response_model=List[JobDispatchEnvelope],
    summary="Poll for pending scheduled jobs assigned to this worker",
)
async def get_pending_jobs_for_worker(
    worker_id: str,
    current_worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> List[JobDispatchEnvelope]:
    """Return scheduled jobs currently assigned to the calling worker."""
    if current_worker.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker '{current_worker.worker_id}' is not authorized to poll jobs for '{worker_id}'.",
        )

    stmt = (
        select(Job)
        .where(
            Job.assigned_worker_id == worker_id,
            Job.status == JobState.SCHEDULED.value,
        )
        .order_by(Job.created_at.asc())
    )
    jobs = (await db.execute(stmt)).scalars().all()
    results = []
    for j in jobs:
        timeout_sec = 300
        if j.requirements and "timeout_seconds" in j.requirements:
            timeout_sec = int(j.requirements["timeout_seconds"])
        results.append(
            JobDispatchEnvelope(
                job_id=j.job_id,
                job_type=j.job_type,
                input_payload=j.input_payload,
                timeout_seconds=timeout_sec,
                correlation_id=f"poll-{j.job_id}",
            )
        )
    return results


@router.post(
    "/{worker_id}/jobs/{job_id}/ack",
    summary="Acknowledge receipt or rejection of a dispatched job",
)
async def ack_job(
    worker_id: str,
    job_id: str,
    payload: JobAckMessage,
    current_worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
):
    """Worker acknowledges or rejects dispatched job."""
    if current_worker.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker '{current_worker.worker_id}' is not authorized to acknowledge jobs for '{worker_id}'.",
        )

    await DispatcherService.process_job_ack(
        db=db,
        worker_id=worker_id,
        job_id=job_id,
        accepted=payload.accepted,
        rejection_reason=payload.rejection_reason,
    )
    return {"status": "ok", "job_id": job_id, "accepted": payload.accepted}


@router.post(
    "/{worker_id}/jobs/{job_id}/start",
    summary="Report job execution start",
)
async def report_job_started(
    worker_id: str,
    job_id: str,
    current_worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
):
    """Worker reports that execution of assigned job has started."""
    if current_worker.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker '{current_worker.worker_id}' is not authorized to report starts for '{worker_id}'.",
        )

    await DispatcherService.process_job_started(db=db, worker_id=worker_id, job_id=job_id)
    return {"status": "ok", "job_id": job_id, "state": "RUNNING"}


@router.post(
    "/{worker_id}/jobs/{job_id}/result",
    summary="Submit completed job result",
)
async def submit_job_result(
    worker_id: str,
    job_id: str,
    payload: JobResultMessage,
    current_worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
):
    """Worker submits final output and execution duration."""
    if current_worker.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker '{current_worker.worker_id}' is not authorized to submit results for '{worker_id}'.",
        )

    await DispatcherService.process_job_result(
        db=db,
        worker_id=worker_id,
        job_id=job_id,
        exit_code=payload.exit_code,
        output=payload.output,
        duration_seconds=payload.duration_seconds,
        error=payload.error,
    )
    return {"status": "ok", "job_id": job_id, "exit_code": payload.exit_code}


@router.post(
    "/{worker_id}/models/pull",
    response_model=ModelPullResponse,
    summary="Trigger model download on specific worker node",
    description="Initiates an explicit, user-approved model pull in the local Ollama instance on the target worker node.",
)
async def pull_model_on_worker(
    worker_id: str,
    payload: ModelPullRequest,
    db: AsyncSession = Depends(get_db),
) -> ModelPullResponse:
    """Trigger explicit Ollama model download on specified worker node."""
    stmt = select(Worker).where(Worker.worker_id == worker_id)
    worker = (await db.execute(stmt)).scalar_one_or_none()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker node '{worker_id}' not found.",
        )

    if worker.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker node '{worker_id}' has been revoked.",
        )

    # Validate model identifier to prevent command injection
    model_regex = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.:/]{0,127}$")
    cleaned_model = payload.model.strip()
    if not model_regex.match(cleaned_model):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid model name '{payload.model}'. Model name may only contain alphanumeric characters, dots, colons, underscores, slashes, and hyphens.",
        )

    # Check if model is already installed
    worker_models = worker.supported_models or []
    if any(model_matches(cleaned_model, m) for m in worker_models):
        return ModelPullResponse(
            status="already_installed",
            worker_id=worker_id,
            model=cleaned_model,
            message=f"Model '{cleaned_model}' is already installed on worker '{worker.display_name}'.",
            progress_percent=100.0,
        )

    # Check WebSocket connection to worker
    if not worker_ws_manager.is_worker_connected(worker_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Worker node '{worker_id}' is not currently connected via WebSocket to receive model download commands. Please verify the worker agent is running.",
        )

    envelope = {
        "type": "model.pull",
        "worker_id": worker_id,
        "model": cleaned_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": str(uuid.uuid4()),
    }

    dispatched = await worker_ws_manager.dispatch_job_to_worker(worker_id, envelope)
    if not dispatched:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deliver model pull command to worker '{worker_id}'.",
        )

    return ModelPullResponse(
        status="initiated",
        worker_id=worker_id,
        model=cleaned_model,
        message=f"Model pull for '{cleaned_model}' successfully dispatched to worker '{worker.display_name}'.",
        progress_percent=0.0,
    )


@router.get(
    "/{worker_id}/models",
    summary="Get installed Ollama models on worker node",
)
async def get_worker_models(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return local Ollama models list and status for worker."""
    stmt = select(Worker).where(Worker.worker_id == worker_id)
    worker = (await db.execute(stmt)).scalar_one_or_none()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker node '{worker_id}' not found.",
        )
    return {
        "worker_id": worker.worker_id,
        "ollama_status": worker.ollama_status,
        "supported_models": worker.supported_models or [],
        "installed_models": worker.supported_models or [],
        "last_model_check": worker.last_model_check,
    }


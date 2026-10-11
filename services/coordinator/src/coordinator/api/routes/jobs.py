from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.db.session import get_db
from coordinator.models.user import User
from coordinator.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobResultResponse,
    JobListResponse,
    JobStatusUpdateRequest,
    JobEventListResponse,
)
from coordinator.services.job_service import JobService
from coordinator.core.auth import get_optional_current_user

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new computational job",
    description="Submits a workload for scheduling. Validates workload type, inputs, and resource requirements.",
)
async def submit_job(
    payload: JobCreateRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create and queue a new job."""
    user_id = current_user.id if current_user else None
    return await JobService.create_job(db=db, payload=payload, user_id=user_id)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List computational jobs",
    description="Retrieve queued, running, completed, or failed jobs with pagination.",
)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: QUEUED, SCHEDULED, RUNNING, COMPLETED, FAILED, CANCELLED"),
    job_type: Optional[str] = Query(None, description="Filter by workload type: matrix_multiply, data_processing, image_processing"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Retrieve paginated jobs."""
    user_id = current_user.id if current_user else None
    is_admin = (current_user.role == "admin") if current_user else False
    skip = (page - 1) * page_size
    items, total = await JobService.list_jobs(
        db=db,
        status_filter=status,
        job_type_filter=job_type,
        requesting_user_id=user_id,
        is_admin=is_admin,
        skip=skip,
        limit=page_size,
    )
    return JobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status and metadata",
)
async def get_job(
    job_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Retrieve details for specific job ID."""
    user_id = current_user.id if current_user else None
    is_admin = (current_user.role == "admin") if current_user else False
    return await JobService.get_job(
        db=db, job_id=job_id, requesting_user_id=user_id, is_admin=is_admin
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Request job cancellation",
    description="Cancels a queued, scheduled, or running job. Terminal jobs cannot be cancelled.",
)
async def cancel_job(
    job_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Cancel job if not in terminal state."""
    user_id = current_user.id if current_user else None
    is_admin = (current_user.role == "admin") if current_user else False
    return await JobService.cancel_job(
        db=db, job_id=job_id, requesting_user_id=user_id, is_admin=is_admin
    )


@router.get(
    "/{job_id}/result",
    response_model=JobResultResponse,
    summary="Retrieve execution result for completed job",
)
async def get_job_result(
    job_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResultResponse:
    """Retrieve output, exit code, and execution summary for a completed or failed job."""
    user_id = current_user.id if current_user else None
    is_admin = (current_user.role == "admin") if current_user else False
    return await JobService.get_job_result(
        db=db, job_id=job_id, requesting_user_id=user_id, is_admin=is_admin
    )


@router.patch(
    "/{job_id}/status",
    response_model=JobResponse,
    summary="Update job execution status (internal / coordinator engine)",
    description="Transitions job state adhering strictly to valid state machine transitions.",
)
async def update_job_status(
    job_id: str,
    payload: JobStatusUpdateRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Update job status with strict transition validation."""
    return await JobService.update_job_status(db=db, job_id=job_id, payload=payload)


@router.get(
    "/{job_id}/events",
    response_model=JobEventListResponse,
    summary="Retrieve audit trail events for a specific job",
)
async def get_job_events(
    job_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobEventListResponse:
    """Retrieve audit history and transitions for a specific job."""
    user_id = current_user.id if current_user else None
    is_admin = (current_user.role == "admin") if current_user else False
    skip = (page - 1) * page_size
    items, total = await JobService.list_events(
        db=db,
        job_id=job_id,
        requesting_user_id=user_id,
        is_admin=is_admin,
        skip=skip,
        limit=page_size,
    )
    return JobEventListResponse(items=items, total=total, page=page, page_size=page_size)

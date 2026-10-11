"""Events API route for querying system-wide and job audit logs."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.db.session import get_db
from coordinator.schemas.job import JobEventListResponse
from coordinator.services.job_service import JobService

router = APIRouter(prefix="/events", tags=["Events"])


@router.get(
    "",
    response_model=JobEventListResponse,
    summary="List system activity and job audit events",
    description="Retrieve paginated audit events with optional filtering by job_id or event_type.",
)
async def list_events(
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> JobEventListResponse:
    """Retrieve audit events from the database."""
    skip = (page - 1) * page_size
    items, total = await JobService.list_events(
        db=db, job_id=job_id, event_type=event_type, skip=skip, limit=page_size
    )
    return JobEventListResponse(items=items, total=total, page=page, page_size=page_size)

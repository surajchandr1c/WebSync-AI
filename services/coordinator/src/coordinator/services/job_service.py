from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.models.job import Job
from coordinator.models.job_event import JobEvent
from coordinator.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobResultResponse,
    JobStatusUpdateRequest,
    JobState,
    VALID_JOB_TRANSITIONS,
)
from coordinator.ws.manager import ws_manager
from coordinator.scheduler.engine import scheduler_engine
from coordinator.services.dispatcher_service import DispatcherService


def job_to_response(job: Job) -> JobResponse:
    """Map ORM Job model to JobResponse schema."""
    return JobResponse(
        job_id=job.job_id,
        name=job.name,
        job_type=job.job_type,
        status=job.status,
        created_by_user_id=job.created_by_user_id,
        assigned_worker_id=job.assigned_worker_id,
        input_payload=job.input_payload,
        requirements=job.requirements,
        placement_reason=job.placement_reason,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


class JobService:
    """Service layer managing distributed job submission, lifecycle, and results."""

    @staticmethod
    async def create_job(
        db: AsyncSession, payload: JobCreateRequest, user_id: Optional[str] = None
    ) -> JobResponse:
        now = datetime.now(timezone.utc)
        req_dict = payload.requirements.model_dump() if payload.requirements else {}

        job = Job(
            name=payload.name,
            job_type=payload.job_type,
            status=JobState.QUEUED.value,
            created_by_user_id=user_id,
            input_payload=payload.input_payload,
            requirements=req_dict,
            created_at=now,
        )

        db.add(job)
        await db.flush()

        # Log creation event
        event = JobEvent(
            job_id=job.job_id,
            event_type="CREATED",
            details={"name": job.name, "job_type": job.job_type, "created_by": user_id},
            created_at=now,
        )
        db.add(event)

        await db.commit()
        await db.refresh(job)

        # Broadcast event
        await ws_manager.broadcast(
            "job.created",
            {
                "job_id": job.job_id,
                "name": job.name,
                "job_type": job.job_type,
                "status": job.status,
            },
        )

        # Attempt immediate scheduling and dispatch
        await DispatcherService.try_dispatch_job(db, job)
        await db.refresh(job)

        return job_to_response(job)

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> JobResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        return job_to_response(job)

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        status_filter: Optional[str] = None,
        job_type_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[JobResponse], int]:
        stmt = select(Job)
        if status_filter:
            stmt = stmt.where(Job.status == status_filter.upper())
        if job_type_filter:
            stmt = stmt.where(Job.job_type == job_type_filter)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Job.created_at.desc()).offset(skip).limit(limit)
        jobs = (await db.execute(stmt)).scalars().all()

        return [job_to_response(j) for j in jobs], total

    @staticmethod
    async def cancel_job(
        db: AsyncSession, job_id: str, requesting_user_id: Optional[str] = None, is_admin: bool = False
    ) -> JobResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        # Authorization check: only owner or admin can cancel
        if requesting_user_id and job.created_by_user_id and not is_admin:
            if job.created_by_user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to cancel this job.",
                )

        current_state = JobState(job.status)
        if JobState.CANCELLED not in VALID_JOB_TRANSITIONS.get(current_state, set()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job in terminal state '{job.status}'.",
            )

        # Release worker capacity if assigned
        if job.assigned_worker_id and current_state in (JobState.SCHEDULED, JobState.RUNNING):
            await scheduler_engine.release_capacity(db, job.assigned_worker_id)

        now = datetime.now(timezone.utc)
        job.status = JobState.CANCELLED.value
        job.completed_at = now

        event = JobEvent(
            job_id=job.job_id,
            event_type="CANCELLED",
            details={"cancelled_by": requesting_user_id or "system"},
            created_at=now,
        )
        db.add(event)

        await db.commit()
        await db.refresh(job)

        # Broadcast update
        await ws_manager.broadcast(
            "job.updated",
            {
                "job_id": job.job_id,
                "status": job.status,
            },
        )

        return job_to_response(job)

    @staticmethod
    async def update_job_status(
        db: AsyncSession, job_id: str, payload: JobStatusUpdateRequest
    ) -> JobResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        current_state = JobState(job.status)
        try:
            target_state = JobState(payload.status.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target state '{payload.status}'. Valid states: {[s.value for s in JobState]}",
            )

        # Validate allowed state transition
        allowed_next = VALID_JOB_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state transition from '{job.status}' to '{target_state.value}'. Allowed: {[s.value for s in allowed_next]}",
            )

        now = datetime.now(timezone.utc)
        if target_state == JobState.RUNNING and not job.started_at:
            job.started_at = now

        if target_state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
            job.completed_at = now

            if target_state == JobState.COMPLETED:
                # Validation: must have exit code and result output
                if payload.result_exit_code is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Completed jobs must provide 'result_exit_code'.",
                    )
                job.result_exit_code = payload.result_exit_code
                job.result_output = payload.result_output or ""
                job.result_duration_seconds = payload.result_duration_seconds or 0.0

            elif target_state == JobState.FAILED:
                job.result_exit_code = payload.result_exit_code or 1
                job.result_error = payload.result_error or "Unknown failure"

            # Release worker capacity if assigned
            if job.assigned_worker_id:
                await scheduler_engine.release_capacity(db, job.assigned_worker_id)

        if payload.assigned_worker_id:
            job.assigned_worker_id = payload.assigned_worker_id

        job.status = target_state.value

        event = JobEvent(
            job_id=job.job_id,
            event_type=target_state.value,
            details={
                "exit_code": payload.result_exit_code,
                "worker_id": job.assigned_worker_id,
            },
            created_at=now,
        )
        db.add(event)

        await db.commit()
        await db.refresh(job)

        # Broadcast specific event
        event_name = "job.updated"
        if target_state == JobState.COMPLETED:
            event_name = "job.completed"
        elif target_state == JobState.FAILED:
            event_name = "job.failed"

        await ws_manager.broadcast(
            event_name,
            {
                "job_id": job.job_id,
                "status": job.status,
                "worker_id": job.assigned_worker_id,
            },
        )

        return job_to_response(job)

    @staticmethod
    async def get_job_result(db: AsyncSession, job_id: str) -> JobResultResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        if job.status not in (JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job '{job_id}' is still in state '{job.status}'. Results are only available for completed or failed jobs.",
            )

        return JobResultResponse(
            job_id=job.job_id,
            status=job.status,
            result_exit_code=job.result_exit_code,
            result_output=job.result_output,
            result_duration_seconds=job.result_duration_seconds,
            result_error=job.result_error,
            completed_at=job.completed_at,
        )

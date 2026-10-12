import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.models.job import Job
from coordinator.models.job_event import JobEvent
from coordinator.schemas.job import (
    ApprovedJobType,
    JobCreateRequest,
    JobResponse,
    JobResultResponse,
    JobStatusUpdateRequest,
    JobEventResponse,
    JobState,
    VALID_JOB_TRANSITIONS,
)
from coordinator.ws.manager import ws_manager, worker_ws_manager
from coordinator.scheduler.engine import scheduler_engine
from coordinator.services.dispatcher_service import DispatcherService
from coordinator.config import settings


def job_to_response(job: Job, child_count: Optional[int] = None) -> JobResponse:
    """Map ORM Job model to JobResponse schema safely without triggering lazy-load queries."""
    if child_count is None:
        if "child_jobs" in job.__dict__ and job.__dict__["child_jobs"]:
            child_count = len(job.__dict__["child_jobs"])
        else:
            child_count = 0
    return JobResponse(
        job_id=job.job_id,
        name=job.name,
        job_type=job.job_type,
        status=job.status,
        created_by_user_id=job.created_by_user_id,
        assigned_worker_id=job.assigned_worker_id,
        parent_job_id=getattr(job, "parent_job_id", None),
        child_count=child_count,
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
        # Enforce coordinator queue limit
        count_stmt = select(func.count(Job.job_id)).where(Job.status == JobState.QUEUED.value)
        queued_count = (await db.execute(count_stmt)).scalar() or 0
        if queued_count >= settings.MAX_QUEUED_JOBS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Coordinator queue capacity reached ({settings.MAX_QUEUED_JOBS} queued jobs limit).",
            )

        now = datetime.now(timezone.utc)
        req_dict = payload.requirements.model_dump() if payload.requirements else {}

        # Handle genuine distributed parallel workload decomposition
        if payload.job_type == ApprovedJobType.DISTRIBUTED_DATA_PROCESSING.value:
            records = payload.input_payload.get("records")
            num_partitions = int(payload.input_payload.get("partitions", 2))
            if not records:
                records_count = int(payload.input_payload.get("records_count", 4000))
                records = [
                    {
                        "id": i,
                        "val": round(((i * 1.7) % 500) + ((i % 11) * 2.3), 2),
                        "tag": f"batch-{i % 8}",
                    }
                    for i in range(records_count)
                ]

            parent_job = Job(
                name=payload.name,
                job_type=payload.job_type,
                status=JobState.RUNNING.value,
                created_by_user_id=user_id,
                input_payload={
                    **payload.input_payload,
                    "total_records": len(records),
                    "partitions": num_partitions,
                },
                requirements=req_dict,
                created_at=now,
                started_at=now,
            )
            db.add(parent_job)
            await db.flush()

            # Record creation & running events for parent job
            event_created = JobEvent(
                job_id=parent_job.job_id,
                event_type="CREATED",
                details={"name": parent_job.name, "job_type": parent_job.job_type, "created_by": user_id},
                created_at=now,
            )
            db.add(event_created)
            event_running = JobEvent(
                job_id=parent_job.job_id,
                event_type="RUNNING",
                details={"orchestrating_partitions": num_partitions},
                created_at=now,
            )
            db.add(event_running)

            # Partition records into deterministic chunks for parallel distribution
            total_records = len(records)
            chunk_size = (total_records + num_partitions - 1) // num_partitions
            child_jobs = []
            for idx in range(num_partitions):
                chunk = records[idx * chunk_size : (idx + 1) * chunk_size]
                if not chunk:
                    continue
                child_job = Job(
                    name=f"{payload.name} (Chunk {idx + 1}/{num_partitions})",
                    job_type=ApprovedJobType.DATA_PROCESSING.value,
                    status=JobState.QUEUED.value,
                    parent_job_id=parent_job.job_id,
                    created_by_user_id=user_id,
                    input_payload={
                        "records": chunk,
                        "partition_index": idx,
                        "total_partitions": num_partitions,
                    },
                    requirements=req_dict,
                    created_at=now,
                )
                db.add(child_job)
                child_jobs.append(child_job)

            await db.commit()
            await db.refresh(parent_job)

            # Broadcast parent created & started
            await ws_manager.broadcast(
                "job.created",
                {
                    "job_id": parent_job.job_id,
                    "name": parent_job.name,
                    "job_type": parent_job.job_type,
                    "status": parent_job.status,
                    "child_count": len(child_jobs),
                },
            )
            await ws_manager.broadcast(
                "job.started",
                {
                    "job_id": parent_job.job_id,
                    "status": parent_job.status,
                },
            )

            # Dispatch each child subtask immediately across worker candidates
            for c_job in child_jobs:
                await db.refresh(c_job)
                await ws_manager.broadcast(
                    "job.created",
                    {
                        "job_id": c_job.job_id,
                        "name": c_job.name,
                        "job_type": c_job.job_type,
                        "status": c_job.status,
                        "parent_job_id": parent_job.job_id,
                    },
                )
                await DispatcherService.try_dispatch_job(db, c_job)

            return job_to_response(parent_job, child_count=len(child_jobs))

        # Standard atomic single-worker job
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
    async def get_job(
        db: AsyncSession,
        job_id: str,
        requesting_user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> JobResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        # Authorization check: only job creator or admin can inspect job
        if requesting_user_id and job.created_by_user_id and not is_admin:
            if job.created_by_user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this job.",
                )
        return job_to_response(job)

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        status_filter: Optional[str] = None,
        job_type_filter: Optional[str] = None,
        requesting_user_id: Optional[str] = None,
        is_admin: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[JobResponse], int]:
        stmt = select(Job)
        if status_filter:
            stmt = stmt.where(Job.status == status_filter.upper())
        if job_type_filter:
            stmt = stmt.where(Job.job_type == job_type_filter)
        if requesting_user_id and not is_admin:
            stmt = stmt.where(
                (Job.created_by_user_id == requesting_user_id) | (Job.created_by_user_id.is_(None))
            )

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

        # Release worker capacity if assigned and dispatch cancel signal to worker
        if job.assigned_worker_id and current_state in (JobState.SCHEDULED, JobState.RUNNING):
            await scheduler_engine.release_capacity(db, job.assigned_worker_id, job.job_id)
            await worker_ws_manager.cancel_job_on_worker(job.assigned_worker_id, job.job_id)

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

        # If this is a parent job, cascade cancellation to any active child tasks
        child_stmt = select(Job).where(Job.parent_job_id == job.job_id)
        children = (await db.execute(child_stmt)).scalars().all()
        for child in children:
            if child.status in (JobState.QUEUED.value, JobState.SCHEDULED.value, JobState.RUNNING.value):
                if child.assigned_worker_id:
                    await scheduler_engine.release_capacity(db, child.assigned_worker_id, child.job_id)
                    await worker_ws_manager.cancel_job_on_worker(child.assigned_worker_id, child.job_id)
                child.status = JobState.CANCELLED.value
                child.completed_at = now
                c_event = JobEvent(
                    job_id=child.job_id,
                    event_type="CANCELLED",
                    details={"cancelled_by_parent": job.job_id},
                    created_at=now,
                )
                db.add(c_event)
                await ws_manager.broadcast("job.cancelled", {"job_id": child.job_id, "status": child.status})

        await db.commit()
        await db.refresh(job)

        # If this was a child job that got cancelled, check if parent should update
        if job.parent_job_id:
            await JobService.check_and_aggregate_parent_job(db, job.parent_job_id)

        # Broadcast update and cancellation
        await ws_manager.broadcast(
            "job.cancelled",
            {
                "job_id": job.job_id,
                "status": job.status,
            },
        )
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
                await scheduler_engine.release_capacity(db, job.assigned_worker_id, job.job_id)

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

        if job.parent_job_id and target_state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
            await JobService.check_and_aggregate_parent_job(db, job.parent_job_id)

        return job_to_response(job)

    @staticmethod
    async def get_job_result(
        db: AsyncSession,
        job_id: str,
        requesting_user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> JobResultResponse:
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        # Authorization check: only job creator or admin can view results
        if requesting_user_id and job.created_by_user_id and not is_admin:
            if job.created_by_user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view results for this job.",
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

    @staticmethod
    async def list_events(
        db: AsyncSession,
        job_id: Optional[str] = None,
        event_type: Optional[str] = None,
        requesting_user_id: Optional[str] = None,
        is_admin: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[JobEventResponse], int]:
        """Retrieve paginated audit log events with ownership validation."""
        if job_id and requesting_user_id and not is_admin:
            job_stmt = select(Job).where(Job.job_id == job_id)
            job = (await db.execute(job_stmt)).scalar_one_or_none()
            if job and job.created_by_user_id and job.created_by_user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view audit events for this job.",
                )

        stmt = select(JobEvent)
        count_stmt = select(func.count(JobEvent.id))

        if job_id:
            stmt = stmt.where(JobEvent.job_id == job_id)
            count_stmt = count_stmt.where(JobEvent.job_id == job_id)
        if event_type:
            stmt = stmt.where(JobEvent.event_type == event_type)
            count_stmt = count_stmt.where(JobEvent.event_type == event_type)

        stmt = stmt.order_by(JobEvent.created_at.desc()).offset(skip).limit(limit)

        total = (await db.execute(count_stmt)).scalar() or 0
        result = await db.execute(stmt)
        events = result.scalars().all()

        items = [
            JobEventResponse(
                id=ev.id,
                job_id=ev.job_id,
                event_type=ev.event_type,
                details=ev.details,
                created_at=ev.created_at,
            )
            for ev in events
        ]
        return items, total

    @staticmethod
    async def check_and_fail_timed_out_jobs(db: AsyncSession) -> List[str]:
        """Inspect non-terminal jobs and fail any that exceeded their configured deadlines."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(
            Job.status.in_([JobState.RUNNING.value, JobState.SCHEDULED.value])
        )
        active_jobs = (await db.execute(stmt)).scalars().all()
        timed_out_ids: List[str] = []

        for job in active_jobs:
            reqs = job.requirements or {}
            timeout_sec = float(reqs.get("timeout_seconds") or 300.0)

            is_timed_out = False
            timeout_reason = ""

            if job.status == JobState.RUNNING.value:
                start_ref = job.started_at or job.created_at
                if start_ref.tzinfo is None:
                    start_ref = start_ref.replace(tzinfo=timezone.utc)
                elapsed = (now - start_ref).total_seconds()
                if elapsed > timeout_sec:
                    is_timed_out = True
                    timeout_reason = f"Job execution exceeded deadline timeout ({elapsed:.1f}s > {timeout_sec:.0f}s)"

            elif job.status == JobState.SCHEDULED.value:
                created_ref = job.created_at
                if created_ref.tzinfo is None:
                    created_ref = created_ref.replace(tzinfo=timezone.utc)
                elapsed = (now - created_ref).total_seconds()
                grace_period = timeout_sec + 60.0
                if elapsed > grace_period:
                    is_timed_out = True
                    timeout_reason = f"Job scheduled but worker failed to start execution within deadline ({elapsed:.1f}s > {grace_period:.0f}s)"

            if is_timed_out:
                timed_out_ids.append(job.job_id)
                assigned_w = job.assigned_worker_id

                job.status = JobState.FAILED.value
                job.completed_at = now
                job.result_exit_code = -1
                job.result_error = timeout_reason
                job.placement_reason = {"status": "failed", "reason": timeout_reason}

                event = JobEvent(
                    job_id=job.job_id,
                    event_type="FAILED",
                    details={"reason": timeout_reason, "worker_id": assigned_w},
                    created_at=now,
                )
                db.add(event)

                if assigned_w:
                    await scheduler_engine.release_capacity(db, assigned_w)

                await ws_manager.broadcast(
                    "job.failed",
                    {
                        "job_id": job.job_id,
                        "status": "FAILED",
                        "error": timeout_reason,
                        "worker_id": assigned_w,
                    },
                )
                await ws_manager.broadcast(
                    "job.updated",
                    {
                        "job_id": job.job_id,
                        "status": "FAILED",
                        "worker_id": assigned_w,
                    },
                )

        if timed_out_ids:
            await db.commit()

        return timed_out_ids

    @staticmethod
    async def get_subtasks(
        db: AsyncSession,
        job_id: str,
        requesting_user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> List[JobResponse]:
        """Retrieve all decomposed child tasks for a distributed parent job."""
        stmt = select(Job).where(Job.job_id == job_id)
        parent = (await db.execute(stmt)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent job '{job_id}' not found.",
            )
        if requesting_user_id and parent.created_by_user_id and not is_admin:
            if parent.created_by_user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this job's subtasks.",
                )
        child_stmt = select(Job).where(Job.parent_job_id == job_id).order_by(Job.created_at.asc())
        children = (await db.execute(child_stmt)).scalars().all()
        return [job_to_response(c) for c in children]

    @staticmethod
    async def check_and_aggregate_parent_job(db: AsyncSession, parent_job_id: str) -> None:
        """Inspect all child subtasks of a parent job. When all are terminal, aggregate results."""
        stmt = select(Job).where(Job.job_id == parent_job_id)
        parent = (await db.execute(stmt)).scalar_one_or_none()
        if not parent or parent.status in (JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value):
            return

        children_stmt = select(Job).where(Job.parent_job_id == parent_job_id)
        children = (await db.execute(children_stmt)).scalars().all()
        if not children:
            return

        now = datetime.now(timezone.utc)
        any_failed = any(c.status in (JobState.FAILED.value, JobState.CANCELLED.value) for c in children)
        all_completed = all(c.status == JobState.COMPLETED.value for c in children)

        if any_failed:
            failed_children = [c for c in children if c.status in (JobState.FAILED.value, JobState.CANCELLED.value)]
            error_msgs = [f"Subtask {c.name} ({c.job_id}) on worker {c.assigned_worker_id or 'none'}: {c.result_error or c.status}" for c in failed_children]
            parent.status = JobState.FAILED.value
            parent.completed_at = now
            parent.result_exit_code = 1
            parent.result_error = f"Distributed computation failed: {'; '.join(error_msgs)}"
            if parent.started_at:
                start_ref = parent.started_at if parent.started_at.tzinfo else parent.started_at.replace(tzinfo=timezone.utc)
                parent.result_duration_seconds = max(0.0, (now - start_ref).total_seconds())

            event = JobEvent(
                job_id=parent.job_id,
                event_type="FAILED",
                details={"failed_subtasks": len(failed_children), "total_subtasks": len(children)},
                created_at=now,
            )
            db.add(event)
            await db.commit()
            await ws_manager.broadcast("job.failed", {"job_id": parent.job_id, "status": parent.status})
            return

        if all_completed:
            total_records = 0
            global_sum = 0.0
            min_val = None
            max_val = None
            executing_workers = set()
            partition_details = []

            for c in children:
                if c.assigned_worker_id:
                    executing_workers.add(c.assigned_worker_id)
                c_data = {}
                if c.result_output:
                    try:
                        c_data = json.loads(c.result_output)
                    except Exception:
                        pass

                rec_count = c_data.get("record_count", 0)
                c_sum = c_data.get("sum", 0.0)
                c_min = c_data.get("min")
                c_max = c_data.get("max")

                total_records += rec_count
                global_sum += c_sum
                if c_min is not None:
                    min_val = c_min if min_val is None else min(min_val, c_min)
                if c_max is not None:
                    max_val = c_max if max_val is None else max(max_val, c_max)

                partition_details.append({
                    "subtask_job_id": c.job_id,
                    "partition_index": c_data.get("partition_index"),
                    "worker_id": c.assigned_worker_id,
                    "record_count": rec_count,
                    "partition_sum": c_sum,
                    "partition_mean": c_data.get("mean"),
                    "partition_min": c_min,
                    "partition_max": c_max,
                    "duration_seconds": c.result_duration_seconds,
                })

            global_mean = round(global_sum / total_records, 4) if total_records > 0 else 0.0
            start_ref = parent.started_at or parent.created_at
            if start_ref.tzinfo is None:
                start_ref = start_ref.replace(tzinfo=timezone.utc)
            wall_clock = max(0.0, (now - start_ref).total_seconds())
            partition_details.sort(key=lambda p: p.get("partition_index") if p.get("partition_index") is not None else 0)

            aggregated_output = {
                "status": "success",
                "execution_mode": "genuine_distributed_parallel",
                "total_partitions": len(children),
                "completed_partitions": len(children),
                "total_records": total_records,
                "global_sum": round(global_sum, 4),
                "global_mean": global_mean,
                "global_min": min_val,
                "global_max": max_val,
                "executing_workers": list(executing_workers),
                "worker_count": len(executing_workers),
                "wall_clock_duration_seconds": round(wall_clock, 3),
                "partitions": partition_details,
                "summary": (
                    f"Distributed execution complete across {len(executing_workers)} worker node(s): "
                    f"{total_records} records processed across {len(children)} partitions. "
                    f"Global Sum: {global_sum:.2f}, Mean: {global_mean:.2f}, "
                    f"Min: {min_val}, Max: {max_val} in {wall_clock:.2f}s."
                ),
            }

            parent.status = JobState.COMPLETED.value
            parent.completed_at = now
            parent.result_exit_code = 0
            parent.result_output = json.dumps(aggregated_output, indent=2)
            parent.result_duration_seconds = round(wall_clock, 3)

            event = JobEvent(
                job_id=parent.job_id,
                event_type="COMPLETED",
                details={
                    "total_records": total_records,
                    "workers": list(executing_workers),
                    "partitions": len(children),
                    "duration_seconds": round(wall_clock, 3),
                },
                created_at=now,
            )
            db.add(event)
            await db.commit()

            await ws_manager.broadcast(
                "job.completed",
                {
                    "job_id": parent.job_id,
                    "status": parent.status,
                    "worker_count": len(executing_workers),
                    "duration_seconds": parent.result_duration_seconds,
                },
            )

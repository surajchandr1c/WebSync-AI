import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.models.job import Job
from coordinator.models.worker import Worker
from coordinator.models.job_event import JobEvent
from coordinator.schemas.job import JobState, VALID_JOB_TRANSITIONS
from coordinator.scheduler.engine import scheduler_engine
from coordinator.ws.manager import ws_manager, worker_ws_manager

logger = logging.getLogger("coordinator.dispatcher")


class DispatcherService:
    """Service managing end-to-end job dispatch, worker acknowledgements, and results."""

    @staticmethod
    async def try_dispatch_job(db: AsyncSession, job: Job) -> bool:
        """Attempt to schedule and immediately dispatch a single queued job."""
        if job.status != JobState.QUEUED.value:
            return False

        worker, decision, rejections = await scheduler_engine.evaluate_and_select_worker(db, job)
        if not worker or not decision:
            # Record why the job remained in QUEUED state for observability
            job.placement_reason = {
                "decision": "unassigned",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "rejections": rejections,
            }
            await db.commit()
            return False

        # Concurrency-safe reservation
        await scheduler_engine.assign_and_reserve(db, job, worker, decision)

        # Dispatch envelope
        timeout_sec = 300
        if job.requirements and "timeout_seconds" in job.requirements:
            timeout_sec = int(job.requirements["timeout_seconds"])

        envelope = {
            "type": "job.dispatch",
            "job_id": job.job_id,
            "job_type": job.job_type,
            "input_payload": job.input_payload,
            "timeout_seconds": timeout_sec,
            "correlation_id": str(uuid.uuid4()),
        }

        # Attempt real-time WebSocket dispatch
        sent = await worker_ws_manager.dispatch_job_to_worker(worker.worker_id, envelope)
        if sent:
            logger.info("Dispatched job '%s' to worker '%s' over WebSocket", job.job_id, worker.worker_id)
        else:
            logger.info(
                "Job '%s' scheduled for worker '%s' (available for worker polling / connect)",
                job.job_id,
                worker.worker_id,
            )

        return True

    @staticmethod
    async def dispatch_pending_queued_jobs(db: AsyncSession) -> int:
        """Scan and attempt to schedule oldest pending QUEUED jobs."""
        stmt = (
            select(Job)
            .where(Job.status == JobState.QUEUED.value)
            .order_by(Job.created_at.asc())
            .limit(10)
        )
        queued_jobs = (await db.execute(stmt)).scalars().all()
        dispatched_count = 0

        for job in queued_jobs:
            success = await DispatcherService.try_dispatch_job(db, job)
            if success:
                dispatched_count += 1

        return dispatched_count

    @staticmethod
    async def process_job_ack(
        db: AsyncSession,
        worker_id: str,
        job_id: str,
        accepted: bool,
        rejection_reason: Optional[str] = None,
    ) -> None:
        """Process worker acknowledgement of job receipt."""
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            logger.warning("Ack received for unknown job '%s'", job_id)
            return

        now = datetime.now(timezone.utc)
        if accepted:
            logger.info("Worker '%s' acknowledged acceptance of job '%s'", worker_id, job_id)
            event = JobEvent(
                job_id=job.job_id,
                event_type="ACKNOWLEDGED",
                details={"worker_id": worker_id},
                created_at=now,
            )
            db.add(event)
            await db.commit()
        else:
            logger.warning(
                "Worker '%s' REJECTED job '%s': %s. Re-queueing job.",
                worker_id,
                job_id,
                rejection_reason,
            )
            # Re-queue job
            job.status = JobState.QUEUED.value
            job.assigned_worker_id = None
            job.placement_reason = {
                "decision": "rejected_by_worker",
                "worker_id": worker_id,
                "reason": rejection_reason or "Worker rejected job without specific reason",
                "rejected_at": now.isoformat(),
            }
            # Release capacity on rejecting worker
            await scheduler_engine.release_capacity(db, worker_id)

            event = JobEvent(
                job_id=job.job_id,
                event_type="QUEUED",
                details={"reason": f"Worker rejected job: {rejection_reason}"},
                created_at=now,
            )
            db.add(event)
            await db.commit()
            await ws_manager.broadcast("job.requeued", {"job_id": job.job_id})

    @staticmethod
    async def process_job_started(
        db: AsyncSession,
        worker_id: str,
        job_id: str,
    ) -> None:
        """Process worker execution-start confirmation."""
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            logger.warning("Start signal received for unknown job '%s'", job_id)
            return

        if job.status == JobState.RUNNING.value:
            # Idempotent
            return

        now = datetime.now(timezone.utc)
        job.status = JobState.RUNNING.value
        job.started_at = now
        job.assigned_worker_id = worker_id

        event = JobEvent(
            job_id=job.job_id,
            event_type="RUNNING",
            details={"worker_id": worker_id},
            created_at=now,
        )
        db.add(event)
        await db.commit()

        logger.info("Job '%s' execution started on worker '%s'", job_id, worker_id)
        await ws_manager.broadcast(
            "job.started",
            {
                "job_id": job.job_id,
                "worker_id": worker_id,
                "status": job.status,
            },
        )

    @staticmethod
    async def process_job_result(
        db: AsyncSession,
        worker_id: str,
        job_id: str,
        exit_code: int,
        output: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> None:
        """Process and persist final workload execution result and release capacity."""
        stmt = select(Job).where(Job.job_id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            logger.warning("Result received for unknown job '%s'", job_id)
            return

        if job.assigned_worker_id and job.assigned_worker_id != worker_id:
            logger.warning(
                "Result rejected: Worker '%s' attempted to submit result for job '%s' assigned to '%s'",
                worker_id,
                job_id,
                job.assigned_worker_id,
            )
            return

        if job.status in (JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value):
            logger.info("Job '%s' is already in terminal state '%s'. Result ignored idempotently.", job_id, job.status)
            return

        now = datetime.now(timezone.utc)
        job.completed_at = now
        job.result_duration_seconds = max(0.0, float(duration_seconds))

        if exit_code == 0:
            job.status = JobState.COMPLETED.value
            job.result_exit_code = 0
            job.result_output = output
            event_type = "COMPLETED"
            broadcast_event = "job.completed"
            logger.info("Job '%s' completed successfully on worker '%s' in %.2fs", job_id, worker_id, duration_seconds)
        else:
            job.status = JobState.FAILED.value
            job.result_exit_code = exit_code
            job.result_error = error or output or "Workload execution reported non-zero exit code"
            event_type = "FAILED"
            broadcast_event = "job.failed"
            logger.warning("Job '%s' failed on worker '%s' with exit code %d: %s", job_id, worker_id, exit_code, job.result_error)

        # Release capacity
        await scheduler_engine.release_capacity(db, worker_id)

        event = JobEvent(
            job_id=job.job_id,
            event_type=event_type,
            details={
                "exit_code": exit_code,
                "worker_id": worker_id,
                "duration_seconds": duration_seconds,
            },
            created_at=now,
        )
        db.add(event)
        await db.commit()

        await ws_manager.broadcast(
            broadcast_event,
            {
                "job_id": job.job_id,
                "worker_id": worker_id,
                "status": job.status,
                "exit_code": exit_code,
            },
        )

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.config import settings
from coordinator.models.worker import Worker
from coordinator.models.job import Job
from coordinator.models.job_event import JobEvent
from coordinator.schemas.job import JobState
from coordinator.scheduler.config import SchedulerWeights, default_weights
from coordinator.scheduler.evaluator import evaluate_worker_eligibility
from coordinator.scheduler.scoring import score_worker
from coordinator.ws.manager import ws_manager

logger = logging.getLogger("coordinator.scheduler")


class SchedulingDecision:
    """Structured, explainable scheduling outcome with metric breakdown."""

    def __init__(
        self,
        worker_id: str,
        worker_display_name: str,
        score: float,
        score_breakdown: Dict[str, Any],
        evaluated_workers_count: int,
        eligible_workers_count: int,
        rejections: Dict[str, str],
    ):
        self.worker_id = worker_id
        self.worker_display_name = worker_display_name
        self.score = score
        self.score_breakdown = score_breakdown
        self.evaluated_workers_count = evaluated_workers_count
        self.eligible_workers_count = eligible_workers_count
        self.rejections = rejections
        self.decision_timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_display_name": self.worker_display_name,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "evaluated_workers_count": self.evaluated_workers_count,
            "eligible_workers_count": self.eligible_workers_count,
            "rejections": self.rejections,
            "decision_timestamp": self.decision_timestamp,
        }


class SchedulerEngine:
    """Core adaptive scheduler engine evaluating, ranking, and assigning distributed jobs."""

    def __init__(self, weights: Optional[SchedulerWeights] = None):
        self.weights = weights or default_weights

    async def evaluate_and_select_worker(
        self,
        db: AsyncSession,
        job: Job,
        heartbeat_timeout_seconds: Optional[float] = None,
    ) -> Tuple[Optional[Worker], Optional[SchedulingDecision], Dict[str, str]]:
        """Evaluate all candidate workers against job requirements and select best candidate.
        
        Returns:
            (best_worker, scheduling_decision, rejections_map)
        """
        hb_timeout = heartbeat_timeout_seconds or float(settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS)

        # 1. Fetch all non-revoked workers
        stmt = select(Worker).where(Worker.is_revoked == False)
        all_workers = (await db.execute(stmt)).scalars().all()

        evaluated_count = len(all_workers)
        rejections: Dict[str, str] = {}
        eligible_candidates: List[Tuple[Worker, float, Dict[str, Any]]] = []

        logger.info(
            "Evaluating %d worker(s) for job '%s' (type: %s, reqs: %s)",
            evaluated_count,
            job.job_id,
            job.job_type,
            job.requirements,
        )

        # 2. Capability matching loop
        for worker in all_workers:
            eligible, reason = evaluate_worker_eligibility(
                worker=worker,
                job=job,
                heartbeat_timeout_seconds=hb_timeout,
            )
            if not eligible:
                rejections[worker.worker_id] = reason or "Unknown constraint violation"
                logger.debug(
                    "Worker '%s' rejected for job '%s': %s",
                    worker.worker_id,
                    job.job_id,
                    reason,
                )
            else:
                score, breakdown = score_worker(worker=worker, weights=self.weights)
                eligible_candidates.append((worker, score, breakdown))

        eligible_count = len(eligible_candidates)
        if not eligible_candidates:
            logger.warning(
                "No eligible workers found for job '%s'. Total evaluated: %d. Rejections: %s",
                job.job_id,
                evaluated_count,
                rejections,
            )
            return None, None, rejections

        # 3. Rank eligible candidates (lower score is better; tiebreak by active jobs then available RAM)
        eligible_candidates.sort(
            key=lambda item: (
                item[1],  # total_score ascending
                item[0].active_job_count,  # fewer active jobs
                -item[0].available_ram_bytes,  # more available RAM
            )
        )

        best_worker, best_score, best_breakdown = eligible_candidates[0]

        decision = SchedulingDecision(
            worker_id=best_worker.worker_id,
            worker_display_name=best_worker.display_name,
            score=best_score,
            score_breakdown=best_breakdown,
            evaluated_workers_count=evaluated_count,
            eligible_workers_count=eligible_count,
            rejections=rejections,
        )

        logger.info(
            "Selected worker '%s' (score: %.4f) for job '%s' out of %d eligible candidates",
            best_worker.worker_id,
            best_score,
            job.job_id,
            eligible_count,
        )

        return best_worker, decision, rejections

    async def assign_and_reserve(
        self,
        db: AsyncSession,
        job: Job,
        worker: Worker,
        decision: SchedulingDecision,
    ) -> None:
        """Atomically reserve worker capacity and transition job to SCHEDULED."""
        now = datetime.now(timezone.utc)

        # Check concurrency limit before reservation
        max_jobs = getattr(worker, "max_concurrent_jobs", 2)
        if worker.active_job_count >= max_jobs:
            raise ValueError(
                f"Cannot reserve capacity on worker '{worker.worker_id}': limit reached ({worker.active_job_count}/{max_jobs})"
            )

        # Reserve capacity
        worker.active_job_count += 1
        if worker.active_job_count >= max_jobs:
            worker.connection_status = "busy"

        # Update job
        job.status = JobState.SCHEDULED.value
        job.assigned_worker_id = worker.worker_id
        job.placement_reason = decision.to_dict()

        # Log audit event
        event = JobEvent(
            job_id=job.job_id,
            event_type="SCHEDULED",
            details=decision.to_dict(),
            created_at=now,
        )
        db.add(event)

        await db.commit()
        await db.refresh(job)
        await db.refresh(worker)

        # Broadcast update
        await ws_manager.broadcast(
            "job.scheduled",
            {
                "job_id": job.job_id,
                "assigned_worker_id": worker.worker_id,
                "score": decision.score,
                "status": job.status,
            },
        )

    async def release_capacity(self, db: AsyncSession, worker_id: str) -> None:
        """Release one active job slot from the specified worker node."""
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        worker = (await db.execute(stmt)).scalar_one_or_none()
        if worker:
            worker.active_job_count = max(0, worker.active_job_count - 1)
            max_jobs = getattr(worker, "max_concurrent_jobs", 2)
            if worker.active_job_count < max_jobs and worker.connection_status == "busy":
                worker.connection_status = "online"
            await db.commit()
            logger.debug(
                "Released capacity on worker '%s'. Active jobs remaining: %d",
                worker_id,
                worker.active_job_count,
            )

    async def handle_worker_disconnect_cleanup(
        self, db: AsyncSession, worker_id: str
    ) -> List[str]:
        """Safely clean up jobs assigned to a disconnected worker.
        
        - SCHEDULED jobs: worker never started; re-queue to QUEUED and unassign.
        - RUNNING jobs: failed mid-execution; mark FAILED and log error.
        """
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(
            Job.assigned_worker_id == worker_id,
            Job.status.in_([JobState.SCHEDULED.value, JobState.RUNNING.value]),
        )
        affected_jobs = (await db.execute(stmt)).scalars().all()
        recovered_ids: List[str] = []

        for j in affected_jobs:
            recovered_ids.append(j.job_id)
            if j.status == JobState.SCHEDULED.value:
                # Re-queue safely
                j.status = JobState.QUEUED.value
                j.assigned_worker_id = None
                event = JobEvent(
                    job_id=j.job_id,
                    event_type="QUEUED",
                    details={"reason": f"Re-queued: assigned worker '{worker_id}' disconnected before execution start"},
                    created_at=now,
                )
                db.add(event)
                await ws_manager.broadcast("job.requeued", {"job_id": j.job_id})
            elif j.status == JobState.RUNNING.value:
                # Fail explicitly
                j.status = JobState.FAILED.value
                j.completed_at = now
                j.result_exit_code = -1
                j.result_error = f"Worker '{worker_id}' disconnected during execution"
                j.placement_reason = {"status": "failed", "reason": j.result_error}
                event = JobEvent(
                    job_id=j.job_id,
                    event_type="FAILED",
                    details={"reason": j.result_error},
                    created_at=now,
                )
                db.add(event)
                await ws_manager.broadcast("job.failed", {"job_id": j.job_id, "error": j.result_error})

        # Reset worker active job count
        stmt_w = select(Worker).where(Worker.worker_id == worker_id)
        w = (await db.execute(stmt_w)).scalar_one_or_none()
        if w:
            w.active_job_count = 0
            w.connection_status = "disconnected"

        await db.commit()
        return recovered_ids


# Global scheduler engine singleton
scheduler_engine = SchedulerEngine()

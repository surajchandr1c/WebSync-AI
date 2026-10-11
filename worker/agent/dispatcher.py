import asyncio
import logging
from typing import Dict, Any, List, Optional
from worker.agent.transport import CoordinatorTransport
from worker.agent.executor import ModularJobExecutor, WorkloadExecutionResult

logger = logging.getLogger("websync-worker.dispatcher")


class WorkerDispatcher:
    """Manages job reception, validation, acknowledgement, execution, and result delivery."""

    def __init__(
        self,
        transport: CoordinatorTransport,
        executor: ModularJobExecutor,
        worker_id: str,
        worker_jwt: str,
        supported_workloads: List[str],
        poll_interval_seconds: float = 1.0,
    ):
        self.transport = transport
        self.executor = executor
        self.worker_id = worker_id
        self.worker_jwt = worker_jwt
        self.supported_workloads = supported_workloads
        self.poll_interval_seconds = poll_interval_seconds
        self._running = False
        self._processing_jobs: set[str] = set()
        self._lock = asyncio.Lock()

    async def handle_job_envelope(self, envelope: Dict[str, Any]) -> None:
        """Handle a received job envelope from coordinator (via WebSocket or polling)."""
        job_id = envelope.get("job_id")
        job_type = envelope.get("job_type")
        input_payload = envelope.get("input_payload", {})
        timeout_seconds = int(envelope.get("timeout_seconds", 300))

        if not job_id or not job_type:
            logger.warning("Received invalid job envelope: missing job_id or job_type")
            return

        async with self._lock:
            if job_id in self._processing_jobs:
                logger.debug("Job '%s' already in processing, ignoring duplicate.", job_id)
                return
            self._processing_jobs.add(job_id)

        try:
            # 1. Verify workload type compatibility
            if job_type not in self.supported_workloads:
                reason = f"Workload '{job_type}' not supported on this node (supported: {self.supported_workloads})"
                logger.warning("Rejecting job '%s': %s", job_id, reason)
                await self.transport.ack_job(
                    worker_id=self.worker_id,
                    job_id=job_id,
                    accepted=False,
                    rejection_reason=reason,
                    worker_jwt=self.worker_jwt,
                )
                return

            # 2. Verify local concurrency limit
            active_count = self.executor.get_active_jobs_count()
            if active_count >= self.executor.max_concurrent_jobs:
                reason = f"Local concurrency limit reached ({active_count}/{self.executor.max_concurrent_jobs})"
                logger.warning("Rejecting job '%s': %s", job_id, reason)
                await self.transport.ack_job(
                    worker_id=self.worker_id,
                    job_id=job_id,
                    accepted=False,
                    rejection_reason=reason,
                    worker_jwt=self.worker_jwt,
                )
                return

            # 3. Acknowledge acceptance
            logger.info("Accepting job '%s' (type: %s)", job_id, job_type)
            await self.transport.ack_job(
                worker_id=self.worker_id,
                job_id=job_id,
                accepted=True,
                rejection_reason=None,
                worker_jwt=self.worker_jwt,
            )

            # 4. Notify execution start
            await self.transport.report_job_started(
                worker_id=self.worker_id,
                job_id=job_id,
                worker_jwt=self.worker_jwt,
            )

            # 5. Execute job via modular executor
            logger.info("Executing job '%s' with timeout %ds...", job_id, timeout_seconds)
            result = await self.executor.execute_job(
                job_id=job_id,
                job_type=job_type,
                input_payload=input_payload,
                timeout_seconds=timeout_seconds,
            )

            # 6. Report final execution outcome
            logger.info(
                "Job '%s' finished: exit_code=%d in %.4fs (error=%s)",
                job_id,
                result.exit_code,
                result.duration_seconds,
                result.error,
            )
            await self.transport.report_job_result(
                worker_id=self.worker_id,
                job_id=job_id,
                exit_code=result.exit_code,
                output=result.output,
                duration_seconds=result.duration_seconds,
                error=result.error,
                worker_jwt=self.worker_jwt,
            )

        finally:
            async with self._lock:
                self._processing_jobs.discard(job_id)

    async def poll_and_process_pending(self) -> int:
        """Poll coordinator for pending jobs and dispatch execution tasks."""
        pending_jobs = await self.transport.poll_pending_jobs(
            worker_id=self.worker_id,
            worker_jwt=self.worker_jwt,
        )
        if not pending_jobs:
            return 0

        logger.info("Found %d pending job(s) for worker '%s'", len(pending_jobs), self.worker_id)
        for envelope in pending_jobs:
            # Spawn each job in background task
            asyncio.create_task(self.handle_job_envelope(envelope))

        return len(pending_jobs)

    async def run(self) -> None:
        """Continuously poll for and execute jobs until stopped."""
        self._running = True
        logger.info(
            "WorkerDispatcher started for worker '%s' (poll interval: %.1fs)",
            self.worker_id,
            self.poll_interval_seconds,
        )
        while self._running:
            try:
                await self.poll_and_process_pending()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in job dispatch loop: %s", str(e))

            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break

        logger.info("WorkerDispatcher stopped for worker '%s'.", self.worker_id)

    def stop(self) -> None:
        self._running = False

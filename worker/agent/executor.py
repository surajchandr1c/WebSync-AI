import asyncio
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("websync-worker.executor")


class WorkloadExecutionResult:
    """Outcome and telemetry of a completed workload execution."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        exit_code: int,
        output: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.exit_code = exit_code
        self.output = output
        self.duration_seconds = duration_seconds
        self.error = error
        self.success = (exit_code == 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "exit_code": self.exit_code,
            "output": self.output,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "success": self.success,
        }


class ModularJobExecutor:
    """Safe, modular workload executor enforcing strict handler isolation without eval."""

    def __init__(self, max_concurrent_jobs: int = 2):
        self.max_concurrent_jobs = max_concurrent_jobs
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def get_active_jobs_count(self) -> int:
        return len(self._active_jobs)

    async def execute_job(
        self,
        job_id: str,
        job_type: str,
        input_payload: Dict[str, Any],
        timeout_seconds: int = 300,
    ) -> WorkloadExecutionResult:
        """Execute validated workload adhering strictly to safe registered handlers."""
        if len(self._active_jobs) >= self.max_concurrent_jobs:
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=0.0,
                error=f"Node concurrency limit reached (max: {self.max_concurrent_jobs})",
            )

        start_time = time.perf_counter()
        task = asyncio.current_task()
        if task:
            async with self._lock:
                self._active_jobs[job_id] = task

        try:
            handler = self._resolve_handler(job_type)
            output = await asyncio.wait_for(
                handler(input_payload),
                timeout=timeout_seconds,
            )
            elapsed = time.perf_counter() - start_time
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=0,
                output=output,
                duration_seconds=round(elapsed, 4),
            )

        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start_time
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=round(elapsed, 4),
                error=f"Job timed out after {timeout_seconds}s",
            )

        except asyncio.CancelledError:
            elapsed = time.perf_counter() - start_time
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=round(elapsed, 4),
                error="Job execution cancelled by operator",
            )

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error("Job %s execution failed: %s", job_id, str(e))
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=1,
                output="",
                duration_seconds=round(elapsed, 4),
                error=str(e),
            )

        finally:
            async with self._lock:
                self._active_jobs.pop(job_id, None)

    def _resolve_handler(self, job_type: str):
        """Map approved workload type to safe execution function."""
        handlers = {
            "matrix_multiply": self._run_matrix_multiply,
            "data_processing": self._run_data_processing,
            "image_processing": self._run_image_processing,
        }
        if job_type not in handlers:
            raise ValueError(
                f"Unsupported workload '{job_type}'. Approved types: {list(handlers.keys())}"
            )
        return handlers[job_type]

    # --- Safe Pure Handlers ---

    @staticmethod
    async def _run_matrix_multiply(payload: Dict[str, Any]) -> str:
        """Execute linear algebra matrix multiplication benchmark."""
        # Yield to event loop
        await asyncio.sleep(0.01)

        dim = payload.get("dimension", 100)
        if not isinstance(dim, int) or dim <= 0 or dim > 500:
            dim = 100

        # Construct deterministic sample matrices
        a = [[(i + j) % 10 for j in range(dim)] for i in range(dim)]
        b = [[(i * j) % 10 for j in range(dim)] for i in range(dim)]

        # Multiply
        c = [[0] * dim for _ in range(dim)]
        for i in range(dim):
            for k in range(dim):
                for j in range(dim):
                    c[i][j] += a[i][k] * b[k][j]

        # Return summary
        checksum = sum(c[i][i] for i in range(dim))
        return f"Successfully multiplied {dim}x{dim} matrices. Trace checksum: {checksum}"

    @staticmethod
    async def _run_data_processing(payload: Dict[str, Any]) -> str:
        """Execute deterministic data transformation & aggregation."""
        await asyncio.sleep(0.01)

        records = payload.get("records", [])
        if not isinstance(records, list) or not records:
            # Fallback to generated items
            records = [{"id": i, "val": i * 1.5, "tag": f"group-{i % 5}"} for i in range(1000)]

        total_sum = sum(r.get("val", 0) for r in records if isinstance(r, dict))
        count = len(records)
        return f"Processed {count} records. Aggregated sum: {total_sum:.2f}"

    @staticmethod
    async def _run_image_processing(payload: Dict[str, Any]) -> str:
        """Execute image transform if Pillow is installed."""
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("PIL/Pillow library is not installed for image_processing.")

        width = payload.get("width", 256)
        height = payload.get("height", 256)
        img = Image.new("RGB", (width, height), color=(73, 109, 137))
        return f"Generated image buffer of dimensions {width}x{height} pixels ({img.mode})"

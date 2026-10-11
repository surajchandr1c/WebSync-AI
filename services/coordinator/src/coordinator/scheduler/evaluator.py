from datetime import datetime, timezone
import math
from typing import Tuple, Optional
from coordinator.models.worker import Worker
from coordinator.models.job import Job


def evaluate_worker_eligibility(
    worker: Worker,
    job: Job,
    heartbeat_timeout_seconds: float = 30.0,
) -> Tuple[bool, Optional[str]]:
    """Determine whether a candidate worker satisfies all functional and resource constraints.
    
    Returns:
        (True, None) if the worker is eligible.
        (False, "reason string") if the worker fails any eligibility criterion.
    """
    # 1. Revocation & administrative exclusion
    if worker.is_revoked:
        return False, "Worker is revoked or administratively disabled"

    # 2. Connection status check
    if worker.connection_status not in ("online", "busy"):
        return False, f"Worker connection status is '{worker.connection_status}' (expected online/busy)"

    # 3. Heartbeat freshness
    if not worker.last_heartbeat:
        return False, "Worker has never sent a heartbeat"

    now = datetime.now(timezone.utc)
    last_hb = worker.last_heartbeat
    if last_hb.tzinfo is None:
        last_hb = last_hb.replace(tzinfo=timezone.utc)
    elapsed = (now - last_hb).total_seconds()
    if elapsed > heartbeat_timeout_seconds:
        return False, f"Worker heartbeat is stale ({elapsed:.1f}s ago > {heartbeat_timeout_seconds:.1f}s threshold)"

    # 4. Telemetry data sanity checks (prevent NaN or distorted metrics)
    if (
        math.isnan(worker.cpu_utilization)
        or math.isinf(worker.cpu_utilization)
        or worker.cpu_utilization < 0.0
        or worker.cpu_utilization > 100.0
    ):
        return False, f"Worker reported invalid CPU metric: {worker.cpu_utilization}"

    if worker.total_ram_bytes <= 0:
        return False, f"Worker reported invalid total RAM: {worker.total_ram_bytes} bytes"

    if worker.available_ram_bytes < 0 or worker.available_ram_bytes > worker.total_ram_bytes:
        return False, f"Worker reported invalid available RAM: {worker.available_ram_bytes} bytes (total: {worker.total_ram_bytes})"

    # 5. Workload type support
    supported = worker.supported_workloads or []
    if job.job_type not in supported:
        return False, f"Workload '{job.job_type}' not in worker supported workloads: {supported}"

    # 6. Memory requirement matching
    reqs = job.requirements or {}
    if "min_ram_bytes" in reqs and reqs["min_ram_bytes"] is not None:
        required_ram = int(reqs["min_ram_bytes"])
    elif "min_ram_mb" in reqs and reqs["min_ram_mb"] is not None:
        required_ram = int(reqs["min_ram_mb"]) * 1024 * 1024
    else:
        required_ram = 0

    if worker.available_ram_bytes < required_ram:
        avail_mb = worker.available_ram_bytes / (1024 * 1024)
        req_mb = required_ram / (1024 * 1024)
        return (
            False,
            f"Insufficient available RAM: {avail_mb:.1f} MB available < {req_mb:.1f} MB required",
        )

    # 7. GPU requirement matching
    gpu_required = bool(reqs.get("gpu_required", False))
    if gpu_required:
        if not worker.gpu_available:
            return False, "Workload requires GPU but worker has no GPU detected"
        if not worker.gpu_metadata:
            return False, "Workload requires GPU but worker reported no valid GPU devices"

    # 8. Concurrency capacity check
    max_jobs = getattr(worker, "max_concurrent_jobs", 2)
    if worker.active_job_count >= max_jobs:
        return (
            False,
            f"Worker at concurrency limit: {worker.active_job_count}/{max_jobs} active jobs",
        )

    return True, None

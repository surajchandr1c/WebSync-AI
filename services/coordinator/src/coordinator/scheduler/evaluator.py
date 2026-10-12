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

    # 2. Target worker constraint
    reqs = job.requirements or {}
    payload = job.input_payload or {}
    target_worker_id = reqs.get("target_worker_id") or payload.get("target_worker_id")
    if target_worker_id and worker.worker_id != target_worker_id:
        return False, f"Job targeted worker '{target_worker_id}', but candidate worker is '{worker.worker_id}'"

    # 3. Connection status check
    if worker.connection_status not in ("online", "busy"):
        return False, f"Worker connection status is '{worker.connection_status}' (expected online/busy)"

    # 4. Heartbeat freshness
    if not worker.last_heartbeat:
        return False, "Worker has never sent a heartbeat"

    now = datetime.now(timezone.utc)
    last_hb = worker.last_heartbeat
    if last_hb.tzinfo is None:
        last_hb = last_hb.replace(tzinfo=timezone.utc)
    elapsed = (now - last_hb).total_seconds()
    if elapsed > heartbeat_timeout_seconds:
        return False, f"Worker heartbeat is stale ({elapsed:.1f}s ago > {heartbeat_timeout_seconds:.1f}s threshold)"

    # 5. Telemetry data sanity checks (prevent NaN or distorted metrics)
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

    # 6. Workload type support
    supported = worker.supported_workloads or []
    if job.job_type not in supported:
        return False, f"Workload '{job.job_type}' not in worker supported workloads: {supported}"

    # 7. LLM prompt model matching
    if job.job_type == "llm_prompt":
        req_model = reqs.get("model") or payload.get("model")
        if req_model:
            worker_models = worker.supported_models or []
            model_match = any(
                req_model == m or req_model == m.split(":")[0] or m == req_model.split(":")[0]
                for m in worker_models
            )
            if not model_match:
                return (
                    False,
                    f"Requested model '{req_model}' not available on worker (available: {worker_models})",
                )

    # 8. Memory requirement matching
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

    # 9. GPU requirement matching
    gpu_required = bool(reqs.get("gpu_required", False))
    if gpu_required:
        if not worker.gpu_available:
            return False, "Workload requires GPU but worker has no GPU detected"
        if not worker.gpu_metadata:
            return False, "Workload requires GPU but worker reported no valid GPU devices"

    # 10. Concurrency capacity check
    active_jobs = getattr(worker, "active_job_count", 0)
    if active_jobs is None:
        active_jobs = 0
    max_jobs = getattr(worker, "max_concurrent_jobs", 2)
    if max_jobs is None:
        max_jobs = 2
    if active_jobs >= max_jobs:
        return (
            False,
            f"Worker at concurrency limit: {active_jobs}/{max_jobs} active jobs",
        )

    return True, None

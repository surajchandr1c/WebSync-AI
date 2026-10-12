from datetime import datetime, timezone
import math
from typing import Tuple, Optional
from coordinator.models.worker import Worker
from coordinator.models.job import Job


def normalize_model_name(name: str) -> str:
    """Normalize model identifier into canonical form (lowercase, stripped, :latest default tag)."""
    if not name or not isinstance(name, str):
        return ""
    cleaned = name.strip().lower()
    if not cleaned:
        return ""
    if ":" not in cleaned:
        return f"{cleaned}:latest"
    return cleaned


def model_matches(requested: str, installed: str) -> bool:
    """Return True if installed model matches requested model tag.

    - If requested has no tag (e.g. 'llama3.2'), it matches 'llama3.2', 'llama3.2:latest', or any model whose canonical name is 'llama3.2:latest'.
    - If requested has an explicit tag (e.g. 'llama3.2:3b'), it must strictly match 'llama3.2:3b'.
    - Tag 'llama3.2:3b' will NEVER match 'llama3.2:1b'.
    """
    if not requested or not installed:
        return False
    req = requested.strip().lower()
    inst = installed.strip().lower()

    if req == inst:
        return True

    # If requested has no tag, check canonical :latest match
    if ":" not in req:
        return inst == f"{req}:latest" or inst == req

    # If requested has an explicit tag (e.g. "llama3.2:3b" or "llama3.2:latest")
    inst_canonical = inst if ":" in inst else f"{inst}:latest"
    return req == inst_canonical


def evaluate_worker_eligibility(
    worker: Worker,
    job: Job,
    heartbeat_timeout_seconds: float = 30.0,
    reserved_ram_bytes: int = 0,
    reserved_cpu_cores: int = 0,
) -> Tuple[bool, Optional[str]]:
    """Determine whether a candidate worker satisfies all functional and resource constraints.
    
    Takes into account in-flight resource reservations (RAM and CPU cores) so concurrent jobs
    cannot collectively exceed physical worker limits.
    
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

    # Check host CPU threshold limit
    max_cpu_allowed = getattr(worker, "configured_max_cpu_percent", 95.0) or 95.0
    if worker.cpu_utilization >= max_cpu_allowed:
        return (
            False,
            f"Worker CPU utilization ({worker.cpu_utilization:.1f}%) exceeds configured limit ({max_cpu_allowed:.1f}%)",
        )

    if worker.total_ram_bytes <= 0:
        return False, f"Worker reported invalid total RAM: {worker.total_ram_bytes} bytes"

    if worker.available_ram_bytes < 0 or worker.available_ram_bytes > worker.total_ram_bytes:
        return False, f"Worker reported invalid available RAM: {worker.available_ram_bytes} bytes (total: {worker.total_ram_bytes})"

    # 6. Workload type support
    supported = worker.supported_workloads or []
    effective_workload = job.job_type
    if effective_workload == "distributed_data_processing":
        effective_workload = "data_processing"

    if effective_workload not in supported:
        return False, f"Workload '{effective_workload}' not in worker supported workloads: {supported}"

    # 7. LLM prompt model matching
    if job.job_type == "llm_prompt":
        req_model = reqs.get("model") or payload.get("model")
        if req_model:
            # Check Ollama service status on worker
            ollama_status = getattr(worker, "ollama_status", "not_installed") or "not_installed"
            if ollama_status in ("stopped", "not_installed", "unreachable"):
                return (
                    False,
                    f"Ollama service is {ollama_status.upper()} on worker node '{worker.worker_id}'",
                )

            worker_models = worker.supported_models or []
            if not any(model_matches(req_model, m) for m in worker_models):
                return (
                    False,
                    f"Requested model '{req_model}' is not installed in local Ollama on worker '{worker.worker_id}' "
                    f"(installed: {worker_models or 'none'}). To install it, run 'ollama pull {req_model}' on the node or use the 'Install Model' action.",
                )

    # 8. Memory requirement matching with reservation tracking & safety buffer
    if "min_ram_bytes" in reqs and reqs["min_ram_bytes"] is not None:
        required_ram = int(reqs["min_ram_bytes"])
    elif "min_ram_mb" in reqs and reqs["min_ram_mb"] is not None:
        required_ram = int(reqs["min_ram_mb"]) * 1024 * 1024
    else:
        required_ram = 0

    safety_buffer_bytes = int(getattr(worker, "configured_min_available_ram_mb", 512) or 512) * 1024 * 1024
    unreserved_ram = max(0, worker.available_ram_bytes - reserved_ram_bytes)
    allocatable_ram = max(0, unreserved_ram - safety_buffer_bytes)

    if allocatable_ram < required_ram:
        alloc_mb = allocatable_ram / (1024 * 1024)
        req_mb = required_ram / (1024 * 1024)
        res_mb = reserved_ram_bytes / (1024 * 1024)
        return (
            False,
            f"Insufficient unreserved allocatable RAM: {alloc_mb:.1f} MB allocatable (in-flight reserved: {res_mb:.1f} MB) < {req_mb:.1f} MB required",
        )

    # 9. CPU core requirement matching
    required_cores = int(reqs.get("min_cpu_cores", 1))
    worker_logical_cores = getattr(worker, "cpu_count_logical", 1) or 1
    unreserved_cores = max(0, worker_logical_cores - reserved_cpu_cores)
    if unreserved_cores < required_cores:
        return (
            False,
            f"Insufficient CPU cores: {unreserved_cores} unreserved cores ({worker_logical_cores} total, {reserved_cpu_cores} in-flight) < {required_cores} required",
        )

    # 10. GPU requirement matching
    gpu_required = bool(reqs.get("gpu_required", False))
    if gpu_required:
        if not worker.gpu_available:
            return False, "Workload requires GPU but worker has no GPU detected"
        if not worker.gpu_metadata:
            return False, "Workload requires GPU but worker reported no valid GPU devices"

    # 11. Concurrency capacity check
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

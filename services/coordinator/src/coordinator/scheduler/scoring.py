import math
from typing import Dict, Optional, Tuple
from coordinator.models.worker import Worker
from coordinator.scheduler.config import SchedulerWeights, default_weights


def score_worker(
    worker: Worker,
    weights: Optional[SchedulerWeights] = None,
    latency_ms: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Calculate normalized placement score for an eligible worker.
    
    A lower score represents a more suitable worker (lower CPU, higher available RAM,
    lower active job load, lower latency).
    
    Returns:
        (total_score, score_breakdown)
    """
    w = weights or default_weights

    # Sanity verification: ensure metrics are finite
    cpu_pct = float(worker.cpu_utilization)
    if math.isnan(cpu_pct) or math.isinf(cpu_pct):
        cpu_pct = 100.0
    cpu_pct = max(0.0, min(100.0, cpu_pct))

    tot_ram = max(1, int(worker.total_ram_bytes))
    avail_ram = max(0, min(tot_ram, int(worker.available_ram_bytes)))
    active_jobs = max(0, int(worker.active_job_count))
    max_jobs = max(1, getattr(worker, "max_concurrent_jobs", 2))

    # Normalized sub-scores [0.0, 1.0]
    s_cpu = cpu_pct / 100.0
    s_ram = 1.0 - (avail_ram / tot_ram)  # Higher RAM pressure = higher penalty
    s_load = min(1.0, active_jobs / max_jobs)

    # Latency sub-score: if not measured, use 0.0 without inventing fake numbers
    if latency_ms is not None and latency_ms >= 0:
        s_lat = min(1.0, latency_ms / 200.0)  # Normalized against 200ms baseline
    else:
        s_lat = 0.0

    total_score = (
        (w.w_cpu * s_cpu)
        + (w.w_ram * s_ram)
        + (w.w_load * s_load)
        + (w.w_lat * s_lat)
    )

    breakdown = {
        "cpu_score": round(s_cpu, 4),
        "ram_score": round(s_ram, 4),
        "load_score": round(s_load, 4),
        "latency_score": round(s_lat, 4),
        "cpu_pct": round(cpu_pct, 1),
        "available_ram_mb": round(avail_ram / (1024 * 1024), 1),
        "active_jobs": active_jobs,
        "max_concurrent_jobs": max_jobs,
    }

    return round(total_score, 4), breakdown

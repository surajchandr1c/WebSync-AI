from datetime import datetime, timezone, timedelta
import math
import pytest
from coordinator.models.worker import Worker
from coordinator.models.job import Job
from coordinator.scheduler.config import SchedulerWeights
from coordinator.scheduler.evaluator import evaluate_worker_eligibility
from coordinator.scheduler.scoring import score_worker
from coordinator.scheduler.engine import scheduler_engine


def make_test_worker(
    worker_id="test-worker",
    status="online",
    cpu_util=25.0,
    total_ram=16 * 1024 * 1024 * 1024,
    avail_ram=8 * 1024 * 1024 * 1024,
    workloads=None,
    gpu_avail=False,
    gpu_meta=None,
    active_jobs=0,
    max_jobs=2,
    heartbeat_age_sec=5.0,
    is_revoked=False,
) -> Worker:
    now = datetime.now(timezone.utc)
    return Worker(
        worker_id=worker_id,
        display_name=f"Worker {worker_id}",
        hostname="box",
        platform="Linux",
        platform_version="6.1",
        cpu_utilization=cpu_util,
        total_ram_bytes=total_ram,
        available_ram_bytes=avail_ram,
        supported_workloads=workloads or ["matrix_multiply", "data_processing"],
        gpu_available=gpu_avail,
        gpu_metadata=gpu_meta or ([] if not gpu_avail else [{"name": "RTX 3050", "memory_total_bytes": 4 * 1024**3}]),
        active_job_count=active_jobs,
        max_concurrent_jobs=max_jobs,
        connection_status=status,
        last_heartbeat=now - timedelta(seconds=heartbeat_age_sec),
        registered_at=now,
        is_revoked=is_revoked,
    )


def make_test_job(
    job_id="job-1",
    job_type="matrix_multiply",
    min_ram_bytes=None,
    min_ram_mb=512,
    gpu_required=False,
) -> Job:
    reqs = {
        "min_ram_mb": min_ram_mb,
        "gpu_required": gpu_required,
    }
    if min_ram_bytes is not None:
        reqs["min_ram_bytes"] = min_ram_bytes

    return Job(
        job_id=job_id,
        name="test-job",
        job_type=job_type,
        status="QUEUED",
        input_payload={"dimension": 50},
        requirements=reqs,
    )


# --- 1. Capability Matching Tests ---

def test_eligible_worker_passes():
    worker = make_test_worker()
    job = make_test_job()
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is True
    assert reason is None


def test_revoked_worker_rejected():
    worker = make_test_worker(is_revoked=True)
    job = make_test_job()
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is False
    assert "revoked" in reason.lower()


def test_offline_or_disconnected_worker_rejected():
    for st in ("offline", "disconnected", "registered"):
        worker = make_test_worker(status=st)
        job = make_test_job()
        eligible, reason = evaluate_worker_eligibility(worker, job)
        assert eligible is False
        assert "expected online/busy" in reason


def test_stale_heartbeat_rejected():
    worker = make_test_worker(heartbeat_age_sec=45.0)  # > 30s threshold
    job = make_test_job()
    eligible, reason = evaluate_worker_eligibility(worker, job, heartbeat_timeout_seconds=30.0)
    assert eligible is False
    assert "stale" in reason.lower()


def test_unsupported_workload_rejected():
    worker = make_test_worker(workloads=["data_processing"])
    job = make_test_job(job_type="matrix_multiply")
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is False
    assert "not in worker supported workloads" in reason


def test_insufficient_ram_rejected():
    # 4 GB available, but job requires 8 GB
    worker = make_test_worker(avail_ram=4 * 1024 * 1024 * 1024)
    job = make_test_job(min_ram_bytes=8 * 1024 * 1024 * 1024)
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is False
    assert "Insufficient" in reason and "RAM" in reason


def test_gpu_requirement_enforced():
    # GPU required but worker has no GPU
    worker = make_test_worker(gpu_avail=False)
    job = make_test_job(gpu_required=True)
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is False
    assert "requires GPU" in reason

    # Worker with GPU satisfies requirement
    worker_gpu = make_test_worker(gpu_avail=True)
    eligible_gpu, reason_gpu = evaluate_worker_eligibility(worker_gpu, job)
    assert eligible_gpu is True
    assert reason_gpu is None


def test_concurrency_limit_enforced():
    worker = make_test_worker(active_jobs=2, max_jobs=2)
    job = make_test_job()
    eligible, reason = evaluate_worker_eligibility(worker, job)
    assert eligible is False
    assert "concurrency limit" in reason.lower()


def test_invalid_telemetry_rejected():
    # Negative CPU
    bad_cpu = make_test_worker(cpu_util=-5.0)
    assert evaluate_worker_eligibility(bad_cpu, make_test_job())[0] is False

    # CPU > 100
    bad_cpu2 = make_test_worker(cpu_util=105.0)
    assert evaluate_worker_eligibility(bad_cpu2, make_test_job())[0] is False

    # Total RAM 0
    bad_ram = make_test_worker(total_ram=0)
    assert evaluate_worker_eligibility(bad_ram, make_test_job())[0] is False


# --- 2. Adaptive Scoring Tests ---

def test_scheduler_weights_validation():
    # Valid sum = 1.0
    w = SchedulerWeights(w_cpu=0.4, w_ram=0.4, w_load=0.2, w_lat=0.0)
    assert w.w_cpu == 0.4

    # Invalid sum != 1.0
    with pytest.raises(ValueError):
        SchedulerWeights(w_cpu=0.5, w_ram=0.5, w_load=0.5, w_lat=0.0)


def test_scoring_prefers_lower_utilization():
    weights = SchedulerWeights(w_cpu=0.5, w_ram=0.5, w_load=0.0, w_lat=0.0)
    
    # Idle node
    idle = make_test_worker(cpu_util=10.0, avail_ram=14 * 1024**3, total_ram=16 * 1024**3)
    score_idle, bd_idle = score_worker(idle, weights)

    # Busy node
    busy = make_test_worker(cpu_util=80.0, avail_ram=2 * 1024**3, total_ram=16 * 1024**3)
    score_busy, bd_busy = score_worker(busy, weights)

    assert score_idle < score_busy
    assert bd_idle["cpu_score"] < bd_busy["cpu_score"]
    assert bd_idle["ram_score"] < bd_busy["ram_score"]


def test_latency_scoring_fallback():
    weights = SchedulerWeights(w_cpu=0.3, w_ram=0.3, w_load=0.3, w_lat=0.1)
    worker = make_test_worker()
    
    # When latency is None, s_lat defaults to 0.0 without crash
    score, bd = score_worker(worker, weights, latency_ms=None)
    assert bd["latency_score"] == 0.0

    # When latency is 100ms, s_lat is 0.5 (100 / 200)
    score_with_lat, bd_with_lat = score_worker(worker, weights, latency_ms=100.0)
    assert bd_with_lat["latency_score"] == 0.5
    assert score_with_lat > score

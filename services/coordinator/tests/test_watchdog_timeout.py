import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from coordinator.models.job import Job
from coordinator.models.worker import Worker
from coordinator.schemas.job import JobState
from coordinator.services.job_service import JobService
from coordinator.services.dispatcher_service import DispatcherService


@pytest.mark.asyncio
async def test_job_service_deadline_timeout_enforcement(db_session):
    """Verify that jobs exceeding their timeout deadline are marked FAILED by the watchdog."""
    now = datetime.now(timezone.utc)
    # Create an expired running job (started 400 seconds ago, timeout 60s)
    expired_start = now - timedelta(seconds=400)
    job = Job(
        job_id="job-timeout-test",
        name="Timed Out LLM Prompt",
        job_type="llm_prompt",
        status=JobState.RUNNING.value,
        input_payload={"prompt": "Slow query", "model": "llama3.2:latest"},
        requirements={"timeout_seconds": 60},
        started_at=expired_start,
        created_at=expired_start,
    )
    db_session.add(job)
    await db_session.commit()

    # Run timeout sweep
    timed_out_ids = await JobService.check_and_fail_timed_out_jobs(db_session)
    assert "job-timeout-test" in timed_out_ids

    # Verify job status in DB
    refreshed = (await db_session.execute(select(Job).where(Job.job_id == "job-timeout-test"))).scalar_one()
    assert refreshed.status == JobState.FAILED.value
    assert refreshed.result_exit_code == -1
    assert "exceeded deadline timeout" in refreshed.result_error


@pytest.mark.asyncio
async def test_dispatcher_rejects_mismatched_worker_result(db_session):
    """Verify that a rogue/mismatched worker cannot submit results for another worker's job."""
    now = datetime.now(timezone.utc)
    job = Job(
        job_id="job-ownership-test",
        name="Ownership Test Job",
        job_type="matrix_multiply",
        status=JobState.RUNNING.value,
        assigned_worker_id="legitimate-worker-1",
        input_payload={"dim": 10},
        started_at=now,
        created_at=now,
    )
    db_session.add(job)
    await db_session.commit()

    # Rogue worker attempts to submit result
    await DispatcherService.process_job_result(
        db=db_session,
        worker_id="rogue-imposter-worker",
        job_id="job-ownership-test",
        exit_code=0,
        output="Forged Result",
        duration_seconds=1.0,
    )

    # Verify job was NOT modified or marked completed by the imposter
    refreshed = (await db_session.execute(select(Job).where(Job.job_id == "job-ownership-test"))).scalar_one()
    assert refreshed.status == JobState.RUNNING.value
    assert refreshed.result_output is None

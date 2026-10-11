import asyncio
import pytest
from worker.agent.executor import ModularJobExecutor


@pytest.mark.asyncio
async def test_matrix_multiply_workload():
    """Verify safe local matrix multiplication execution."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)
    result = await executor.execute_job(
        job_id="job-mat-1",
        job_type="matrix_multiply",
        input_payload={"dimension": 20},
    )

    assert result.success is True
    assert result.exit_code == 0
    assert "Successfully multiplied 20x20 matrices" in result.output
    assert result.duration_seconds > 0.0


@pytest.mark.asyncio
async def test_data_processing_workload():
    """Verify safe local data processing execution."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)
    result = await executor.execute_job(
        job_id="job-data-1",
        job_type="data_processing",
        input_payload={
            "records": [{"id": 1, "val": 10.5}, {"id": 2, "val": 20.5}]
        },
    )

    assert result.success is True
    assert result.exit_code == 0
    assert "Processed 2 records. Aggregated sum: 31.00" in result.output


@pytest.mark.asyncio
async def test_unsupported_workload_rejected():
    """Verify arbitrary or unsupported workload types are rejected cleanly."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)
    result = await executor.execute_job(
        job_id="job-evil-1",
        job_type="arbitrary_bash_command",
        input_payload={"cmd": "whoami"},
    )

    assert result.success is False
    assert result.exit_code == 1
    assert "Unsupported workload" in result.error


@pytest.mark.asyncio
async def test_executor_timeout():
    """Verify workload execution adheres to timeout bounds."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    # Mock handler that sleeps longer than timeout
    async def slow_handler(_):
        await asyncio.sleep(0.5)
        return "done"

    executor._resolve_handler = lambda _: slow_handler

    result = await executor.execute_job(
        job_id="job-timeout-1",
        job_type="matrix_multiply",
        input_payload={},
        timeout_seconds=0.05,
    )

    assert result.success is False
    assert result.exit_code == -1
    assert "timed out" in result.error

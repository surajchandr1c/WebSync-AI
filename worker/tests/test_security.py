import asyncio
import json
from unittest.mock import patch, MagicMock
import pytest

from worker.agent.config import settings, WorkerSettings
from worker.agent.executor import ModularJobExecutor, WorkloadExecutionResult


@pytest.mark.asyncio
async def test_executor_output_truncation():
    """Outputs exceeding WORKER_MAX_OUTPUT_BYTES are truncated with clear notice."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)
    
    # Temporarily set max output to 500 bytes for test
    with patch.object(settings, "WORKER_MAX_OUTPUT_BYTES", 500):
        # Image processing or matrix multiply returns string
        # Let's mock a handler or run data processing returning large output
        with patch.object(
            executor,
            "_run_matrix_multiply",
            return_value="A" * 2000,
        ):
            result = await executor.execute_job(
                job_id="test-trunc-01",
                job_type="matrix_multiply",
                input_payload={"dimension": 10},
            )
            assert result.exit_code == 0
            assert len(result.output) < 2000
            assert "[Output truncated at 500 bytes limit]" in result.output
            assert result.output.startswith("A" * 500)


@pytest.mark.asyncio
async def test_executor_input_size_limit():
    """Input payload exceeding WORKER_MAX_INPUT_BYTES is rejected before execution."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)
    
    with patch.object(settings, "WORKER_MAX_INPUT_BYTES", 1024):
        huge_payload = {"data": "x" * 2048}
        result = await executor.execute_job(
            job_id="test-input-limit-01",
            job_type="matrix_multiply",
            input_payload=huge_payload,
        )
        assert result.exit_code == -1
        assert "Input payload exceeds maximum allowed size" in (result.error or "")


@pytest.mark.asyncio
async def test_executor_owner_pause_sharing():
    """When node owner pauses sharing, incoming jobs are rejected without processing."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    with patch.object(settings, "WORKER_PAUSE_SHARING", True):
        result = await executor.execute_job(
            job_id="test-pause-01",
            job_type="matrix_multiply",
            input_payload={"dimension": 10},
        )
        assert result.exit_code == -1
        assert "paused workload sharing" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_executor_cpu_threshold_protection():
    """When host CPU utilization exceeds WORKER_MAX_CPU_PERCENT, execution is refused."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    with patch.object(settings, "WORKER_MAX_CPU_PERCENT", 80.0):
        with patch("psutil.cpu_percent", return_value=95.5):
            result = await executor.execute_job(
                job_id="test-cpu-limit-01",
                job_type="matrix_multiply",
                input_payload={"dimension": 10},
            )
            assert result.exit_code == -1
            assert "Host CPU utilization too high" in (result.error or "")


@pytest.mark.asyncio
async def test_executor_ram_threshold_protection():
    """When host available RAM is below WORKER_MIN_AVAILABLE_RAM_MB, execution is refused."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    # Mock 256MB available RAM when 512MB is required
    mock_mem = MagicMock()
    mock_mem.available = 256 * 1024 * 1024

    with patch.object(settings, "WORKER_MIN_AVAILABLE_RAM_MB", 512):
        with patch("psutil.virtual_memory", return_value=mock_mem):
            with patch("psutil.cpu_percent", return_value=10.0):
                result = await executor.execute_job(
                    job_id="test-ram-limit-01",
                    job_type="matrix_multiply",
                    input_payload={"dimension": 10},
                )
                assert result.exit_code == -1
                assert "Insufficient available host RAM" in (result.error or "")


@pytest.mark.asyncio
async def test_handler_resolution_whitelist_only():
    """Arbitrary or unapproved job types must be strictly rejected without eval."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    result = await executor.execute_job(
        job_id="test-unapproved-01",
        job_type="shell_exec",
        input_payload={"command": "rm -rf /"},
    )
    assert result.exit_code == 1
    assert "Unsupported workload 'shell_exec'" in (result.error or "")

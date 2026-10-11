import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from worker.agent.dispatcher import WorkerDispatcher
from worker.agent.executor import ModularJobExecutor


@pytest.fixture
def mock_transport():
    transport = MagicMock()
    transport.poll_pending_jobs = AsyncMock(return_value=[])
    transport.ack_job = AsyncMock()
    transport.report_job_started = AsyncMock()
    transport.report_job_result = AsyncMock()
    return transport


@pytest.fixture
def executor():
    return ModularJobExecutor(max_concurrent_jobs=2)


@pytest.fixture
def dispatcher(mock_transport, executor):
    return WorkerDispatcher(
        transport=mock_transport,
        executor=executor,
        worker_id="test-worker-node",
        worker_jwt="mock-jwt-token",
        supported_workloads=["matrix_multiply", "data_processing"],
        poll_interval_seconds=0.1,
    )


@pytest.mark.asyncio
async def test_dispatcher_rejects_unsupported_workload(dispatcher, mock_transport):
    envelope = {
        "job_id": "job-bad-type",
        "job_type": "arbitrary_unapproved_script",
        "input_payload": {},
        "timeout_seconds": 60,
    }
    await dispatcher.handle_job_envelope(envelope)

    mock_transport.ack_job.assert_awaited_once()
    args, kwargs = mock_transport.ack_job.call_args
    assert kwargs["accepted"] is False
    assert "not supported" in kwargs["rejection_reason"]


@pytest.mark.asyncio
async def test_dispatcher_rejects_when_concurrency_limit_reached(dispatcher, mock_transport, executor):
    executor.max_concurrent_jobs = 0  # Artificially saturated
    envelope = {
        "job_id": "job-saturated",
        "job_type": "matrix_multiply",
        "input_payload": {"dimension": 10},
        "timeout_seconds": 60,
    }
    await dispatcher.handle_job_envelope(envelope)

    mock_transport.ack_job.assert_awaited_once()
    args, kwargs = mock_transport.ack_job.call_args
    assert kwargs["accepted"] is False
    assert "concurrency limit" in kwargs["rejection_reason"].lower()


@pytest.mark.asyncio
async def test_dispatcher_executes_and_reports_matrix_multiply(dispatcher, mock_transport):
    envelope = {
        "job_id": "job-matrix-valid",
        "job_type": "matrix_multiply",
        "input_payload": {
            "matrix_a": [[1, 2], [3, 4]],
            "matrix_b": [[5, 6], [7, 8]],
        },
        "timeout_seconds": 60,
    }
    await dispatcher.handle_job_envelope(envelope)

    # Ack was sent with accepted=True
    mock_transport.ack_job.assert_awaited_once()
    assert mock_transport.ack_job.call_args[1]["accepted"] is True

    # Start was reported
    mock_transport.report_job_started.assert_awaited_once()

    # Result was reported
    mock_transport.report_job_result.assert_awaited_once()
    result_kwargs = mock_transport.report_job_result.call_args[1]
    assert result_kwargs["exit_code"] == 0
    assert "Multiplied 2x2 by 2x2 matrices" in result_kwargs["output"]
    assert result_kwargs["duration_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_matrix_multiply_input_validation(executor):
    # Dimension mismatch error
    res_mismatch = await executor.execute_job(
        job_id="test-mismatch",
        job_type="matrix_multiply",
        input_payload={
            "matrix_a": [[1, 2, 3]],
            "matrix_b": [[1, 2], [3, 4]],  # cols_a 3 != rows_b 2
        },
    )
    assert res_mismatch.exit_code == 1
    assert "Dimension mismatch" in res_mismatch.error

    # Excessively large dimension (> 500)
    res_large = await executor.execute_job(
        job_id="test-large",
        job_type="matrix_multiply",
        input_payload={"dimension": 999},
    )
    assert res_large.exit_code == 1
    assert "exceeds maximum limit" in res_large.error


@pytest.mark.asyncio
async def test_data_processing_input_validation(executor):
    # Valid bounded records
    res_valid = await executor.execute_job(
        job_id="test-dp-valid",
        job_type="data_processing",
        input_payload={
            "records": [
                {"id": 1, "val": 10.5},
                {"id": 2, "val": 20.5},
                {"id": 3, "val": 30.0},
            ]
        },
    )
    assert res_valid.exit_code == 0
    assert "Aggregated sum: 61.00" in res_valid.output

    # Empty records
    res_empty = await executor.execute_job(
        job_id="test-dp-empty",
        job_type="data_processing",
        input_payload={"records": []},
    )
    assert res_empty.exit_code == 1
    assert "must not be empty" in res_empty.error

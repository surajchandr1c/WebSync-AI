import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from worker.agent.capabilities import detect_ollama_models, get_supported_workloads
from worker.agent.executor import ModularJobExecutor


def test_detect_ollama_models_offline():
    """Verify detect_ollama_models returns (False, []) when Ollama is offline."""
    # Point to an unreachable port with immediate timeout
    available, models = detect_ollama_models(
        ollama_url="http://127.0.0.1:54321",
        timeout=0.1,
        force_refresh=True,
    )
    assert available is False
    assert models == []


def test_detect_ollama_models_online():
    """Verify detect_ollama_models correctly parses models when Ollama /api/tags succeeds."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "llama3.2:latest", "model": "llama3.2:latest"},
            {"name": "mistral:latest", "model": "mistral:latest"},
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        available, models = detect_ollama_models(force_refresh=True)
        assert available is True
        assert "llama3.2:latest" in models
        assert "mistral:latest" in models


@pytest.mark.asyncio
async def test_run_llm_prompt_success():
    """Verify _run_llm_prompt succeeds when local Ollama generates a response."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "llama3.2:latest",
        "response": "Distributed computing enables multiple nodes to work cooperatively.",
        "eval_count": 35,
        "eval_duration": 850000000,
        "done": True,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await executor.execute_job(
            job_id="job-ai-success-1",
            job_type="llm_prompt",
            input_payload={
                "prompt": "What is distributed computing?",
                "model": "llama3.2:latest",
                "temperature": 0.7,
            },
            timeout_seconds=30,
        )

        assert result.success is True
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["model"] == "llama3.2:latest"
        assert "Distributed computing enables" in parsed["response"]
        assert parsed["eval_count"] == 35


@pytest.mark.asyncio
async def test_run_llm_prompt_missing_prompt_or_model():
    """Verify missing prompt or model fails input validation."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    # Missing prompt
    res1 = await executor.execute_job(
        job_id="job-ai-invalid-1",
        job_type="llm_prompt",
        input_payload={"model": "llama3.2:latest"},
    )
    assert res1.success is False
    assert "LLM workload requires a non-empty 'prompt'" in res1.error

    # Missing model
    res2 = await executor.execute_job(
        job_id="job-ai-invalid-2",
        job_type="llm_prompt",
        input_payload={"prompt": "Hello"},
    )
    assert res2.success is False
    assert "LLM workload requires a non-empty 'model'" in res2.error


@pytest.mark.asyncio
async def test_run_llm_prompt_ollama_unreachable():
    """Verify clear error message when Ollama inference server is not running."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    # Mock ConnectError
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        result = await executor.execute_job(
            job_id="job-ai-offline-1",
            job_type="llm_prompt",
            input_payload={
                "prompt": "Hello world",
                "model": "llama3.2:latest",
            },
        )

        assert result.success is False
        assert result.exit_code == 1
        assert "Ollama inference engine is not reachable on this node" in result.error
        assert "ollama serve" in result.error


@pytest.mark.asyncio
async def test_run_llm_prompt_model_not_found():
    """Verify clear actionable error message when model is missing from local Ollama."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"error": "model 'nonexistent-model' not found"}
    mock_resp.text = "model 'nonexistent-model' not found"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await executor.execute_job(
            job_id="job-ai-missing-model-1",
            job_type="llm_prompt",
            input_payload={
                "prompt": "Hello",
                "model": "nonexistent-model",
            },
        )

        assert result.success is False
        assert result.exit_code == 1
        assert "Model 'nonexistent-model' not found in local Ollama repository" in result.error
        assert "ollama pull nonexistent-model" in result.error

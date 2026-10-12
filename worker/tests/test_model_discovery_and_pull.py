"""Comprehensive unit tests for Ollama model discovery, normalization, matching, and pull manager."""

import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
import pytest

from worker.agent.capabilities import (
    normalize_model_name,
    model_matches,
    detect_ollama_status,
    detect_ollama_models,
)
from worker.agent.pull_manager import (
    validate_model_name,
    is_model_pulling,
    get_active_pulls,
    execute_model_pull,
    _active_pulls,
)
from worker.agent.executor import ModularJobExecutor


def test_normalize_model_name():
    """Verify model name canonicalization."""
    assert normalize_model_name("llama3.2") == "llama3.2:latest"
    assert normalize_model_name("llama3.2:latest") == "llama3.2:latest"
    assert normalize_model_name("llama3.2:3b") == "llama3.2:3b"
    assert normalize_model_name("  LLAMA3.2:LATEST  ") == "llama3.2:latest"
    assert normalize_model_name("phi3:mini") == "phi3:mini"
    assert normalize_model_name("library/deepseek-r1:8b") == "library/deepseek-r1:8b"
    assert normalize_model_name("") == ""
    assert normalize_model_name(None) == ""


def test_model_matches_rules():
    """Verify strict tag matching and flexible default tag resolution."""
    # Untagged request matches bare name or :latest
    assert model_matches("llama3.2", "llama3.2") is True
    assert model_matches("llama3.2", "llama3.2:latest") is True
    assert model_matches("llama3.2:latest", "llama3.2") is True
    assert model_matches("llama3.2:latest", "llama3.2:latest") is True

    # Case insensitive
    assert model_matches("Llama3.2:Latest", "llama3.2:latest") is True
    assert model_matches("llama3.2", "LLAMA3.2:LATEST") is True

    # Explicit size tags MUST NOT match different sizes
    assert model_matches("llama3.2:3b", "llama3.2:1b") is False
    assert model_matches("llama3.2:3b", "llama3.2:latest") is False
    assert model_matches("llama3.2:latest", "llama3.2:3b") is False
    assert model_matches("llama3.2:3b", "llama3.2:3b") is True

    # Cloud catalog models do NOT match unless actually present
    assert model_matches("gpt-oss:20b", "llama3.2:latest") is False
    assert model_matches("gpt-oss:20b", "gpt-oss:20b") is True

    # Empty edge cases
    assert model_matches("", "llama3.2") is False
    assert model_matches("llama3.2", "") is False
    assert model_matches(None, "llama3.2") is False


def test_detect_ollama_status_offline():
    """Verify detect_ollama_status accurately reports stopped or not_installed when offline."""
    with patch("shutil.which", return_value=None):
        status_info = detect_ollama_status(
            ollama_url="http://127.0.0.1:54321",
            timeout=0.1,
            force_refresh=True,
        )
        assert status_info["status"] == "not_installed"
        assert status_info["is_available"] is False
        assert status_info["installed_models"] == []

    with patch("shutil.which", return_value="/usr/local/bin/ollama"):
        status_info = detect_ollama_status(
            ollama_url="http://127.0.0.1:54321",
            timeout=0.1,
            force_refresh=True,
        )
        assert status_info["status"] == "stopped"
        assert status_info["is_available"] is False
        assert status_info["installed_models"] == []


def test_detect_ollama_status_ready():
    """Verify detect_ollama_status parses models accurately without cloud model spoofing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "llama3.2:latest"},
            {"name": "deepseek-r1:8b"},
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        status_info = detect_ollama_status(force_refresh=True)
        assert status_info["status"] == "ready"
        assert status_info["is_available"] is True
        assert status_info["installed_models"] == ["llama3.2:latest", "deepseek-r1:8b"]
        # Verify gpt-oss:20b or uninstalled cloud models are NOT present
        assert "gpt-oss:20b" not in status_info["installed_models"]


def test_validate_model_name():
    """Verify model name sanitization against injection attacks."""
    assert validate_model_name("llama3.2") == "llama3.2"
    assert validate_model_name("llama3.2:latest") == "llama3.2:latest"
    assert validate_model_name("deepseek-r1:1.5b") == "deepseek-r1:1.5b"
    assert validate_model_name("user/model:tag") == "user/model:tag"

    # Shell injection and forbidden characters must raise ValueError
    with pytest.raises(ValueError):
        validate_model_name("model; rm -rf /")

    with pytest.raises(ValueError):
        validate_model_name("model | cat")

    with pytest.raises(ValueError):
        validate_model_name("model`whoami`")

    with pytest.raises(ValueError):
        validate_model_name("")

    with pytest.raises(ValueError):
        validate_model_name("   ")


@pytest.mark.asyncio
async def test_execute_model_pull_already_installed():
    """Verify execute_model_pull fast-paths when model is already installed."""
    mock_status = {
        "status": "ready",
        "is_available": True,
        "installed_models": ["llama3.2:latest"],
        "last_checked": "2026-10-12T00:00:00Z",
    }

    with patch("worker.agent.pull_manager.detect_ollama_status", return_value=mock_status):
        result = await execute_model_pull("llama3.2")
        assert result["status"] == "already_installed"
        assert "already installed" in result["message"]


@pytest.mark.asyncio
async def test_execute_model_pull_streaming_success():
    """Verify execute_model_pull streams chunks and updates active pulls."""
    # Pre-condition: model not installed
    mock_status_before = {
        "status": "ready",
        "is_available": True,
        "installed_models": [],
        "last_checked": "2026-10-12T00:00:00Z",
    }
    mock_status_after = {
        "status": "ready",
        "is_available": True,
        "installed_models": ["phi3:latest"],
        "last_checked": "2026-10-12T00:01:00Z",
    }

    progress_events = []

    def on_progress(p):
        progress_events.append(p)

    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"status": "downloading", "completed": 500, "total": 1000}),
        json.dumps({"status": "downloading", "completed": 1000, "total": 1000}),
        json.dumps({"status": "verifying sha256 digest"}),
        json.dumps({"status": "success"}),
    ]

    async def mock_aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = mock_aiter_lines

    class MockStreamContext:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("worker.agent.pull_manager.detect_ollama_status", side_effect=[mock_status_before, mock_status_after]), \
         patch("httpx.AsyncClient.stream", return_value=MockStreamContext()):
        result = await execute_model_pull("phi3:latest", progress_callback=on_progress)
        assert result["status"] == "completed"
        assert "phi3:latest" in result["installed_models"]
        assert len(progress_events) >= 2


@pytest.mark.asyncio
async def test_executor_rejects_job_when_pull_in_progress():
    """Verify executor rejects job immediately if requested model is actively being pulled."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    with patch("worker.agent.executor.is_model_pulling", return_value=True):
        result = await executor.execute_job(
            job_id="job-pulling-test",
            job_type="llm_prompt",
            input_payload={"prompt": "Hello", "model": "mistral:latest"},
        )
        assert result.success is False
        assert "pull in progress" in result.error
        assert "currently downloading" in result.error


@pytest.mark.asyncio
async def test_executor_rejects_job_when_ollama_stopped():
    """Verify executor rejects job immediately if local Ollama daemon is stopped."""
    executor = ModularJobExecutor(max_concurrent_jobs=2)

    mock_stopped = {
        "status": "stopped",
        "is_available": False,
        "installed_models": [],
        "last_checked": "2026-10-12T00:00:00Z",
    }

    with patch("worker.agent.executor.is_model_pulling", return_value=False), \
         patch("worker.agent.executor.detect_ollama_status", return_value=mock_stopped):
        result = await executor.execute_job(
            job_id="job-stopped-test",
            job_type="llm_prompt",
            input_payload={"prompt": "Hello", "model": "llama3.2:latest"},
        )
        assert result.success is False
        assert "Ollama inference engine is stopped" in result.error
        assert "ollama serve" in result.error

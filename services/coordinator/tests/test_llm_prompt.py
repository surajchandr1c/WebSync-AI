import pytest
from httpx import AsyncClient, ASGITransport
from coordinator.main import app
from coordinator.models.worker import Worker
from coordinator.models.job import Job
from coordinator.scheduler.evaluator import evaluate_worker_eligibility
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_llm_prompt_job_submission_validation():
    """Verify input validation for llm_prompt workload submissions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid llm_prompt submission
        valid_payload = {
            "name": "Explain Concurrency",
            "job_type": "llm_prompt",
            "input_payload": {
                "prompt": "Explain asyncio in Python briefly.",
                "model": "llama3.2:latest",
                "temperature": 0.5,
            },
            "requirements": {
                "model": "llama3.2:latest",
            },
        }
        resp = await client.post("/api/v1/jobs", json=valid_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_type"] == "llm_prompt"
        assert data["input_payload"]["model"] == "llama3.2:latest"

        # 2. Missing prompt rejected
        invalid_no_prompt = {
            "name": "Invalid Prompt",
            "job_type": "llm_prompt",
            "input_payload": {
                "model": "llama3.2:latest",
            },
        }
        resp = await client.post("/api/v1/jobs", json=invalid_no_prompt)
        assert resp.status_code == 422

        # 3. Missing model rejected
        invalid_no_model = {
            "name": "Invalid Model",
            "job_type": "llm_prompt",
            "input_payload": {
                "prompt": "Hello world",
            },
        }
        resp = await client.post("/api/v1/jobs", json=invalid_no_model)
        assert resp.status_code == 422

        # 4. Malicious shell/command injection in model rejected
        invalid_model_chars = {
            "name": "Attack Payload",
            "job_type": "llm_prompt",
            "input_payload": {
                "prompt": "Hello",
                "model": "llama3; rm -rf /",
            },
        }
        resp = await client.post("/api/v1/jobs", json=invalid_model_chars)
        assert resp.status_code == 422

        # 5. Oversized prompt rejected (> 32,768 chars)
        oversized = {
            "name": "Huge Prompt",
            "job_type": "llm_prompt",
            "input_payload": {
                "prompt": "x" * 35000,
                "model": "llama3.2:latest",
            },
        }
        resp = await client.post("/api/v1/jobs", json=oversized)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_worker_registration_and_heartbeat_with_models():
    """Verify worker advertising and updating local LLM models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register worker with supported models
        reg_payload = {
            "worker_id": "ai-worker-node-1",
            "display_name": "AI Inference Node",
            "hostname": "ai-host",
            "platform": "Linux",
            "platform_version": "6.5.0",
            "cpu_utilization": 15.0,
            "total_ram_bytes": 16 * 1024 * 1024 * 1024,
            "available_ram_bytes": 12 * 1024 * 1024 * 1024,
            "supported_workloads": ["matrix_multiply", "data_processing", "llm_prompt"],
            "supported_models": ["llama3.2:latest", "mistral:latest"],
            "gpu_available": True,
            "gpu_metadata": [{"name": "NVIDIA RTX 4090", "memory_total_bytes": 24 * 1024 * 1024 * 1024}],
        }
        headers = {"X-Worker-Auth-Token": "test-dev-worker-token"}
        resp = await client.post("/api/v1/workers/register", json=reg_payload, headers=headers)
        assert resp.status_code == 201
        token = resp.json()["auth_token"]

        # Inspect worker details
        resp = await client.get("/api/v1/workers/ai-worker-node-1")
        assert resp.status_code == 200
        worker_data = resp.json()
        assert "llm_prompt" in worker_data["supported_workloads"]
        assert "llama3.2:latest" in worker_data["supported_models"]
        assert "mistral:latest" in worker_data["supported_models"]

        # Heartbeat update with new model
        hb_payload = {
            "cpu_utilization": 22.0,
            "available_ram_bytes": 10 * 1024 * 1024 * 1024,
            "supported_models": ["llama3.2:latest", "mistral:latest", "gemma2:latest"],
        }
        resp = await client.post(
            "/api/v1/workers/heartbeat",
            json=hb_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "gemma2:latest" in resp.json()["supported_models"]


@pytest.mark.asyncio
async def test_scheduler_evaluator_llm_model_matching():
    """Verify scheduler evaluator correctly enforces llm_prompt model requirements."""
    now = datetime.now(timezone.utc)
    worker = Worker(
        worker_id="ollama-rig-1",
        display_name="Ollama Rig",
        hostname="ollama-pc",
        platform="Windows",
        cpu_utilization=10.0,
        total_ram_bytes=32 * 1024 * 1024 * 1024,
        available_ram_bytes=24 * 1024 * 1024 * 1024,
        supported_workloads=["llm_prompt"],
        supported_models=["llama3.2:latest", "phi3:latest"],
        ollama_status="ready",
        active_job_count=0,
        max_concurrent_jobs=2,
        connection_status="online",
        last_heartbeat=now,
        registered_at=now,
        is_revoked=False,
    )

    # Job requesting available model with canonical tag
    job_match = Job(
        job_id="job-ai-1",
        name="Test Matching Model",
        job_type="llm_prompt",
        input_payload={"prompt": "Hi", "model": "llama3.2:latest"},
        requirements={"model": "llama3.2:latest"},
    )
    eligible, reason = evaluate_worker_eligibility(worker, job_match)
    assert eligible is True
    assert reason is None

    # Job requesting available model without tag (e.g. "llama3.2" matching "llama3.2:latest")
    job_match_untagged = Job(
        job_id="job-ai-1b",
        name="Test Untagged Model Match",
        job_type="llm_prompt",
        input_payload={"prompt": "Hi", "model": "llama3.2"},
        requirements={"model": "llama3.2"},
    )
    eligible, reason = evaluate_worker_eligibility(worker, job_match_untagged)
    assert eligible is True
    assert reason is None

    # Job requesting unavailable model
    job_unmatched = Job(
        job_id="job-ai-2",
        name="Test Missing Model",
        job_type="llm_prompt",
        input_payload={"prompt": "Hi", "model": "mistral:7b"},
        requirements={"model": "mistral:7b"},
    )
    eligible, reason = evaluate_worker_eligibility(worker, job_unmatched)
    assert eligible is False
    assert "Requested model 'mistral:7b' is not installed in local Ollama" in reason
    assert "ollama pull mistral:7b" in reason

    # Worker with stopped Ollama service
    worker_stopped = Worker(
        worker_id="ollama-rig-stopped",
        display_name="Stopped Ollama",
        hostname="stopped-pc",
        platform="Windows",
        cpu_utilization=10.0,
        total_ram_bytes=32 * 1024 * 1024 * 1024,
        available_ram_bytes=24 * 1024 * 1024 * 1024,
        supported_workloads=["llm_prompt"],
        supported_models=["llama3.2:latest"],
        ollama_status="stopped",
        active_job_count=0,
        max_concurrent_jobs=2,
        connection_status="online",
        last_heartbeat=now,
        registered_at=now,
        is_revoked=False,
    )
    eligible, reason = evaluate_worker_eligibility(worker_stopped, job_match)
    assert eligible is False
    assert "Ollama service is STOPPED" in reason

    # Job requesting target worker ID
    job_targeted = Job(
        job_id="job-ai-3",
        name="Test Targeted Node",
        job_type="llm_prompt",
        input_payload={"prompt": "Hi", "model": "llama3.2:latest", "target_worker_id": "other-worker"},
        requirements={"model": "llama3.2:latest", "target_worker_id": "other-worker"},
    )
    eligible, reason = evaluate_worker_eligibility(worker, job_targeted)
    assert eligible is False
    assert "Job targeted worker 'other-worker'" in reason


@pytest.mark.asyncio
async def test_worker_model_pull_endpoint():
    """Verify worker model pull initiation and input sanitization endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a test worker
        reg_payload = {
            "worker_id": "pull-test-worker",
            "display_name": "Pull Test Node",
            "hostname": "pull-host",
            "platform": "Linux",
            "cpu_utilization": 10.0,
            "total_ram_bytes": 16 * 1024 * 1024 * 1024,
            "available_ram_bytes": 12 * 1024 * 1024 * 1024,
            "supported_workloads": ["llm_prompt"],
            "supported_models": ["llama3.2:latest"],
            "ollama_status": "ready",
        }
        headers = {"X-Worker-Auth-Token": "test-dev-worker-token"}
        resp = await client.post("/api/v1/workers/register", json=reg_payload, headers=headers)
        assert resp.status_code == 201

        # 2. Get models endpoint
        resp = await client.get("/api/v1/workers/pull-test-worker/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ollama_status"] == "ready"
        assert "llama3.2:latest" in data["installed_models"]

        # 3. Pull an already-installed model
        resp = await client.post(
            "/api/v1/workers/pull-test-worker/models/pull",
            json={"model": "llama3.2"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_installed"

        # 4. Pull invalid model name (shell injection attempt)
        resp = await client.post(
            "/api/v1/workers/pull-test-worker/models/pull",
            json={"model": "model; echo pwned"},
        )
        assert resp.status_code == 422

        # 5. Pull for non-existent worker
        resp = await client.post(
            "/api/v1/workers/nonexistent-worker-xyz/models/pull",
            json={"model": "mistral"},
        )
        assert resp.status_code == 404


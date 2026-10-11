import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import pytest
from sqlalchemy import select

from coordinator.config import CoordinatorSettings, validate_production_secrets
from coordinator.core.security import create_access_token, hash_password
from coordinator.core.logging_config import SensitiveDataFilter
from coordinator.core.rate_limit import SlidingWindowRateLimiter
from coordinator.db.session import async_session_factory
from coordinator.models.user import User
from coordinator.models.worker import Worker
from coordinator.models.job import Job
from coordinator.schemas.job import JobState
from coordinator.scheduler.engine import scheduler_engine


@pytest.mark.asyncio
async def test_token_type_separation(client, admin_auth_headers):
    """Worker tokens must be rejected on user endpoints, and user tokens rejected on worker endpoints."""
    # 1. Create a worker token
    worker_token = create_access_token(subject="worker-node-99", token_type="worker")
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    # Worker token attempting user job submission
    resp = await client.post(
        "/api/v1/jobs",
        json={"name": "Worker Job", "job_type": "matrix_multiply", "input_payload": {"dimension": 10}},
        headers=worker_headers,
    )
    assert resp.status_code == 403
    assert "Token is not authorized for user access" in resp.json()["detail"]

    # 2. User token attempting worker internal action
    user_headers = admin_auth_headers
    resp = await client.get("/api/v1/workers/worker-node-99/jobs/pending", headers=user_headers)
    assert resp.status_code == 403
    assert "Token is not authorized for worker actions" in resp.json()["detail"]

    # 3. Expired token rejection
    expired_token = create_access_token(
        subject="user-1",
        token_type="user",
        expires_delta=timedelta(seconds=-10),
    )
    resp = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_privilege_escalation_prevention(client, admin_auth_headers):
    """Non-admin user registration cannot self-grant 'admin' role once system is bootstrapped."""
    # Attempting to self-grant admin role without admin credentials is forbidden (403)
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "attacker",
            "email": "attacker@example.com",
            "password": "strong_password_123",
            "role": "admin",
        },
    )
    assert resp.status_code == 403
    assert "Administrative role cannot be self-assigned" in resp.json()["detail"]

    # Authenticated admin CAN create another admin
    admin_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "second_admin",
            "email": "second_admin@example.com",
            "password": "strong_password_123",
            "role": "admin",
        },
        headers=admin_auth_headers,
    )
    assert admin_resp.status_code == 201
    assert admin_resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_object_ownership_isolation(client, admin_auth_headers):
    """Standard users can only access their own jobs and results; admins can access any."""
    async with async_session_factory() as db:
        user_a = User(
            username="user_a",
            email="user_a@websync.ai",
            hashed_password=hash_password("password_a_123"),
            role="operator",
            is_active=True,
        )
        user_b = User(
            username="user_b",
            email="user_b@websync.ai",
            hashed_password=hash_password("password_b_123"),
            role="operator",
            is_active=True,
        )
        db.add_all([user_a, user_b])
        await db.commit()
        await db.refresh(user_a)
        await db.refresh(user_b)
        user_a_id = user_a.id
        user_b_id = user_b.id

    token_a = create_access_token(subject=user_a_id, token_type="user", role="operator")
    token_b = create_access_token(subject=user_b_id, token_type="user", role="operator")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a job
    create_resp = await client.post(
        "/api/v1/jobs",
        json={"name": "Job User A", "job_type": "matrix_multiply", "input_payload": {"dimension": 10}},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    # User B attempts to access User A's job directly -> Denied (403 or 404)
    get_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=headers_b)
    assert get_resp.status_code in (403, 404)

    # User B attempts to access User A's job result -> Denied
    result_resp = await client.get(f"/api/v1/jobs/{job_id}/result", headers=headers_b)
    assert result_resp.status_code in (403, 404)

    # User B lists jobs -> empty list
    list_b = await client.get("/api/v1/jobs", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()["items"]) == 0

    # User A can view their own job
    get_a = await client.get(f"/api/v1/jobs/{job_id}", headers=headers_a)
    assert get_a.status_code == 200

    # Admin can view User A's job
    get_admin = await client.get(f"/api/v1/jobs/{job_id}", headers=admin_auth_headers)
    assert get_admin.status_code == 200


@pytest.mark.asyncio
async def test_worker_revocation_and_cross_worker_spoofing(client, admin_auth_headers):
    """Admin can revoke workers; revoked workers are blocked; workers cannot act as other workers."""
    # 1. Register worker 1 and worker 2
    reg_payload_1 = {
        "worker_id": "sec-worker-01",
        "display_name": "Security Node 1",
        "hostname": "sec-host-01",
        "platform": "Linux",
        "total_ram_bytes": 8589934592,
        "available_ram_bytes": 4294967296,
        "supported_workloads": ["matrix_multiply"],
    }
    reg_resp_1 = await client.post(
        "/api/v1/workers/register",
        json=reg_payload_1,
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
    )
    assert reg_resp_1.status_code == 201
    token_w1 = reg_resp_1.json()["auth_token"]

    reg_payload_2 = {
        "worker_id": "sec-worker-02",
        "display_name": "Security Node 2",
        "hostname": "sec-host-02",
        "platform": "Linux",
        "total_ram_bytes": 8589934592,
        "available_ram_bytes": 4294967296,
        "supported_workloads": ["matrix_multiply"],
    }
    reg_resp_2 = await client.post(
        "/api/v1/workers/register",
        json=reg_payload_2,
        headers={"X-Worker-Auth-Token": "test-dev-worker-token"},
    )
    assert reg_resp_2.status_code == 201
    token_w2 = reg_resp_2.json()["auth_token"]

    # 2. Cross-worker spoofing test: Worker 1 attempts action under Worker 2 path
    headers_w1 = {"Authorization": f"Bearer {token_w1}"}
    spoof_resp = await client.post(
        "/api/v1/workers/sec-worker-02/jobs/dummy-job/ack",
        json={"job_id": "dummy-job", "worker_id": "sec-worker-02", "accepted": True},
        headers=headers_w1,
    )
    assert spoof_resp.status_code == 403
    assert "not authorized to acknowledge jobs for 'sec-worker-02'" in spoof_resp.json()["detail"]

    # 3. Non-admin attempting worker revocation -> 403 Forbidden
    async with async_session_factory() as db:
        regular_user = User(
            username="regular_op",
            email="reg@websync.ai",
            hashed_password=hash_password("regular_123"),
            role="operator",
            is_active=True,
        )
        db.add(regular_user)
        await db.commit()
        await db.refresh(regular_user)
        reg_user_id = regular_user.id

    token_reg = create_access_token(subject=reg_user_id, token_type="user", role="operator")
    revoke_unauth = await client.post(
        "/api/v1/workers/sec-worker-01/revoke",
        headers={"Authorization": f"Bearer {token_reg}"},
    )
    assert revoke_unauth.status_code == 403

    # 4. Admin revokes worker 1
    revoke_resp = await client.post(
        "/api/v1/workers/sec-worker-01/revoke",
        headers=admin_auth_headers,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_revoked"] is True

    # 5. Worker 1 calls heartbeat after revocation -> 403 Forbidden
    hb_resp = await client.post(
        "/api/v1/workers/heartbeat",
        json={
            "cpu_utilization": 25.0,
            "available_ram_bytes": 4294967296,
            "active_job_count": 0,
        },
        headers=headers_w1,
    )
    assert hb_resp.status_code == 403
    assert "revoked" in hb_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_input_payload_size_enforcement(client, admin_auth_headers):
    """Job input payload exceeding MAX_JOB_INPUT_BYTES must be rejected with 422."""
    huge_input = {"data": "x" * (2 * 1024 * 1024 + 100)}
    resp = await client.post(
        "/api/v1/jobs",
        json={"name": "Huge Job", "job_type": "data_processing", "input_payload": huge_input},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_startup_stranded_job_recovery():
    """Coordinator startup recovers stranded SCHEDULED jobs to QUEUED and marks RUNNING jobs FAILED."""
    now = datetime.now(timezone.utc)
    job_sched_id = "job-stranded-sched"
    job_run_id = "job-stranded-run"

    async with async_session_factory() as db:
        # Create worker
        w = Worker(
            worker_id="reboot-worker-01",
            display_name="Reboot Worker",
            hostname="reboot-host",
            platform="Linux",
            connection_status="busy",
            active_job_count=2,
            supported_workloads=["matrix_multiply"],
        )
        db.add(w)

        # Create scheduled job
        j_sched = Job(
            job_id=job_sched_id,
            name="Stranded Sched",
            job_type="matrix_multiply",
            input_payload={"dimension": 10},
            status=JobState.SCHEDULED.value,
            assigned_worker_id="reboot-worker-01",
        )
        # Create running job
        j_run = Job(
            job_id=job_run_id,
            name="Stranded Run",
            job_type="matrix_multiply",
            input_payload={"dimension": 10},
            status=JobState.RUNNING.value,
            assigned_worker_id="reboot-worker-01",
            started_at=now,
        )
        db.add_all([j_sched, j_run])
        await db.commit()

        # Run startup recovery
        summary = await scheduler_engine.recover_jobs_on_coordinator_startup(db)
        assert summary["requeued"] >= 1
        assert summary["failed"] >= 1

        # Check recovered states
        stmt_sched = select(Job).where(Job.job_id == job_sched_id)
        res_sched = (await db.execute(stmt_sched)).scalar_one()
        assert res_sched.status == JobState.QUEUED.value
        assert res_sched.assigned_worker_id is None

        stmt_run = select(Job).where(Job.job_id == job_run_id)
        res_run = (await db.execute(stmt_run)).scalar_one()
        assert res_run.status == JobState.FAILED.value
        assert "Coordinator restarted" in (res_run.result_error or "")

        stmt_w = select(Worker).where(Worker.worker_id == "reboot-worker-01")
        res_w = (await db.execute(stmt_w)).scalar_one()
        assert res_w.connection_status == "disconnected"
        assert res_w.active_job_count == 0


def test_production_secrets_validator():
    """Production secrets validator must raise ValueError on weak secrets, default dev token, or wildcard CORS."""
    strong_key = "super-strong-production-signing-token-min-32-chars-long"

    # 1. Weak secret in production
    with pytest.raises(ValueError, match="at least 32 characters"):
        CoordinatorSettings(
            ENVIRONMENT="production",
            COORDINATOR_SECRET_KEY="short-key",
            WORKER_DEV_AUTH_TOKEN="custom-token-xyz",
            WORKER_ENROLLMENT_SECRET="production-worker-enrollment-secret-min-32-chars",
            COORDINATOR_ALLOWED_ORIGINS="https://dashboard.example.com",
        )

    # 2. Wildcard CORS in production
    with pytest.raises(ValueError, match="Wildcard"):
        CoordinatorSettings(
            ENVIRONMENT="production",
            COORDINATOR_SECRET_KEY=strong_key,
            WORKER_DEV_AUTH_TOKEN="custom-token-xyz",
            WORKER_ENROLLMENT_SECRET="production-worker-enrollment-secret-min-32-chars",
            COORDINATOR_ALLOWED_ORIGINS="*",
        )

    # 3. Missing enrollment secret in production
    with pytest.raises(ValueError, match="WORKER_ENROLLMENT_SECRET must be configured"):
        CoordinatorSettings(
            ENVIRONMENT="production",
            COORDINATOR_SECRET_KEY=strong_key,
            WORKER_DEV_AUTH_TOKEN="custom-token-xyz",
            WORKER_ENROLLMENT_SECRET="",
            COORDINATOR_ALLOWED_ORIGINS="https://dashboard.example.com",
        )

    # 4. Valid production settings
    valid_prod = CoordinatorSettings(
        ENVIRONMENT="production",
        COORDINATOR_SECRET_KEY=strong_key,
        WORKER_DEV_AUTH_TOKEN="custom-token-xyz",
        WORKER_ENROLLMENT_SECRET="production-worker-enrollment-secret-min-32-chars",
        COORDINATOR_ALLOWED_ORIGINS="https://dashboard.example.com",
    )
    assert valid_prod.ENVIRONMENT == "production"


def test_sensitive_data_logging_redaction():
    """SensitiveDataFilter must redact JWTs, bearer tokens, passwords, and DB connection strings."""
    filter_instance = SensitiveDataFilter()

    # Redact Bearer JWT
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="User authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.xyz",
        args=(), exc_info=None,
    )
    filter_instance.filter(record)
    assert "[REDACTED_JWT]" in record.msg
    assert "eyJhbGci" not in record.msg

    # Redact password
    record_pw = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Failed login attempt for user admin with password 'supersecret123'",
        args=(), exc_info=None,
    )
    filter_instance.filter(record_pw)
    assert "[REDACTED_PASSWORD]" in record_pw.msg
    assert "supersecret123" not in record_pw.msg

    # Redact DB connection string
    record_db = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Connecting to database postgresql+asyncpg://admin:db_secret_pass@db.internal:5432/websync",
        args=(), exc_info=None,
    )
    filter_instance.filter(record_db)
    assert "[REDACTED_SECRET]" in record_db.msg
    assert "db_secret_pass" not in record_db.msg


def test_sliding_window_rate_limiter():
    """SlidingWindowRateLimiter blocks requests that exceed configured capacity with HTTP 429."""
    from fastapi import HTTPException
    limiter = SlidingWindowRateLimiter()
    key = "test-client-ip"

    # First 3 requests succeed
    limiter.check(key=key, max_requests=3, window_seconds=60)
    limiter.check(key=key, max_requests=3, window_seconds=60)
    limiter.check(key=key, max_requests=3, window_seconds=60)

    # 4th request must raise HTTP 429 with Retry-After header
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(key=key, max_requests=3, window_seconds=60)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0

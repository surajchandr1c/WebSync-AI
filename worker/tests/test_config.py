import pytest
from pydantic import ValidationError
from worker.agent.config import WorkerSettings


def test_default_worker_settings():
    """Verify default worker configuration is populated cleanly."""
    cfg = WorkerSettings()
    assert cfg.WEB_SYNC_COORDINATOR_URL.startswith("http")
    assert len(cfg.WEB_SYNC_WORKER_ID) > 0
    assert cfg.WEB_SYNC_HEARTBEAT_INTERVAL >= 1
    assert cfg.WEB_SYNC_MAX_CONCURRENT_JOBS >= 1
    assert cfg.WEB_SYNC_LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR")


def test_coordinator_url_formatting():
    """Verify URL trailing slash is stripped and schemes validated."""
    cfg = WorkerSettings(WEB_SYNC_COORDINATOR_URL="http://192.168.1.100:8000/")
    assert cfg.WEB_SYNC_COORDINATOR_URL == "http://192.168.1.100:8000"

    with pytest.raises(ValidationError):
        WorkerSettings(WEB_SYNC_COORDINATOR_URL="ftp://invalid-scheme.com")


def test_invalid_log_level_rejected():
    """Verify invalid log level throws ValidationError."""
    with pytest.raises(ValidationError):
        WorkerSettings(WEB_SYNC_LOG_LEVEL="UNSUPPORTED_LEVEL")


def test_invalid_intervals_rejected():
    """Verify non-positive intervals throw ValidationError."""
    with pytest.raises(ValidationError):
        WorkerSettings(WEB_SYNC_HEARTBEAT_INTERVAL=0)

    with pytest.raises(ValidationError):
        WorkerSettings(WEB_SYNC_MAX_CONCURRENT_JOBS=0)

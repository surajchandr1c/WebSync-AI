import socket
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Configuration settings for the WebSync AI Worker Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    WORKER_ID: str = f"node-{socket.gethostname()}"
    WORKER_COORDINATOR_URL: str = "http://localhost:8000"
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 10
    WORKER_AUTH_TOKEN: str = "change-worker-token-in-production"
    WORKER_MAX_CONCURRENT_JOBS: int = 2
    LOG_LEVEL: str = "INFO"


settings = WorkerSettings()

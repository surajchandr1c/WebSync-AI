import platform
import socket
from typing import Optional
from pydantic import Field, field_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Configuration settings for the WebSync AI Worker Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Coordinator Connection
    WEB_SYNC_COORDINATOR_URL: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("WEB_SYNC_COORDINATOR_URL", "WORKER_COORDINATOR_URL"),
        description="URL of the central WebSync AI coordinator service",
    )

    # Worker Identity
    WEB_SYNC_WORKER_ID: str = Field(
        default_factory=lambda: f"node-{socket.gethostname().lower().replace(' ', '-')}",
        validation_alias=AliasChoices("WEB_SYNC_WORKER_ID", "WORKER_ID"),
        description="Unique worker node identifier",
    )
    WEB_SYNC_WORKER_NAME: str = Field(
        default_factory=lambda: socket.gethostname(),
        validation_alias=AliasChoices("WEB_SYNC_WORKER_NAME", "WORKER_NAME"),
        description="Human-friendly node display name",
    )

    # Credentials
    WEB_SYNC_WORKER_TOKEN: str = Field(
        default="dev-worker-secret-token",
        validation_alias=AliasChoices("WEB_SYNC_WORKER_TOKEN", "WORKER_DEV_AUTH_TOKEN"),
        description="Pre-shared registration secret for worker enrollment",
    )

    # Operation & Telemetry
    WEB_SYNC_HEARTBEAT_INTERVAL: int = Field(
        default=10,
        ge=1,
        validation_alias=AliasChoices("WEB_SYNC_HEARTBEAT_INTERVAL", "WORKER_HEARTBEAT_INTERVAL_SECONDS"),
        description="Seconds between heartbeat reports",
    )
    WEB_SYNC_LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias=AliasChoices("WEB_SYNC_LOG_LEVEL", "LOG_LEVEL"),
        description="Logging verbosity level (DEBUG, INFO, WARNING, ERROR)",
    )
    WEB_SYNC_MAX_CONCURRENT_JOBS: int = Field(
        default=2,
        ge=1,
        validation_alias=AliasChoices("WEB_SYNC_MAX_CONCURRENT_JOBS", "WORKER_MAX_CONCURRENT_JOBS"),
        description="Maximum concurrent jobs allowed on this node",
    )

    # Networking & Timeouts
    WEB_SYNC_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        ge=1.0,
        description="HTTP client timeout in seconds",
    )
    WEB_SYNC_MAX_RETRY_BACKOFF_SECONDS: float = Field(
        default=30.0,
        ge=5.0,
        description="Maximum exponential backoff cap in seconds",
    )

    @field_validator("WEB_SYNC_COORDINATOR_URL")
    @classmethod
    def validate_coordinator_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(
                f"WEB_SYNC_COORDINATOR_URL must begin with http:// or https:// (got '{v}')"
            )
        return v

    @field_validator("WEB_SYNC_LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level '{v}'. Allowed: {', '.join(valid_levels)}")
        return v.upper()


def load_settings() -> WorkerSettings:
    """Load and validate worker settings with helpful error reporting."""
    try:
        return WorkerSettings()
    except Exception as e:
        raise ValueError(f"Worker configuration error: {str(e)}") from e


# Global settings instance
settings = load_settings()

from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoordinatorSettings(BaseSettings):
    """Configuration settings for the WebSync AI Coordinator Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    COORDINATOR_HOST: str = "0.0.0.0"
    COORDINATOR_PORT: int = 8000
    COORDINATOR_API_V1_STR: str = "/api/v1"

    # Security & Auth
    COORDINATOR_SECRET_KEY: str = "dev-insecure-secret-key-32-chars-min-needed-here"
    COORDINATOR_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    WORKER_TOKEN_EXPIRE_MINUTES: int = 1440

    # Worker Settings
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = 30
    WORKER_DEV_AUTH_TOKEN: str = "dev-worker-secret-token"

    # CORS
    COORDINATOR_ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,tauri://localhost"
    )

    # Database (PostgreSQL intended, SQLite supported for development)
    DATABASE_URL: str = "sqlite+aiosqlite:///./coordinator.db"

    @property
    def cors_origins(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.COORDINATOR_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "CoordinatorSettings":
        if self.ENVIRONMENT.lower() == "production":
            insecure_markers = ["dev-insecure", "change-this", "secret", "admin"]
            if (
                any(marker in self.COORDINATOR_SECRET_KEY.lower() for marker in insecure_markers)
                or len(self.COORDINATOR_SECRET_KEY) < 32
            ):
                raise ValueError(
                    "COORDINATOR_SECRET_KEY must be a cryptographically secure key "
                    "(at least 32 characters) when running in production."
                )
        return self


settings = CoordinatorSettings()

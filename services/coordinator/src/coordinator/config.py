from typing import List, Optional
from pydantic import model_validator, field_validator, Field, AliasChoices
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
    COORDINATOR_PORT: int = Field(
        default=8000,
        validation_alias=AliasChoices("COORDINATOR_PORT", "PORT"),
    )
    COORDINATOR_API_V1_STR: str = "/api/v1"

    # Security & Auth
    COORDINATOR_SECRET_KEY: str = "dev-insecure-secret-key-32-chars-min-needed-here"
    COORDINATOR_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    WORKER_TOKEN_EXPIRE_MINUTES: int = 1440

    # Worker Enrollment & Credentials
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = 30
    WORKER_DEV_AUTH_TOKEN: str = "dev-worker-secret-token"
    WORKER_ENROLLMENT_SECRET: str = ""

    # Resource Limits & Quotas
    MAX_QUEUED_JOBS: int = 1000
    MAX_JOB_INPUT_BYTES: int = 2 * 1024 * 1024  # 2MB
    MAX_WS_MESSAGE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2MB

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 20

    # CORS & Frontend Origins
    COORDINATOR_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,tauri://localhost",
        validation_alias=AliasChoices("COORDINATOR_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )
    FRONTEND_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("FRONTEND_URL", "NEXT_PUBLIC_FRONTEND_URL"),
    )

    # Database (PostgreSQL intended, SQLite supported for development)
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./coordinator.db",
        validation_alias=AliasChoices("DATABASE_URL"),
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not v:
            return "sqlite+aiosqlite:///./coordinator.db"
        v_str = str(v).strip()
        # Convert standard Railway postgresql:// or postgres:// to asyncpg dialect
        if v_str.startswith("postgres://"):
            v_str = "postgresql+asyncpg://" + v_str[len("postgres://"):]
        elif v_str.startswith("postgresql://") and not v_str.startswith("postgresql+asyncpg://"):
            v_str = "postgresql+asyncpg://" + v_str[len("postgresql://"):]
        return v_str

    @property
    def cors_origins(self) -> List[str]:
        origins = [
            origin.strip()
            for origin in self.COORDINATOR_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        if self.FRONTEND_URL and self.FRONTEND_URL.strip():
            clean_front = self.FRONTEND_URL.strip().rstrip("/")
            if clean_front not in origins:
                origins.append(clean_front)
        return origins

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "CoordinatorSettings":
        if self.ENVIRONMENT.lower() == "production":
            insecure_markers = ["dev-insecure", "change-this", "secret", "admin", "test-secret"]
            if (
                any(marker in self.COORDINATOR_SECRET_KEY.lower() for marker in insecure_markers)
                or len(self.COORDINATOR_SECRET_KEY) < 32
            ):
                raise ValueError(
                    "COORDINATOR_SECRET_KEY must be a cryptographically secure key "
                    "(at least 32 characters) when running in production."
                )
            if self.WORKER_DEV_AUTH_TOKEN == "dev-worker-secret-token":
                raise ValueError(
                    "WORKER_DEV_AUTH_TOKEN must not use the default development token in production."
                )
            if not self.WORKER_ENROLLMENT_SECRET or len(self.WORKER_ENROLLMENT_SECRET) < 16:
                raise ValueError(
                    "WORKER_ENROLLMENT_SECRET must be configured with a secure key (min 16 chars) in production."
                )
            if "*" in self.COORDINATOR_ALLOWED_ORIGINS:
                raise ValueError(
                    "Wildcard '*' CORS origins are strictly forbidden in production."
                )
        return self


def validate_production_secrets(cfg: CoordinatorSettings) -> CoordinatorSettings:
    """Explicit validator function for testing or deployment sanity-checks."""
    return cfg.validate_production_secrets()


settings = CoordinatorSettings()

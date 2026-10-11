from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class CoordinatorSettings(BaseSettings):
    """Configuration settings for the WebSync AI Coordinator."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    COORDINATOR_HOST: str = "0.0.0.0"
    COORDINATOR_PORT: int = 8000
    COORDINATOR_API_V1_STR: str = "/api/v1"
    COORDINATOR_SECRET_KEY: str = "change-this-secret-key-in-production"
    COORDINATOR_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,tauri://localhost"
    DATABASE_URL: str = "sqlite+aiosqlite:///./coordinator.db"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.COORDINATOR_ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = CoordinatorSettings()

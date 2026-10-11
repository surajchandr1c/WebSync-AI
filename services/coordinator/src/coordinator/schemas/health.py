from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing coordinator service operational health."""

    status: str = Field(default="healthy", description="Coordinator overall operational status")
    service: str = Field(default="WebSync AI Coordinator", description="Service identifier")
    version: str = Field(default="0.2.0", description="Coordinator API version")
    timestamp: datetime = Field(description="Current UTC timestamp")
    uptime_seconds: float = Field(ge=0.0, description="Coordinator process uptime in seconds")
    python_version: str = Field(description="Host Python runtime version")
    environment: str = Field(description="Deployment environment name")
    database: str = Field(
        description="Database health connectivity status ('healthy' or 'unhealthy')"
    )

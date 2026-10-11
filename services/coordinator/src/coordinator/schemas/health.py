from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing coordinator service operational health."""

    status: str = Field(default="healthy", description="Current operational status")
    service: str = Field(default="WebSync AI Coordinator", description="Service identifier")
    version: str = Field(default="0.1.0", description="Coordinator semantic version")
    timestamp: datetime = Field(description="Current server UTC timestamp")
    uptime_seconds: float = Field(ge=0.0, description="Uptime duration in seconds")
    python_version: str = Field(description="Host Python runtime version")
    environment: str = Field(description="Deployment environment name")

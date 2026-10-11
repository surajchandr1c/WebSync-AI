import time
import platform
from datetime import datetime, timezone
from fastapi import APIRouter
from coordinator.schemas.health import HealthResponse
from coordinator.config import settings

router = APIRouter(tags=["Health"])

_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Coordinator Health Check",
    description="Returns real-time health, uptime, and metadata of the WebSync AI Coordinator.",
)
async def get_health() -> HealthResponse:
    """Return actual operational health metrics."""
    uptime = time.time() - _START_TIME
    return HealthResponse(
        status="healthy",
        service="WebSync AI Coordinator",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(uptime, 2),
        python_version=platform.python_version(),
        environment=settings.ENVIRONMENT,
    )

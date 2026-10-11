import time
import platform
from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from coordinator.schemas.health import HealthResponse
from coordinator.config import settings
from coordinator.db.session import check_db_health

router = APIRouter(tags=["Health"])

_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Coordinator Health Check",
    description="Returns real-time health, uptime, API version, and database connectivity of the Coordinator.",
)
async def get_health(response: Response) -> HealthResponse:
    """Return actual operational health and database connectivity."""
    uptime = time.time() - _START_TIME
    db_ok = await check_db_health()
    db_status = "healthy" if db_ok else "unhealthy"

    overall_status = "healthy" if db_ok else "degraded"
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        service="WebSync AI Coordinator",
        version="0.2.0",
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(uptime, 2),
        python_version=platform.python_version(),
        environment=settings.ENVIRONMENT,
        database=db_status,
    )

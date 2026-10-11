from fastapi import APIRouter
from coordinator.api.routes import health, auth, workers, jobs, ws

api_router = APIRouter()

# Mount API v1 route groups
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(workers.router)
api_router.include_router(jobs.router)

# WebSocket router
ws_router = ws.router

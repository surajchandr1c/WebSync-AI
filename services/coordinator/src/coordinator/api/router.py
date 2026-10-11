from fastapi import APIRouter
from coordinator.api.routes import health, workers

api_router = APIRouter()

# Mount routes
api_router.include_router(health.router)
api_router.include_router(workers.router)

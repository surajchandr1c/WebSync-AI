import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from coordinator.config import settings
from coordinator.api.router import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coordinator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WebSync AI Coordinator v0.1.0 in %s mode", settings.ENVIRONMENT)
    logger.info("CORS origins configured: %s", settings.cors_origins)
    yield
    logger.info("Shutting down WebSync AI Coordinator")


app = FastAPI(
    title="WebSync AI Coordinator",
    description="Central orchestration and scheduling service for WebSync AI distributed computing platform.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix=settings.COORDINATOR_API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "WebSync AI Coordinator",
        "version": "0.1.0",
        "status": "operational",
        "docs_url": "/docs",
        "api_v1": settings.COORDINATOR_API_V1_STR,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "coordinator.main:app",
        host=settings.COORDINATOR_HOST,
        port=settings.COORDINATOR_PORT,
        reload=(settings.ENVIRONMENT == "development"),
    )

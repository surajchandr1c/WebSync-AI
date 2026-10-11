import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from coordinator.config import settings
from coordinator.core.logging_config import setup_coordinator_logging
from coordinator.db.session import init_db
from coordinator.api.router import api_router, ws_router

# Configure structured logging with sensitive token redaction filter
setup_coordinator_logging(settings.LOG_LEVEL)
logger = logging.getLogger("coordinator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WebSync AI Coordinator v0.2.0 in '%s' mode", settings.ENVIRONMENT)
    # Initialize DB schemas and run startup recovery
    try:
        await init_db()
        from coordinator.db.session import async_session_factory
        from coordinator.scheduler.engine import scheduler_engine
        async with async_session_factory() as db:
            await scheduler_engine.recover_jobs_on_coordinator_startup(db)
    except Exception as e:
        logger.error("Database schema initialization / startup recovery encountered error: %s", str(e))

    logger.info("CORS origins configured: %s", settings.cors_origins)
    yield
    logger.info("Shutting down WebSync AI Coordinator gracefully.")


app = FastAPI(
    title="WebSync AI Coordinator",
    description="Central orchestration, worker management, and job scheduling service for WebSync AI distributed compute platform.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Centralized Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic validation errors cleanly without leaking internals."""
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Sanitize internal errors to prevent stack trace or raw SQL leakage in responses."""
    logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred. Please contact the administrator."},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


from coordinator.api.routes.health import router as health_router

# Mount API routers
app.include_router(health_router)
app.include_router(api_router, prefix=settings.COORDINATOR_API_V1_STR)
app.include_router(ws_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "WebSync AI Coordinator",
        "version": "0.2.0",
        "status": "operational",
        "api_v1": settings.COORDINATOR_API_V1_STR,
        "docs_url": "/docs",
        "ws_dashboard": "/ws/dashboard",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "coordinator.main:app",
        host=settings.COORDINATOR_HOST,
        port=settings.COORDINATOR_PORT,
        reload=(settings.ENVIRONMENT == "development"),
    )

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
import asyncio
from coordinator.config import settings
from coordinator.core.logging_config import setup_coordinator_logging
from coordinator.db.session import init_db
from coordinator.api.router import api_router, ws_router

# Configure structured logging with sensitive token redaction filter
setup_coordinator_logging(settings.LOG_LEVEL)
logger = logging.getLogger("coordinator")


async def run_cluster_watchdog():
    """Continuous background loop monitoring stale workers and expired job deadlines."""
    logger.info("Cluster watchdog background monitor started.")
    from coordinator.db.session import async_session_factory
    from coordinator.services.worker_service import WorkerService
    from coordinator.services.job_service import JobService

    while True:
        try:
            await asyncio.sleep(5.0)
            async with async_session_factory() as db:
                await WorkerService.check_and_mark_stale_workers(db)
                await JobService.check_and_fail_timed_out_jobs(db)
        except asyncio.CancelledError:
            logger.info("Cluster watchdog monitor stopped.")
            break
        except Exception as e:
            logger.debug("Cluster watchdog iteration warning: %s", str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WebSync AI Coordinator v0.2.0 in '%s' mode", settings.ENVIRONMENT)
    if settings.ENVIRONMENT.lower() == "production" and "sqlite" in settings.DATABASE_URL.lower():
        err_msg = "Production environment error: SQLite is not permitted for production deployment. Please configure DATABASE_URL with a valid PostgreSQL connection string."
        logger.error(err_msg)
        raise RuntimeError(err_msg)

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

    watchdog_task = asyncio.create_task(run_cluster_watchdog())

    yield

    watchdog_task.cancel()
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass
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
# Accepts explicit origins plus any private LAN IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x, localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?",
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

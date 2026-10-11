import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from coordinator.config import settings
from coordinator.db.session import init_db
from coordinator.api.router import api_router, ws_router

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coordinator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WebSync AI Coordinator v0.2.0 in '%s' mode", settings.ENVIRONMENT)
    # Initialize DB schemas
    try:
        await init_db()
    except Exception as e:
        logger.error("Database schema initialization encountered error: %s", str(e))

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


# Mount API routers
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

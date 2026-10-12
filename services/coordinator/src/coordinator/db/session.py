import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from coordinator.config import settings
from coordinator.db.base import Base

logger = logging.getLogger("coordinator.db")

# Build async engine
engine_kwargs = {
    "echo": (settings.LOG_LEVEL.upper() == "DEBUG"),
    "future": True,
}
if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy.pool import NullPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = NullPool
else:
    # Production PostgreSQL connection pool configuration
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    # Import models so they are registered with Base metadata
    import coordinator.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.DATABASE_URL:
            try:
                await conn.execute(text("ALTER TABLE workers ADD COLUMN supported_models JSON DEFAULT '[]' NOT NULL"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE workers ADD COLUMN ollama_status VARCHAR(32) DEFAULT 'not_installed' NOT NULL"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE workers ADD COLUMN last_model_check TIMESTAMP WITH TIME ZONE NULL"))
            except Exception:
                pass
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_assigned_worker_id ON jobs (assigned_worker_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_assigned_worker_status ON jobs (assigned_worker_id, status)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_status_created_at ON jobs (status, created_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workers_status_last_heartbeat ON workers (connection_status, last_heartbeat)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_events_created_at ON job_events (created_at)"))
        except Exception as e:
            logger.debug("Database index ensure skipped: %s", str(e))
    logger.info("Database schemas initialized successfully.")


async def check_db_health() -> bool:
    """Execute lightweight ping to verify actual database connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database health check failed: %s", str(e))
        return False

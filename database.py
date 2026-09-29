import time
import logging
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool

from config import settings

logger = logging.getLogger("onboarding_buddy.database")

Base = declarative_base()


def get_engine():
    """Create and configure SQLAlchemy engine with connection pooling optimized for Neon PostgreSQL."""
    db_url = settings.DATABASE_URL.strip() if settings.DATABASE_URL else ""

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    if db_url:
        logger.info(f"Configuring PostgreSQL connection pool for: {settings.masked_database_url}")
        return create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,  # Crucial for Neon serverless scale-to-zero wakeups
            echo=False,
        )
    else:
        # Fallback to local SQLite when no database URL is supplied (e.g. offline testing)
        logger.warning("No DATABASE_URL configured. Falling back to local SQLite database.")
        return create_engine(
            "sqlite:///./onboarding_buddy_local.db",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_migrations():
    """Apply Alembic migrations to align database schema with models."""
    try:
        import os
        from alembic.config import Config
        from alembic import command

        base_dir = os.path.abspath(os.path.dirname(__file__))
        ini_path = os.path.join(base_dir, "alembic.ini")
        if os.path.exists(ini_path):
            alembic_cfg = Config(ini_path)
            alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
            command.upgrade(alembic_cfg, "head")
            logger.info("Database schema migrations applied successfully.")
    except Exception as e:
        logger.warning(f"Note on running database migrations: {e}")


def init_db():
    """Initialize database schemas and apply pending migrations idempotently."""
    try:
        # Import models so they are registered with Base.metadata
        import models.db_models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        run_migrations()
        logger.info("Database schema initialized and verified successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
        raise


def get_db() -> Generator:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for obtaining a database session in background/service code."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> dict:
    """Performs an active database ping to verify connection health and latency."""
    start_time = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.time() - start_time) * 1000, 2)
        provider = "Neon PostgreSQL" if "neon.tech" in (settings.DATABASE_URL or "") else ("PostgreSQL" if settings.is_db_configured else "SQLite (Local Fallback)")
        return {
            "status": "healthy",
            "provider": provider,
            "latency_ms": latency_ms,
            "pool_size": settings.DB_POOL_SIZE if settings.is_db_configured else 1,
            "database": settings.masked_database_url if settings.is_db_configured else "local_sqlite"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": "Database connection unreachable",
            "provider": "Neon PostgreSQL" if "neon.tech" in (settings.DATABASE_URL or "") else "Unknown"
        }

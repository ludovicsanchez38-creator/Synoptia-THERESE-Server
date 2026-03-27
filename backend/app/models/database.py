"""
Thérèse Server - Database Connection

Supports PostgreSQL (production) and SQLite (development).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

logger = logging.getLogger(__name__)

# Engines
sync_engine = None
async_engine = None
AsyncSessionLocal = None


def _is_sqlite() -> bool:
    """Check if using SQLite."""
    return "sqlite" in settings.database_url


def _get_sync_url() -> str:
    """Convert async URL to sync URL."""
    url = settings.database_url
    url = url.replace("+asyncpg", "")
    url = url.replace("+aiosqlite", "")
    return url


async def init_db() -> None:
    """Initialize database connection and create tables."""
    global sync_engine, async_engine, AsyncSessionLocal

    logger.info("Initialisation base de données : %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url)

    # Engine kwargs selon le type de DB
    async_kwargs = {
        "echo": settings.debug,
        "pool_pre_ping": True,
    }
    sync_kwargs = {
        "echo": settings.debug,
    }

    if _is_sqlite():
        sync_kwargs["connect_args"] = {"check_same_thread": False}
        # SQLite : pool limité
        async_kwargs["pool_size"] = 5
        async_kwargs["max_overflow"] = 10
        async_kwargs["pool_recycle"] = 1800

        # PRAGMAs SQLite
        from sqlalchemy import event

        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
    else:
        # PostgreSQL : pool plus large
        async_kwargs["pool_size"] = 20
        async_kwargs["max_overflow"] = 30
        async_kwargs["pool_recycle"] = 3600

    # Sync engine (migrations, table creation)
    sync_engine = create_engine(_get_sync_url(), **sync_kwargs)

    # Async engine (runtime)
    async_engine = create_async_engine(settings.database_url, **async_kwargs)

    # SQLite PRAGMAs
    if _is_sqlite():
        from sqlalchemy import event
        event.listen(sync_engine, "connect", _set_sqlite_pragmas)
        event.listen(async_engine.sync_engine, "connect", _set_sqlite_pragmas)

    # Session factory
    AsyncSessionLocal = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import models to register them
    from app.auth import models as auth_models  # noqa: F401
    from app.models import entities  # noqa: F401
    from app.models import entities_agents  # noqa: F401
    from app.models import entities_missions  # noqa: F401

    # Create tables
    SQLModel.metadata.create_all(sync_engine)

    # Indexes
    from sqlalchemy import text as sqlalchemy_text
    with sync_engine.connect() as conn:
        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_conversations_org_id ON conversations (org_id)",
            "CREATE INDEX IF NOT EXISTS ix_conversations_created_at ON conversations (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_contacts_email ON contacts (email)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_org_id ON audit_logs (org_id)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs (timestamp)",
        ]
        for stmt in index_statements:
            try:
                conn.execute(sqlalchemy_text(stmt))
            except (OSError, RuntimeError) as e:
                logger.debug("Index creation skipped: %s", e)
        conn.commit()

    logger.info("Base de données initialisée")


async def close_db() -> None:
    """Close database connections."""
    global async_engine, sync_engine

    if async_engine:
        await async_engine.dispose()
        async_engine = None
    if sync_engine:
        sync_engine.dispose()
        sync_engine = None

    logger.info("Connexions base de données fermées")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session for dependency injection."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.debug("Session rollback (get_session): %s", e)
            await session.rollback()
            raise


def get_sync_session() -> Session:
    """Get sync database session for migrations."""
    if sync_engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return Session(sync_engine)


def get_sync_connection():
    """Get sync connection from singleton engine."""
    if sync_engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return sync_engine.connect()


@asynccontextmanager
async def get_session_context():
    """Get async database session as context manager (for startup code)."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.debug("Session rollback (get_session_context): %s", e)
            await session.rollback()
            raise

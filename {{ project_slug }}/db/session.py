"""Async SQLAlchemy engine and session dependency for the API."""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from {{ project_slug }}.core.config import settings
from {{ project_slug }}.core.logging import get_logging_context

LOGGER = logging.getLogger(__name__)


def create_db_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: float = 30.0,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> AsyncEngine:
    """Factory function to create database engine.

    Use this function in application lifespan to create the engine
    and store it in app.state for pytest-xdist compatibility.

    Args:
        database_url: Database connection URL
        echo: Echo SQL statements to logs
        pool_size: Number of connections to keep in pool
        max_overflow: Max connections beyond pool_size
        pool_timeout: Seconds to wait for available connection
        pool_recycle: Seconds before recycling connection
        pool_pre_ping: Test connection validity before use

    Returns:
        Configured async SQLAlchemy engine
    """
    return create_async_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Factory function to create session maker.

    Use this function in application lifespan to create the session maker
    and store it in app.state for pytest-xdist compatibility.

    Args:
        engine: Async SQLAlchemy engine to bind sessions to

    Returns:
        Configured async session maker
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Global engine and session maker for backward compatibility.
# These are used by:
# - core/activity_logging.py (fire-and-forget logging without request context)
# - tests/conftest.py (test fixtures update these to point to worker database)
#
# For new code, prefer using app.state.engine and app.state.async_session_maker
# via the get_session() dependency or request.app.state in middleware.
engine = create_db_engine(
    settings.database_url,
    echo=settings.sqlalchemy_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
async_session_maker: async_sessionmaker[AsyncSession] = create_session_maker(engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for request scope.

    Session lifecycle:
    1. Session created from pool
    2. Yielded to request handler
    3. Committed on success OR rolled back on exception
    4. Session closed and returned to pool

    The session dependency handles rollback automatically on exceptions.
    Callers are responsible for explicit commits.

    For pytest-xdist compatibility, test fixtures update the global
    async_session_maker to use the worker-specific database. This allows
    the same code path to work both in production and tests without
    requiring request access in the dependency.

    Yields:
        AsyncSession for database operations
    """
    context = get_logging_context()
    LOGGER.debug("session_created", extra=context)

    async with async_session_maker() as session:
        try:
            yield session
            LOGGER.debug("session_completed", extra=context)
        except Exception:
            LOGGER.warning("session_rollback", extra=context, exc_info=True)
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def init_db(db_engine: AsyncEngine | None = None) -> None:
    """Test-only helper; production migrations should use Alembic.

    Args:
        db_engine: Optional engine to use. Defaults to global engine for backward compatibility.
    """
    target_engine = db_engine if db_engine is not None else engine
    async with target_engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

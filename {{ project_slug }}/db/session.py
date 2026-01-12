"""Async SQLAlchemy engine and session dependency for the API."""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from {{ project_slug }}.core.config import settings
from {{ project_slug }}.core.logging import get_logging_context

LOGGER = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.sqlalchemy_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Create async database session for request scope.

    Session lifecycle:
    1. Session created from pool
    2. Yielded to request handler
    3. Committed on success OR rolled back on exception
    4. Session closed and returned to pool

    The session dependency handles rollback automatically on exceptions.
    Callers are responsible for explicit commits.

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


async def init_db() -> None:
    """Test-only helper; production migrations should use Alembic."""
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

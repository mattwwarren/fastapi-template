import socket
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.db.session import get_session
from app.main import app


@pytest.fixture(scope="session")
def database_url(docker_ip: str, docker_services: Any) -> str:
    port = docker_services.port_for("postgres", 5432)

    def is_responsive() -> bool:
        try:
            socket.create_connection((docker_ip, port), timeout=1).close()
        except OSError:
            return False
        return True

    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=0.5,
        check=is_responsive,
    )
    return f"postgresql+asyncpg://app:app@{docker_ip}:{port}/app_test"


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_maker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def reset_db(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)
        await connection.run_sync(SQLModel.metadata.create_all)


@pytest.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def get_session_override():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

import asyncio
import socket
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine, make_url
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
def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def alembic_engine(database_url: str) -> Generator[Engine, None, None]:
    url = make_url(database_url)
    if url.drivername.endswith("asyncpg"):
        url = url.set(drivername=url.drivername.replace("asyncpg", "psycopg"))
    engine = create_engine(url)
    yield engine
    engine.dispose()


async def truncate_tables(engine: AsyncEngine, alembic_config: Config) -> None:
    table_names = [table.name for table in SQLModel.metadata.sorted_tables]
    if not table_names:
        return
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename IN :names"
            ).bindparams(bindparam("names", expanding=True)),
            {"names": table_names},
        )
        existing = [row[0] for row in result.fetchall()]
    if not existing:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.begin() as connection:
            result = await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename IN :names"
                ).bindparams(bindparam("names", expanding=True)),
                {"names": table_names},
            )
            existing = [row[0] for row in result.fetchall()]
    if not existing:
        return
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE TABLE " + ", ".join(existing) + " RESTART IDENTITY CASCADE")
        )


@pytest.fixture(scope="session")
async def engine(
    database_url: str, alembic_config: Config
) -> AsyncGenerator[AsyncEngine, None]:
    await asyncio.to_thread(command.upgrade, alembic_config, "head")
    engine = create_async_engine(database_url, poolclass=NullPool)
    yield engine
    await truncate_tables(engine, alembic_config)
    await engine.dispose()


@pytest.fixture
def session_maker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def reset_db(engine, alembic_config: Config) -> None:
    await truncate_tables(engine, alembic_config)


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

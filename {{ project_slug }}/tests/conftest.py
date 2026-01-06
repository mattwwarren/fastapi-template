"""Pytest fixtures for async API testing with Postgres + Alembic."""

import asyncio
import os
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

from {{ project_slug }}.core.config import settings
from {{ project_slug }}.db import session as db_session
from {{ project_slug }}.db.session import get_session
from {{ project_slug }}.main import app

# Port constants
POSTGRES_PORT = 5432
SOCKET_TIMEOUT_SECONDS = 1
DOCKER_TIMEOUT_SECONDS = 30.0
DOCKER_PAUSE_SECONDS = 0.5


@pytest.fixture(scope="session")
def database_url(docker_ip: str, docker_services: object) -> str:
    port = docker_services.port_for("postgres", POSTGRES_PORT)  # type: ignore[attr-defined]

    def is_responsive() -> bool:
        try:
            socket.create_connection(
                (docker_ip, port), timeout=SOCKET_TIMEOUT_SECONDS
            ).close()
        except OSError:
            return False
        return True

    docker_services.wait_until_responsive(  # type: ignore[attr-defined]
        timeout=DOCKER_TIMEOUT_SECONDS,
        pause=DOCKER_PAUSE_SECONDS,
        check=is_responsive,
    )
    url = f"postgresql+asyncpg://app:app@{docker_ip}:{port}/app_test"
    os.environ["DATABASE_URL"] = url
    settings.database_url = url
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("postgresql+asyncpg", "postgresql+psycopg"),
    )
    return config


@pytest.fixture(scope="session")
def alembic_engine(database_url: str) -> Generator[Engine, None, None]:
    url = make_url(database_url)
    if url.drivername.endswith("asyncpg"):
        url = url.set(drivername=url.drivername.replace("asyncpg", "psycopg"))
    engine = create_engine(url)
    yield engine
    engine.dispose()


def run_migrations(config: Config, engine: Engine) -> None:
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        try:
            command.upgrade(config, "head")
        finally:
            config.attributes.pop("connection", None)
        connection.commit()  # type: ignore[attr-defined]


async def truncate_tables(
    engine: AsyncEngine, alembic_config: Config, alembic_engine: Engine
) -> None:
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
        await asyncio.to_thread(run_migrations, alembic_config, alembic_engine)
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
    database_url: str,
    alembic_config: Config,
    alembic_engine: Engine,
) -> AsyncGenerator[AsyncEngine, None]:
    await asyncio.to_thread(run_migrations, alembic_config, alembic_engine)
    old_engine = db_session.engine
    engine = create_async_engine(database_url, poolclass=NullPool)
    if old_engine is not engine:
        await old_engine.dispose()
    db_session.engine = engine
    db_session.async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield engine
    await truncate_tables(engine, alembic_config, alembic_engine)
    await engine.dispose()


@pytest.fixture
def session_maker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def reset_db(
    engine: AsyncEngine, alembic_config: Config, alembic_engine: Engine
) -> None:
    await truncate_tables(engine, alembic_config, alembic_engine)


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


@pytest.fixture
async def test_user(client: AsyncClient) -> dict[str, Any]:
    """Create a test user and return user data."""
    response = await client.post(
        "/users",
        json={
            "name": "Test User",
            "email": "testuser@example.com",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def test_organization(client: AsyncClient) -> dict[str, Any]:
    """Create a test organization and return organization data."""
    response = await client.post(
        "/organizations",
        json={"name": "Test Organization"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def multiple_users(client: AsyncClient) -> list[dict[str, Any]]:
    """Create multiple test users with varying data."""
    users = []
    for i in range(3):
        response = await client.post(
            "/users",
            json={
                "name": f"User {i}",
                "email": f"user{i}@example.com",
            },
        )
        assert response.status_code == 201
        users.append(response.json())
    return users


@pytest.fixture
async def user_with_org(
    client: AsyncClient,
    test_user: dict[str, Any],
    test_organization: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a user with an organization membership."""
    # Create membership
    membership_response = await client.post(
        "/memberships",
        json={
            "user_id": test_user["id"],
            "organization_id": test_organization["id"],
        },
    )
    assert membership_response.status_code == 201

    # Return user and org
    return test_user, test_organization

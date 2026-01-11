"""Pytest fixtures for async API testing with Postgres + Alembic."""

import asyncio
import os
import socket
from collections.abc import AsyncGenerator, Generator
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import bindparam, create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from test_api_service.core.auth import AuthMiddleware, CurrentUser
from test_api_service.core.tenants import TenantContext
from test_api_service.db import session as db_session
from test_api_service.db.session import get_session
from test_api_service.main import app
from test_api_service.models.membership import Membership, MembershipRole
from test_api_service.models.organization import Organization
from test_api_service.models.user import User

# Import settings fixtures for test isolation and pytest-xdist compatibility
from test_api_service.tests.fixtures.settings import (  # noqa: F401
    test_settings,
    test_settings_factory,
    test_settings_with_activity_logging_disabled,
    test_settings_with_auth,
    test_settings_with_storage,
)

# Port constants
POSTGRES_PORT = 5432
SOCKET_TIMEOUT_SECONDS = 1
DOCKER_TIMEOUT_SECONDS = 30.0
DOCKER_PAUSE_SECONDS = 0.5


@pytest.fixture(scope="session")
def database_url(docker_ip: str, docker_services: object) -> str:
    """Get database URL from docker container without mutating global settings.

    Sets DATABASE_URL environment variable for Alembic migrations (which run in
    subprocess), but does NOT mutate the global settings singleton to preserve
    pytest-xdist compatibility. Individual test sessions create fresh Settings
    instances via test_settings fixture.

    Args:
        docker_ip: Docker host IP from docker_services
        docker_services: pytest-docker services fixture

    Returns:
        Database URL for test Postgres instance
    """
    port = docker_services.port_for("postgres", POSTGRES_PORT)  # type: ignore[attr-defined]

    def is_responsive() -> bool:
        try:
            socket.create_connection((docker_ip, port), timeout=SOCKET_TIMEOUT_SECONDS).close()
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
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    # Find alembic.ini at project root (3 levels up from conftest.py)
    project_root = Path(__file__).parent.parent.parent
    alembic_ini_path = project_root / "alembic.ini"

    config = Config(str(alembic_ini_path))
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("postgresql+asyncpg", "postgresql+psycopg"),
    )
    return config


@pytest.fixture(scope="session")
def alembic_engine(database_url: str) -> Generator[Engine]:
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
        connection.commit()


async def truncate_tables(engine: AsyncEngine, alembic_config: Config, alembic_engine: Engine) -> None:
    table_names = [table.name for table in SQLModel.metadata.sorted_tables]
    if not table_names:
        return
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN :names").bindparams(
                bindparam("names", expanding=True)
            ),
            {"names": table_names},
        )
        existing = [row[0] for row in result.fetchall()]
    if not existing:
        await asyncio.to_thread(run_migrations, alembic_config, alembic_engine)
        async with engine.begin() as connection:
            result = await connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN :names").bindparams(
                    bindparam("names", expanding=True)
                ),
                {"names": table_names},
            )
            existing = [row[0] for row in result.fetchall()]
    if not existing:
        return
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE " + ", ".join(existing) + " RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
async def engine(
    database_url: str,
    alembic_config: Config,
    alembic_engine: Engine,
) -> AsyncGenerator[AsyncEngine]:
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
def session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(
    session_maker: async_sessionmaker[AsyncSession],
    reset_db: None,  # noqa: ARG001 - Ensure DB reset happens first
) -> AsyncGenerator[AsyncSession]:
    """Provide a database session for tests that need direct database access."""
    async with session_maker() as session:
        yield session


@pytest.fixture(autouse=True)
async def reset_db(engine: AsyncEngine, alembic_config: Config, alembic_engine: Engine) -> None:
    await truncate_tables(engine, alembic_config, alembic_engine)


class TestAuthMiddleware(BaseHTTPMiddleware):
    """Test middleware that injects a test user and tenant context into all requests.

    Supports header-based user and organization specification for test isolation:
    - X-Test-User-ID: UUID of the user to authenticate as
    - X-Test-Org-ID: UUID of the organization to scope to

    If headers are not provided, uses default test user.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Any,  # noqa: ANN401
    ) -> Response:
        """Inject test user and tenant context into request state.

        Checks for X-Test-User-ID and X-Test-Org-ID headers to allow tests to
        specify which user is making the request. If headers are provided, uses
        those values. Otherwise uses default test user.
        """
        # Try to get user and org from headers (for role-based testing)
        user_id_header = request.headers.get("X-Test-User-ID")
        org_id_header = request.headers.get("X-Test-Org-ID")

        if user_id_header and org_id_header:
            # Test-specified user
            test_user = CurrentUser(
                id=UUID(user_id_header),
                email="test@example.com",
                organization_id=UUID(org_id_header),
            )
        else:
            # Default fallback test user
            test_user = CurrentUser(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                email="testuser@example.com",
                organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            )

        request.state.user = test_user

        # Also set tenant context for endpoints that require TenantDep
        request.state.tenant = TenantContext(
            organization_id=test_user.organization_id,  # type: ignore[arg-type]
            user_id=test_user.id,
        )

        return await call_next(request)


@pytest.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    async def get_session_override() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    # Override session dependency
    app.dependency_overrides[get_session] = get_session_override

    # Reset middleware stack to allow modifications
    app.middleware_stack = None

    # Remove AuthMiddleware if present and add TestAuthMiddleware that injects test user
    app.user_middleware = [m for m in app.user_middleware if m.cls != AuthMiddleware]
    app.add_middleware(TestAuthMiddleware)

    # Need to rebuild the middleware stack
    app.middleware_stack = app.build_middleware_stack()


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
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
async def test_organization(client: AsyncClient) -> dict[str, Any]:
    """Create a test organization and return organization data."""
    response = await client.post(
        "/organizations",
        json={"name": "Test Organization"},
    )
    assert response.status_code == HTTPStatus.CREATED
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
        assert response.status_code == HTTPStatus.CREATED
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
    assert membership_response.status_code == HTTPStatus.CREATED

    # Return user and org
    return test_user, test_organization


@pytest.fixture
async def default_auth_user_in_org(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Ensure default test user and default org exist with OWNER membership.

    This fixture creates the user/org/membership required for tests that rely on
    the default auth middleware credentials to have RBAC permissions.

    Used by tests that POST to endpoints protected by RequireAdmin, RequireOwner, etc.
    """
    test_org_id = UUID("00000000-0000-0000-0000-000000000000")
    test_user_id = UUID("00000000-0000-0000-0000-000000000001")

    async with session_maker() as session:
        # Create test user if it doesn't exist
        user_result = await session.execute(select(User).where(User.id == test_user_id))
        if not user_result.scalar_one_or_none():
            test_user = User(
                id=test_user_id,
                email="testuser@example.com",
                name="Test User",
            )
            session.add(test_user)
            await session.commit()

        # Create test organization if it doesn't exist
        org_result = await session.execute(select(Organization).where(Organization.id == test_org_id))
        if not org_result.scalar_one_or_none():
            test_org = Organization(id=test_org_id, name="Test Organization")
            session.add(test_org)
            await session.commit()

        # Create default membership for test user with OWNER role
        membership_result = await session.execute(
            select(Membership).where(
                Membership.user_id == test_user_id,
                Membership.organization_id == test_org_id,
            )
        )
        if not membership_result.scalar_one_or_none():
            test_membership = Membership(
                user_id=test_user_id,
                organization_id=test_org_id,
                role=MembershipRole.OWNER,
            )
            session.add(test_membership)
            await session.commit()

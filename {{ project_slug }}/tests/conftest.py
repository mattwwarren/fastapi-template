"""Pytest fixtures for async API testing with Postgres + Alembic.

This module provides pytest-xdist compatible fixtures for parallel test execution.
Each xdist worker gets its own database (app_test_gw0, app_test_gw1, etc.) to
prevent data conflicts between parallel test runs.
"""

import asyncio
import contextlib
import os
import socket
from collections.abc import AsyncGenerator, Generator
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from psycopg import sql
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

from {{ project_slug }}.core.auth import AuthMiddleware, CurrentUser
from {{ project_slug }}.core.tenants import TenantContext
from {{ project_slug }}.db import session as db_session
from {{ project_slug }}.db.session import create_session_maker, get_session
from {{ project_slug }}.main import app
from {{ project_slug }}.models.membership import Membership, MembershipRole
from {{ project_slug }}.models.organization import Organization
from {{ project_slug }}.models.user import User

# Import settings fixtures for test isolation and pytest-xdist compatibility
from {{ project_slug }}.tests.fixtures.settings import (  # noqa: F401
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


# =============================================================================
# pytest-xdist Database Isolation Helpers
# =============================================================================


def get_worker_database_name(worker_id: str) -> str:
    """Return database name for xdist worker.

    For pytest-xdist, each worker (gw0, gw1, etc.) gets its own database
    to prevent data conflicts during parallel test execution.

    Args:
        worker_id: pytest-xdist worker ID ("master" when not using xdist)

    Returns:
        Database name: "app_test" for master, "app_test_gw0" etc. for workers
    """
    if worker_id == "master" or not worker_id:
        return "app_test"
    return f"app_test_{worker_id}"


def create_database_if_not_exists(host: str, port: int, db_name: str) -> None:
    """Create database using sync psycopg connection to postgres database.

    Handles race conditions where multiple workers may try to create the
    same database simultaneously by catching DuplicateDatabase errors.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        db_name: Name of database to create
    """
    conn_str = f"host={host} port={port} user=app password=app dbname=postgres"
    # Another worker may have created it first - suppress that specific error
    with (
        psycopg.connect(conn_str, autocommit=True) as conn,
        contextlib.suppress(psycopg.errors.DuplicateDatabase),
    ):
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))


def drop_database_if_exists(host: str, port: int, db_name: str) -> None:
    """Drop database at session end for cleanup.

    Terminates any active connections to the database before dropping.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        db_name: Name of database to drop
    """
    conn_str = f"host={host} port={port} user=app password=app dbname=postgres"
    with psycopg.connect(conn_str, autocommit=True) as conn:
        # Terminate active connections to the database
        conn.execute(
            sql.SQL(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s"
            ),
            (db_name,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))


@pytest.fixture(scope="session")
def database_url(
    docker_ip: str,
    docker_services: object,
    worker_id: str,
) -> Generator[str]:
    """Get database URL from docker container with per-worker isolation.

    For pytest-xdist compatibility, creates a separate database for each worker:
    - master (no xdist): app_test
    - gw0: app_test_gw0
    - gw1: app_test_gw1
    - etc.

    Sets DATABASE_URL environment variable for Alembic migrations (which run in
    subprocess), but does NOT mutate the global settings singleton to preserve
    pytest-xdist compatibility. Individual test sessions create fresh Settings
    instances via test_settings fixture.

    Args:
        docker_ip: Docker host IP from docker_services
        docker_services: pytest-docker services fixture
        worker_id: pytest-xdist worker ID ("master" when not using xdist)

    Yields:
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

    # Get worker-specific database name
    db_name = get_worker_database_name(worker_id)

    # Create the database if it doesn't exist
    create_database_if_not_exists(docker_ip, port, db_name)

    # Build URL with worker-specific database
    url = f"postgresql+asyncpg://app:app@{docker_ip}:{port}/{db_name}"
    os.environ["DATABASE_URL"] = url

    yield url

    # Cleanup: drop worker database (skip for master to allow debugging)
    if worker_id != "master":
        drop_database_if_exists(docker_ip, port, db_name)


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
    """Create async database engine for test session.

    This fixture is pytest-xdist compatible: it does NOT mutate the global
    db_session.engine or db_session.async_session_maker. Instead, tests
    use the fixtures directly and client fixtures inject them into app.state.

    Args:
        database_url: Worker-specific database URL from database_url fixture
        alembic_config: Alembic configuration
        alembic_engine: Sync engine for running migrations

    Yields:
        AsyncEngine for this test worker's database
    """
    # Run migrations on the worker's database
    await asyncio.to_thread(run_migrations, alembic_config, alembic_engine)

    # Create async engine for this worker (NullPool avoids connection leaks)
    test_engine = create_async_engine(database_url, poolclass=NullPool)

    # Update global session maker to use test engine for backward compatibility
    # with code that accesses db_session.async_session_maker directly
    # (e.g., activity_logging.py, tenants.py)
    db_session.engine = test_engine
    db_session.async_session_maker = create_session_maker(test_engine)

    yield test_engine

    # Cleanup
    await truncate_tables(test_engine, alembic_config, alembic_engine)
    await test_engine.dispose()


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

        Looks up the user's actual role from the database for proper RBAC testing.
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

        # Look up the user's actual role from the database for proper RBAC testing
        async with request.app.state.async_session_maker() as session:
            result = await session.execute(
                select(Membership.role)
                .where(Membership.user_id == test_user.id)
                .where(Membership.organization_id == test_user.organization_id)
            )
            user_role = result.scalar_one_or_none()

            # Default to OWNER if no membership exists (for backwards compatibility with fixtures)
            if user_role is None:
                user_role = MembershipRole.OWNER

            # Set tenant context with actual role from database
            request.state.tenant = TenantContext(
                organization_id=test_user.organization_id,  # type: ignore[arg-type]
                user_id=test_user.id,
                role=user_role,
            )

        return await call_next(request)


@pytest.fixture
async def client_bypass_auth(
    engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    """Test client that bypasses AuthMiddleware and injects test user directly.

    WARNING: This fixture is for migration purposes only. Use `authenticated_client`
    for new tests to ensure auth middleware is properly tested.

    This client removes AuthMiddleware and replaces it with TestAuthMiddleware that
    directly injects user/tenant into request state without JWT validation.
    """
    async def get_session_override() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    # Set app.state for pytest-xdist compatibility (lifespan pattern)
    app.state.engine = engine
    app.state.async_session_maker = session_maker

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
async def authenticated_client(
    engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    """Test client that keeps AuthMiddleware and requires valid JWT tokens.

    Use this fixture for tests that need to verify auth behavior. Set Authorization
    header with a valid JWT token.

    Example:
        async def test_protected_endpoint(authenticated_client):
            response = await authenticated_client.get(
                "/protected",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            assert response.status_code == 200
    """
    async def get_session_override() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    # Set app.state for pytest-xdist compatibility (lifespan pattern)
    app.state.engine = engine
    app.state.async_session_maker = session_maker

    # Override session dependency
    app.dependency_overrides[get_session] = get_session_override

    # Reset middleware stack to allow modifications
    app.middleware_stack = None

    # Keep AuthMiddleware but rebuild stack to apply overrides
    app.middleware_stack = app.build_middleware_stack()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def client(
    engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    """HTTP client that bypasses authentication (alias for client_bypass_auth).

    WARNING: This fixture is for migration purposes only. Use `authenticated_client`
    for new tests to ensure auth middleware is properly tested.

    This client removes AuthMiddleware and replaces it with TestAuthMiddleware that
    directly injects user/tenant into request state without JWT validation.
    """
    async def get_session_override() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    # Set app.state for pytest-xdist compatibility (lifespan pattern)
    app.state.engine = engine
    app.state.async_session_maker = session_maker

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
    """Create a test user and return user data.

    Note: Uses a unique email to avoid conflict with the default test user
    created by default_auth_user_in_org fixture (testuser@example.com).
    """
    response = await client.post(
        "/users",
        json={
            "name": "Test User",
            "email": "fixture-test-user@example.com",
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
async def test_organization(client: AsyncClient) -> dict[str, Any]:
    """Create a test organization and return organization data.

    Note: Uses client_bypass_auth which bypasses AuthMiddleware,
    so no membership creation is needed for the default test user.
    """
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


@pytest.fixture(autouse=True)
async def default_auth_user_in_org(
    session_maker: async_sessionmaker[AsyncSession],
    reset_db: None,  # noqa: ARG001 - Ensure DB is reset before creating default user/org
) -> None:
    """Ensure default test user and default org exist with OWNER membership.

    This fixture creates the user/org/membership required for tests that rely on
    the default auth middleware credentials to have RBAC permissions.

    Runs automatically for all tests (autouse=True) so tests don't need to declare it.
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

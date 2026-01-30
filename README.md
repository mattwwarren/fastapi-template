# FastAPI Template

A production-ready FastAPI microservice template with async database access, multi-tenant isolation, and comprehensive testing.

## What you get

- Async-only API and data access
- SQLModel models with UUID primary keys and timezone-aware timestamps
- Alembic migrations with drift detection in tests
- Postgres 18 (dev/test), asyncpg driver
- ECS JSON logging via `logging.yaml`
- `/health`, `/ping`, and `/metrics` endpoints
- Pagination via `fastapi-pagination`
- Local Kubernetes dev with k3d + DevSpace
- Non-root container image

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker
- k3d, kubectl, and DevSpace (for the default local dev flow)

## Create New Project from Template

Use [Copier](https://copier.readthedocs.io/) to generate a new project:

### Quick Start

```bash
# Install Copier
pipx install copier

# Generate project with defaults
copier copy gh:mattwwarren/fastapi-template --vcs-ref copier my-project

# Generate with custom options
copier copy gh:mattwwarren/fastapi-template --vcs-ref copier my-project \
  --data project_name="My API Service" \
  --data auth_enabled=true \
  --data auth_provider=ory
```

### Available Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_name` | string | required | Project name (e.g., "User Auth Service") |
| `project_slug` | string | auto | Python package name (lowercase with underscores) |
| `description` | string | "A FastAPI microservice" | Brief project description |
| `port` | int | 8000 | Development server port |
| `auth_enabled` | bool | false | Enable authentication middleware |
| `auth_provider` | choice | none | Auth provider: none, ory, auth0, keycloak, cognito |
| `multi_tenant` | bool | true | Enable multi-tenant isolation |
| `storage_provider` | choice | local | Storage: local, s3, azure, gcs |
| `cors_origins` | string | "http://localhost:3000" | CORS allowed origins |
| `enable_metrics` | bool | true | Enable Prometheus /metrics endpoint |
| `enable_activity_logging` | bool | true | Enable audit trail logging |

### Troubleshooting Template Generation

**"Invalid template" error:**
- Ensure you're using `--vcs-ref copier` to pull from the template branch

**Generated code has syntax errors:**
- Report issue at https://github.com/mattwwarren/fastapi-template/issues

**Missing template variables:**
- Run `copier copy` without `--defaults` to see all prompts

---

## Quickstart (local)

```bash
uv sync --dev
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn fastapi_template.main:app --reload --log-config fastapi_template/core/logging.yaml
```

OpenAPI docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Quickstart (k3d + DevSpace)

This is the default workflow for local Kubernetes:

```bash
devspace build
devspace dev -p dev
```

DevSpace defaults live in `devspace.yaml` and can be overridden via env vars:

```bash
export CLUSTER_NAME=fastapi_template
export NAMESPACE=warren-enterprises-ltd
export IMAGE_NAME=fastapi_template
export IMAGE_TAG=dev
export APP_NAME=fastapi_template
export ENVIRONMENT=dev
export LOG_LEVEL=info
export POSTGRES_DB=app
export POSTGRES_USER=app
export POSTGRES_PASSWORD=app
```

### DevSpace helpers

```bash
devspace run alembic-revision -- "initial"
devspace run alembic-upgrade
devspace run k3d-down
```

## Configuration

Configuration is driven by environment variables (see `.env.example`).
Key values:

- `DATABASE_URL`: async SQLAlchemy URL, e.g. `postgresql+asyncpg://app:app@localhost:5432/app`
- `APP_NAME`, `ENVIRONMENT`
- `ENABLE_METRICS`, `SQLALCHEMY_ECHO`
- Pagination defaults: `PAGINATION_PAGE_SIZE`, `PAGINATION_PAGE_SIZE_MAX`

## Logging

Logging is configured **only** via `fastapi_template/core/logging.yaml` and is ECS JSON.
The runtime entrypoint (`scripts/start.sh`) uses `--log-config` and does not
apply its own log level overrides.

If you want a different verbosity, update `fastapi_template/core/logging.yaml` (or provide an
alternate log config at startup).

## Database model behavior

- All tables use UUID primary keys with `gen_random_uuid()` defaults.
- `created_at` and `updated_at` are timezone-aware.
- `updated_at` is maintained by a Postgres trigger, not by ORM code.

### Model registration for Alembic

Alembic autogenerate uses `SQLModel.metadata`. The module `fastapi_template/db/base.py`
imports every model that should be included in migrations. When you add a new
SQLModel table, **also add it to `fastapi_template/db/base.py`** so Alembic can detect it.

## Database migrations

```bash
alembic upgrade head
```

Never hand-write migrations. Always use:

```bash
alembic revision --autogenerate -m "your message"
```

`init_db()` is test-only; production and local dev should always run Alembic.

## API endpoints

- `GET /health`
- `GET /ping`
- `GET /organizations`
- `POST /organizations`
- `GET /organizations/{organization_id}`
- `PATCH /organizations/{organization_id}`
- `DELETE /organizations/{organization_id}`
- `GET /users`
- `POST /users`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `GET /memberships`
- `POST /memberships`
- `DELETE /memberships/{membership_id}`
- `GET /metrics` (internal-only via infra)

List endpoints use `fastapi-pagination` and return `Page` responses with stable
ordering by `created_at`.

## Health and metrics

- `/health` validates DB connectivity with a short timeout and returns 503 on
  failure.
- `/metrics` exports Prometheus metrics (intended for internal networking only).

## Tests

Tests use `pytest-docker` to launch Postgres (`tests/docker-compose.yml`) and
`pytest-alembic` to ensure schema drift is caught.

### Running the Test Suite

**Always run tests from the project root** (where `pyproject.toml` is located):

```bash
# From project root - pytest-docker starts Postgres automatically
uv run pytest
```

**Run with coverage**:

```bash
uv run pytest --cov
```

**Run specific test file**:

```bash
uv run pytest fastapi_template/tests/test_health.py
```

`pytest-docker` will automatically:
- Start a Postgres container from `tests/docker-compose.yml`
- Wait for it to be ready
- Run migrations via Alembic
- Clean up after tests finish

### Troubleshooting Tests

**"No 'script_location' key found in configuration"**
→ You're running pytest from the wrong directory. Run from project root where `pyproject.toml` is located.

**"Cannot connect to Docker daemon"**
→ Docker is not running. Start Docker and try again. `pytest-docker` requires Docker to launch the database container.

## Code quality

```bash
uv run ruff check
uv run mypy fastapi_template
uv run pre-commit run --all-files
```

## Project layout

- `fastapi_template/main.py` FastAPI app
- `fastapi_template/api/` routers
- `fastapi_template/models/` SQLModel models and schemas
- `fastapi_template/services/` CRUD helpers
- `fastapi_template/db/` async engine/session + Alembic model registry
- `alembic/` migrations
- `k8s/` Kubernetes manifests
- `devspace.yaml` DevSpace configuration

## Documentation (Sphinx)

Build the full docs locally:

```bash
uv run sphinx-build -b html docs docs/_build/html
```

Key docs live in `docs/`:

- `docs/conventions.rst`
- `docs/howto_add_feature.rst`
- `docs/troubleshooting.rst`
- `docs/decision_log.rst`
- `docs/architecture.rst`

## Decision log (summary)

- Async-only API + DB access.
- SQLModel + Alembic for schema lifecycle.
- UUID primary keys; DB-managed `updated_at`.
- ECS JSON logging from `logging.yaml`.
- k3d + DevSpace for local Kubernetes.

## How to add a model/endpoint (summary)

1. Create the SQLModel table + schemas in `fastapi_template/models/`.
2. Import the model in `fastapi_template/db/base.py` so Alembic sees it.
3. Generate a migration via `alembic revision --autogenerate`.
4. Add service helpers in `fastapi_template/services/`.
5. Add endpoints in `fastapi_template/api/`.
6. Add tests under `fastapi_template/tests/`.

## Troubleshooting (quick hits)

- Missing tables in tests: ensure the model is imported in `fastapi_template/db/base.py`.
- DevSpace can't find pods: check image selector and run `devspace build`.
- Logs look wrong: `fastapi_template/core/logging.yaml` is the single source of truth.

## Notes

- Authentication is intentionally excluded. Use a separate auth service (e.g.
  Ory) and integrate via API gateway or shared identity flow.
- Kubernetes manifests are currently static for Postgres credentials; update
  `k8s/postgres-secret.yaml` if you change these values.

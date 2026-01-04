# fastapi-template

Async-only FastAPI template with SQLModel, Alembic, Postgres, Prometheus metrics, and k3d + DevSpace for local Kubernetes workflows.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker
- k3d, kubectl, and DevSpace (for the default local dev flow)

## Quickstart (local)

```bash
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload --log-config app/core/logging.yaml
```

## Quickstart (k3d + DevSpace)

```bash
devspace dev -p dev
```

Defaults are defined in `devspace.yaml` and can be overridden via environment variables:

```bash
export CLUSTER_NAME=fastapi-template
export NAMESPACE=dev
export IMAGE_NAME=fastapi-template
export IMAGE_TAG=dev
export POSTGRES_DB=app
export POSTGRES_USER=app
export POSTGRES_PASSWORD=app
```

## Database migrations

```bash
alembic upgrade head
```

`init_db()` is test-only; production and local dev should run Alembic migrations.

### DevSpace helpers

```bash
devspace run alembic-revision -- "initial"
devspace run alembic-upgrade
```

## Tests

Tests use `pytest-docker` to launch a Postgres container via `tests/docker-compose.yml`.
Schema drift is checked via `pytest-alembic` against SQLModel metadata.

```bash
uv run pytest
```

## Endpoints

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

List endpoints use `fastapi-pagination` and return standard `Page` responses.

Note: the kubectl manifests are currently static for Postgres credentials; update
`k8s/postgres-secret.yaml` if you change these values.
